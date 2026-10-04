# -*- coding: utf-8 -*-
"""校园"绿-雨"配置优化器 · 核心库（自包含，仅依赖 numpy / scipy）

一站式提供：
  1) 数据加载：data/地块参数表.csv、data/设计暴雨表.csv
  2) M1/M2：SCS-CN 产流与现状产流评估
  3) M4：ε-约束 + scipy.milp 双目标精确求解（面积比例 frac / 整块实施 binary 双模式）
  4) 参数扰动接口：CN / 单价 / 降温系数 / 事件雨量（供敏感性、情景分析调用）

参数来源（详见《使用说明.md》"参数与来源"）：
  - 现状 CN：USDA SCS TR-55（水文土壤组 C）
  - 措施等效 CN 与单价：《海绵城市建设技术指南（2014）》
  - 降温系数：公开文献（北京大学学报 2017；中国园林 2022）

说明：本文件与项目主目录 05-模型/m5_common.py 逻辑同源，为独立交付版（评委可直接运行）。
"""
import csv
import os

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, 'data')

# ---------------- 参数区（如需迁移到其他学校，改这里 + 替换 data/ 两个文件） ----------------
MEASURE_ORDER = ['保持现状', '雨水花园', '下沉式绿地', '透水铺装']

MEASURES = {           # cn=改造后等效 CN；unit=单价(元/m2)；dt=降温系数(℃/m2)
    '保持现状': {'cn': None, 'unit': 0.0, 'dt': 0.0},
    '雨水花园': {'cn': 66.0, 'unit': 200.0, 'dt': 7.0},
    '下沉式绿地': {'cn': 68.0, 'unit': 45.0, 'dt': 6.0},
    '透水铺装': {'cn': 80.0, 'unit': 130.0, 'dt': 4.0},
}

SURF_TEMP = {'硬化': 0.0, '球场': 0.0, '草地': -6.0, '林地': -9.0, '待核': 0.0, '混合': 0.0}
# 现状下垫面基准温度指数（℃/m2）：用于扣除"现状已较凉爽"的部分，体现升级收益

FEASIBLE = {           # 工程适用性（依据《指南》设施适用条件）
    '硬化': {'保持现状', '透水铺装', '雨水花园'},
    '球场': {'保持现状', '透水铺装'},
    '草地': {'保持现状', '下沉式绿地', '雨水花园'},
    '林地': {'保持现状', '下沉式绿地'},
    '待核': {'保持现状', '透水铺装'},
}

T_MAIN = 3             # 主设计情景：重现期（年）
DUR_MAIN = 60          # 主设计情景：历时（min）


# ---------------- 数据加载 ----------------
def load_parcels(path=None):
    """加载地块参数表（列：编号, 名称, 面积_m2, 现状类型, CN_现状, 备注）。REM 行参与现状产流。"""
    path = path or os.path.join(DATA_DIR, '地块参数表.csv')
    rows = []
    with open(path, encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            rows.append({'id': r['编号'].strip(), 'name': r['名称'].strip(),
                         'area': float(r['面积_m2']), 'type': r['现状类型'].strip(),
                         'cn': float(r['CN_现状'])})
    return rows


def load_design_storm(path=None, dur=DUR_MAIN):
    """加载设计暴雨表（列：重现期T_年, 历时t_min, 强度q, 雨量P_mm），返回 {重现期: 雨量}。"""
    path = path or os.path.join(DATA_DIR, '设计暴雨表.csv')
    tab = {}
    with open(path, encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            if int(r['历时t_min']) == dur:
                tab[int(r['重现期T_年'])] = float(r['雨量P_mm'])
    return tab


# ---------------- M1/M2：产流计算 ----------------
def runoff_mm(p_mm, cn):
    """SCS-CN 产流深（mm）。Q = (P - 0.2S)^2 / (P + 0.8S)，S = 25400/CN - 254。"""
    s = 25400.0 / cn - 254.0
    ia = 0.2 * s
    if p_mm <= ia:
        return 0.0
    return (p_mm - ia) ** 2 / (p_mm + 0.8 * s)


def q0_total(p_mm, cn_scale=1.0, parcels=None):
    """现状产流总量（含 REM，事件口径，m³）。"""
    parcels = parcels or load_parcels()
    tot = 0.0
    for pc in parcels:
        cn = min(100.0, pc['cn'] * cn_scale)
        tot += runoff_mm(p_mm, cn) * pc['area'] / 1000.0
    return tot


def build_options(cn_scale=1.0, cost_scale=1.0, dt_scale=1.0, p_event=None,
                  parcels=None, ptab=None):
    """生成（可扰动的）单地块措施系数表。

    返回 opts[(地块号, 措施名)] = {'type','cn','cost','dq','dt','dq_by_t'}
        cost：全额造价（元）；dq：主情景径流削减（m³）；dt：降温收益（℃·m²）
    扰动口径：cn_scale（现状与措施 CN 同比例缩放）；cost_scale（单价缩放）；
             dt_scale（降温系数缩放）；p_event（事件雨量 mm，覆盖主情景）。
    """
    parcels = parcels or load_parcels()
    ptab = ptab or load_design_storm()
    t_list = sorted(ptab)
    opts = {}
    for pc in parcels:
        if pc['id'] == 'REM':
            continue
        base_temp = SURF_TEMP.get(pc['type'], 0.0)
        cn_now = min(100.0, pc['cn'] * cn_scale)
        for name, mp in MEASURES.items():
            if name == '保持现状':
                cn_new, cost, dt_pm2 = cn_now, 0.0, 0.0
            else:
                cn_new = min(100.0, mp['cn'] * cn_scale)
                cost = mp['unit'] * cost_scale * pc['area']
                dt_pm2 = mp['dt'] * dt_scale
            dq_by_t = {}
            for t in t_list:
                p = p_event if p_event is not None else ptab[t]
                if name == '保持现状':
                    dq_by_t[t] = 0.0
                else:
                    dq_by_t[t] = (runoff_mm(p, cn_now) - runoff_mm(p, cn_new)) * pc['area'] / 1000.0
            dt_benefit = 0.0 if name == '保持现状' else max(0.0, dt_pm2 + base_temp) * pc['area']
            opts[(pc['id'], name)] = {'type': pc['type'], 'cn': cn_new, 'cost': cost,
                                      'dq': dq_by_t[T_MAIN], 'dt': dt_benefit,
                                      'dq_by_t': dq_by_t}
    return opts, parcels


# ---------------- M4：优化求解 ----------------
def keys_for(parcels, opts, mode):
    """生成决策变量键列表（受工程适用性约束）。frac：不含"保持现状"；binary：含。"""
    ks = []
    for p in parcels:
        typ = opts[(p, '保持现状')]['type']
        for m in MEASURE_ORDER:
            if (p, m) not in opts or m not in FEASIBLE[typ]:
                continue
            if mode == 'binary' or m != '保持现状':
                ks.append((p, m))
    return ks


def solve(keys, opts, b_wan, mode, eps_dt=None, objective='dq'):
    """单次求解：max 目标（dq 或 dt），受预算/地块/适用性/（可选）ε 约束。

    等价解族处理：叠加极小字典序权重（λ=1e-4，编号优先），使报告口径唯一可复现；
    binary 模式下每地块必选一项（Σx=1），该项为常数、无影响。
    """
    n = len(keys)
    pids = sorted({k[0] for k in keys})
    rank = {p: i for i, p in enumerate(pids)}
    tb = np.array([1e-4 * (len(pids) - rank[k[0]]) for k in keys])
    c = np.array([-opts[k][objective] for k in keys]) - tb

    A, lb, ub = [], [], []
    for p in pids:
        A.append(np.array([1.0 if keys[i][0] == p else 0.0 for i in range(n)]))
        if mode == 'binary':
            lb.append(1.0)
            ub.append(1.0)
        else:
            lb.append(0.0)
            ub.append(1.0)
    A.append(np.array([opts[k]['cost'] for k in keys]))
    lb.append(-np.inf)
    ub.append(b_wan * 10000.0)
    if eps_dt is not None:
        A.append(np.array([opts[k]['dt'] for k in keys]))
        lb.append(eps_dt)
        ub.append(np.inf)

    integ = np.ones(n) if mode == 'binary' else np.zeros(n)
    res = milp(c=c, constraints=LinearConstraint(np.array(A), lb, ub),
               integrality=integ, bounds=Bounds(0, 1))
    if not res.success:
        return None
    x = np.round(res.x) if mode == 'binary' else res.x
    chosen = [(keys[i], float(x[i])) for i in range(n) if x[i] > 1e-6]
    return {'cost': sum(opts[k]['cost'] * v for k, v in chosen),
            'dq': sum(opts[k]['dq'] * v for k, v in chosen),
            'dt': sum(opts[k]['dt'] * v for k, v in chosen),
            'chosen': chosen}


def pareto(opts, b_wan, mode='frac', n_eps=41):
    """ε-约束扫描求 Pareto 前沿：对 ε 从 0 到 ΔT_max 等距取值，求 max ΔQ s.t. ΔT ≥ ε，去重。"""
    parcels = sorted({k[0] for k in opts})
    keys = keys_for(parcels, opts, mode)
    r_t = solve(keys, opts, b_wan, mode, objective='dt')
    dt_max = r_t['dt'] if r_t else 0.0
    front = []
    for eps in np.linspace(0.0, dt_max, n_eps):
        r = solve(keys, opts, b_wan, mode, eps_dt=float(eps), objective='dq')
        if not r:
            continue
        if any(abs(r['dq'] - f['dq']) < 1e-6 and abs(r['dt'] - f['dt']) < 1e-6 for f in front):
            continue
        front.append(r)
    front.sort(key=lambda r: (r['dt'], -r['dq']))
    return front


def trio(front):
    """三档方案：径流优先（ΔQ 最大）/ 均衡（两目标归一化加权最大）/ 降温优先（ΔT 最大）。"""
    r_q = max(front, key=lambda r: (r['dq'], -r['dt']))
    r_t = max(front, key=lambda r: (r['dt'], -r['dq']))
    dqm = r_q['dq'] or 1.0
    dtm = r_t['dt'] or 1.0
    mids = [r for r in front if r is not r_q and r is not r_t] or [r_q]
    r_b = max(mids, key=lambda r: r['dq'] / dqm + r['dt'] / dtm)
    return {'径流优先': r_q, '均衡': r_b, '降温优先': r_t}


def fmt_chosen(chosen, skip_keep=True):
    """把解格式化为可读摘要，如 'P01×透水铺装; P04×透水铺装×0.14'（面积比例）。

    skip_keep=True 时省略“保持现状”项（整块模式下更简洁；过滤后为空则明确标注）。
    """
    parts = []
    for (p, m), x in sorted(chosen, key=lambda t: (t[0][0], t[0][1])):
        if skip_keep and m == '保持现状':
            continue
        parts.append(f'{p}×{m}' + ('' if x >= 0.999 else f'×{x:.2f}'))
    return '; '.join(parts) if parts else '（全部保持现状）'
