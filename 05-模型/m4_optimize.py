# -*- coding: utf-8 -*-
"""M4-B 优化 v3：双模式 × 预算情景 × 双目标（ΔQ3, ΔT）

模式 frac（默认，改造面积比例）: x_jk ∈ [0,1]，Σ_k x_jk ≤ 1
模式 binary（对照，整块实施）  : x_jk ∈ {0,1}，Σ_k x_jk = 1
适用性约束（依据《指南》设施适用条件）：
  硬化/看台带 → {透水铺装, 雨水花园}；球场 → {透水铺装}；
  草地 → {下沉式绿地, 雨水花园}；林地 → {下沉式绿地}；待核 → {透水铺装}
求解：ε-约束法 + scipy.milp 精确求解
输出：输出/pareto_{frac|binary}_B{50,100,200}.csv；三档方案_B100.csv（frac 模式）
"""
import csv
import os
import sys

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, '输出')

B_LIST = [50.0, 100.0, 200.0, 400.0]
T_COL = 'ΔQ_3年_m3'
DT_COL = 'ΔT_收益_℃m2'
EPS_N = 41
MEASURE_ORDER = ['保持现状', '雨水花园', '下沉式绿地', '透水铺装']
FEASIBLE = {
    '硬化': {'保持现状', '透水铺装', '雨水花园'},
    '球场': {'保持现状', '透水铺装'},
    '草地': {'保持现状', '下沉式绿地', '雨水花园'},
    '林地': {'保持现状', '下沉式绿地'},
    '待核': {'保持现状', '透水铺装'},
}


def load_options():
    """统一系数源：直接调用 m5_common.build_options（与 M5 各分析完全同值）。

    此前从《措施选项表.csv》回读系数，表格舍入（1 位小数）会破坏
    “同类地块效率相等”的对称性，导致等价最优解族的报告口径分裂；
    现改为函数级共享数值，CSV 仅作报表输出（T_COL/DT_COL 保留作列名兼容）。
    说明：延迟导入以避免 m4_optimize ↔ m5_common 循环导入。
    """
    from m5_common import build_options
    opts, _ = build_options()
    return sorted({k[0] for k in opts}), opts


def keys_for(parcels, opts, mode):
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
    n = len(keys)
    # 字典序 tie-breaker（λ=1e-4，M5 起启用）：措施效率相同时存在等价最优解族（简并），
    # 以极小权重优先填满编号靠前的地块，使输出唯一、可复现；不改变主目标的有效数字。
    # 注：binary 模式下每地块必选一措施（Σx=1），该项为常数、不产生影响。
    pids = sorted({k[0] for k in keys})
    rank = {p: i for i, p in enumerate(pids)}
    tb = np.array([1e-4 * (len(pids) - rank[k[0]]) for k in keys])
    c = np.array([-opts[k][objective] for k in keys]) - tb
    parcels = sorted({k[0] for k in keys})

    A, lb, ub = [], [], []
    for p in parcels:
        A.append(np.array([1.0 if keys[i][0] == p else 0.0 for i in range(n)]))
        if mode == 'binary':
            lb.append(1.0); ub.append(1.0)
        else:
            lb.append(0.0); ub.append(1.0)
    A.append(np.array([opts[k]['cost'] for k in keys]))
    lb.append(-np.inf); ub.append(b_wan * 10000.0)
    if eps_dt is not None:
        A.append(np.array([opts[k]['dt'] for k in keys]))
        lb.append(eps_dt); ub.append(np.inf)

    integ = np.ones(n) if mode == 'binary' else np.zeros(n)
    res = milp(c=c, constraints=LinearConstraint(np.array(A), lb, ub),
               integrality=integ, bounds=Bounds(0, 1))
    if not res.success:
        return None
    x = np.round(res.x) if mode == 'binary' else res.x
    chosen = [(keys[i], float(x[i])) for i in range(n) if x[i] > 1e-6]
    return {'cost': sum(opts[k]['cost'] * xx for k, xx in chosen),
            'dq': sum(opts[k]['dq'] * xx for k, xx in chosen),
            'dt': sum(opts[k]['dt'] * xx for k, xx in chosen),
            'chosen': chosen}


def fmt(chosen):
    parts = []
    for (p, m), x in sorted(chosen, key=lambda t: (t[0][0], t[0][1])):
        parts.append(f'{p}×{m}' + ('' if x >= 0.999 else f'×{x:.2f}'))
    return '; '.join(parts)


def main():
    parcels, opts = load_options()
    for mode in ('frac', 'binary'):
        keys = keys_for(parcels, opts, mode)
        print(f'=== 模式 {mode} | 决策变量 {len(keys)} ===')
        for b in B_LIST:
            r_t = solve(keys, opts, b, mode, objective='dt')
            dt_max = r_t['dt'] if r_t else 0.0
            front = []
            for eps in np.linspace(0, dt_max, EPS_N):
                r = solve(keys, opts, b, mode, eps_dt=eps, objective='dq')
                if r and not any(abs(r['dq'] - f['dq']) < 1e-6 and abs(r['dt'] - f['dt']) < 1e-6
                                 for f in front):
                    front.append(r)
            front.sort(key=lambda r: r['dt'])
            print(f'B={b} 万元: 前沿点 {len(front)} | '
                  f'ΔQ3 [{front[0]["dq"]:.0f}, {front[-1]["dq"]:.0f}] m³ | '
                  f'ΔT [{front[0]["dt"]:.0f}, {front[-1]["dt"]:.0f}] ℃·m²')
            path = os.path.join(OUT_DIR, f'pareto_{mode}_B{int(b)}.csv')
            with open(path, 'w', encoding='utf-8-sig', newline='') as f:
                w = csv.writer(f)
                w.writerow(['B_万元', '点编号', '造价_元', 'ΔQ3_m3', 'ΔT_℃m2', '方案摘要'])
                for i, r in enumerate(front):
                    w.writerow([b, i, round(r['cost']), round(r['dq'], 1),
                                round(r['dt'], 1), fmt(r['chosen'])])

            if mode == 'frac' and b == 100.0 and front:
                dqm = max(r['dq'] for r in front)
                middles = front[1:-1] if len(front) >= 3 else front
                bal = max(middles, key=lambda r: r['dq'] / dqm + (r['dt'] / dt_max if dt_max else 0))
                trio = [('径流优先型', front[0]), ('均衡型', bal), ('降温优先型', front[-1])]
                rows = [{'方案': lab, '造价_元': round(r['cost']),
                         'ΔQ3_m3': round(r['dq'], 1), 'ΔT_℃m2': round(r['dt'], 1),
                         '明细': fmt(r['chosen'])} for lab, r in trio]
                with open(os.path.join(OUT_DIR, '三档方案_B100.csv'), 'w',
                          encoding='utf-8-sig', newline='') as f:
                    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                    w.writeheader(); w.writerows(rows)
                print('  三档方案（B=100万）:')
                for r in rows:
                    print('   ', r['方案'], '| 造价', r['造价_元'], '| ΔQ3', r['ΔQ3_m3'],
                          '| ΔT', r['ΔT_℃m2'])
                    print('      ', r['明细'])
        print()
    print('done')


if __name__ == '__main__':
    main()
