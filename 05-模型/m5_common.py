# -*- coding: utf-8 -*-
"""M5 公共模块：参数化措施选项 + 复用 M4 求解器（敏感性 / 情景 / Monte Carlo 共用）。

扰动口径（论文 8.2 / 8.4）：
  cn_scale   现状 CN 与措施等效 CN 同比例缩放（截断 ≤100）
  cost_scale 三类措施单价同比例缩放（"保持现状"仍为 0 成本）
  dt_scale   三类措施降温系数同比例缩放（现状基准温度指数不变）
  p_event    单场事件雨量覆盖（mm）；None 时按 P_T 表（60 min 行）

产出口径与 M4 一致：ΔQ 按主设计情景（3 年一遇 60 min，可用 p_event 覆盖）、
ΔT 按面积累计（℃·m²）。不含 REM（其余区域不可改造，只参与现状产流计算）。
"""
import csv
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
IN_DIR = os.path.join(HERE, '输入')
OUT_DIR = os.path.join(HERE, '输出')
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from m4_optimize import keys_for, solve  # noqa: E402

SURF_TEMP = {'硬化': 0.0, '球场': 0.0, '草地': -6.0, '林地': -9.0, '待核': 0.0, '混合': 0.0}
T_MAIN = 3
DUR_DEFAULT = 60

MEASURES = {
    '保持现状': {'cn': None, 'unit': 0.0, 'dt': 0.0},
    '雨水花园': {'cn': 66.0, 'unit': 200.0, 'dt': 7.0},
    '下沉式绿地': {'cn': 68.0, 'unit': 45.0, 'dt': 6.0},
    '透水铺装': {'cn': 80.0, 'unit': 130.0, 'dt': 4.0},
}

GREEN = {'P02', 'P03', 'P05', 'P06', 'P07', 'P08', 'P11'}   # 绿地区（草地/林地）
HARD = {'P01', 'P10'}                                        # 硬化区（看台带/宿舍周边）


def runoff_mm(p_mm, cn):
    s = 25400.0 / cn - 254.0
    ia = 0.2 * s
    if p_mm <= ia:
        return 0.0
    return (p_mm - ia) ** 2 / (p_mm + 0.8 * s)


def load_parcels():
    rows = []
    with open(os.path.join(IN_DIR, '地块参数表.csv'), encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            rows.append({'id': r['编号'].strip(), 'name': r['名称'].strip(),
                         'area': float(r['面积_m2']), 'type': r['现状类型'].strip(),
                         'cn': float(r['CN_现状'])})
    return rows


def load_ptab(dur=DUR_DEFAULT):
    tab = {}
    with open(os.path.join(OUT_DIR, 'P_T_表.csv'), encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            if int(r['历时t_min']) == dur:
                tab[int(r['重现期T_年'])] = float(r['雨量P_mm'])
    return tab


def build_options(cn_scale=1.0, cost_scale=1.0, dt_scale=1.0, p_event=None,
                  parcels=None, ptab=None):
    """生成扰动后的措施选项（结构同 m4_optimize.solve 所需）。"""
    parcels = load_parcels() if parcels is None else parcels
    ptab = load_ptab() if ptab is None else ptab
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
            opts[(pc['id'], name)] = {'type': pc['type'], 'cost': cost,
                                      'cn': cn_new,
                                      'dq': dq_by_t[T_MAIN], 'dt': dt_benefit,
                                      'dq_by_t': dq_by_t}
    return opts, parcels


def q0_total(p_mm, cn_scale=1.0, parcels=None):
    """现状产流总量（含 REM，事件口径，m³）。"""
    parcels = load_parcels() if parcels is None else parcels
    tot = 0.0
    for pc in parcels:
        cn = min(100.0, pc['cn'] * cn_scale)
        tot += runoff_mm(p_mm, cn) * pc['area'] / 1000.0
    return tot


def solve_dq_max(opts, b_wan, mode='frac'):
    parcels = sorted({k[0] for k in opts})
    keys = keys_for(parcels, opts, mode)
    return solve(keys, opts, b_wan, mode, objective='dq')


def pareto(opts, b_wan, mode='frac', n_eps=41):
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


def fmt_chosen(chosen):
    parts = []
    for (p, m), x in sorted(chosen, key=lambda t: (t[0][0], t[0][1])):
        parts.append(f'{p}×{m}' + ('' if x >= 0.999 else f'×{x:.2f}'))
    return '; '.join(parts)
