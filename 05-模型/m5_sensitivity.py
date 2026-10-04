# -*- coding: utf-8 -*-
"""M5-A 敏感性分析（日程 D10；论文 8.2；图 T10 素材）

在参数扰动下重算 Pareto 前沿与三档方案，检验关键结论的稳定性：
  基准 / CN ±10%（现状与措施 CN 同比缩放）/ 单价 ±20% / 降温系数 ±30%
  预算情景：50 / 100 / 200 / 400 万元（预算弹性对照）
附加：扫描预算，识别"绿地区首次进入 ΔQ₃ 最优解"的临界预算（含扰动情形）

输出：输出/m5_sens_indicators.csv；输出/m5_sens_green_budget.csv
用法：C:\\Python314\\python.exe m5_sensitivity.py
"""
import csv
import os
import sys

import numpy as np

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

from m5_common import (GREEN, OUT_DIR, build_options, fmt_chosen, pareto,
                       solve_dq_max, trio)

N_EPS = 41
B_MAIN = 100.0

SCEN = [
    ('基准', {}),
    ('CN −10%', {'cn_scale': 0.9}),
    ('CN +10%', {'cn_scale': 1.1}),
    ('单价 −20%', {'cost_scale': 0.8}),
    ('单价 +20%', {'cost_scale': 1.2}),
    ('降温系数 −30%', {'dt_scale': 0.7}),
    ('降温系数 +30%', {'dt_scale': 1.3}),
    ('预算 50 万', {'B': 50.0}),
    ('预算 200 万', {'B': 200.0}),
    ('预算 400 万', {'B': 400.0}),
]

GB_SCEN = [
    ('基准', 1.0, 1.0),
    ('CN −10%', 0.9, 1.0),
    ('CN +10%', 1.1, 1.0),
    ('单价 −20%', 1.0, 0.8),
    ('单价 +20%', 1.0, 1.2),
]


def run_main_table():
    rows = []
    base = None
    for name, kw in SCEN:
        kw = dict(kw)
        b = float(kw.pop('B', B_MAIN))
        opts, _ = build_options(**kw)
        front = pareto(opts, b, 'frac', n_eps=N_EPS)
        t = trio(front)
        dq_max = max(r['dq'] for r in front)
        dt_max = max(r['dt'] for r in front)
        if base is None:
            base = {'dq': dq_max, 'dt': dt_max}
        rows.append({
            '情景': name,
            '预算_万元': int(b),
            'ΔQ3_max_m3': round(dq_max, 1),
            'ΔQ3_max_变化率': round(dq_max / base['dq'] - 1.0, 4),
            'ΔT_max_℃m2': round(dt_max),
            'ΔT_max_变化率': round(dt_max / base['dt'] - 1.0, 4),
            '径流优先_ΔT_℃m2': round(t['径流优先']['dt']),
            '降温优先_ΔQ3_m3': round(t['降温优先']['dq'], 1),
            '径流优先_摘要': fmt_chosen(t['径流优先']['chosen']),
            '降温优先_摘要': fmt_chosen(t['降温优先']['chosen']),
        })
        print(f"{name:>12} | B={int(b):>3} 万 | ΔQ3max {dq_max:7.1f} m³ | ΔTmax {dt_max:9.0f} ℃·m²"
              f" | 变化率 ΔQ {dq_max / base['dq'] - 1:+.1%} / ΔT {dt_max / base['dt'] - 1:+.1%}")
    path = os.path.join(OUT_DIR, 'm5_sens_indicators.csv')
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print('saved:', path)


def run_green_budget():
    rows = []
    for name, cn_s, ct_s in GB_SCEN:
        opts, _ = build_options(cn_scale=cn_s, cost_scale=ct_s)
        hit_b, hit_share = None, None
        for b in np.arange(100.0, 500.0 + 2.5, 5.0):
            r = solve_dq_max(opts, float(b))
            if r is None:
                continue
            share = sum(x for (pid, _m), x in r['chosen'] if pid in GREEN)
            if share > 1e-3:
                hit_b, hit_share = float(b), share
                break
        rows.append({'情形': name,
                     '临界预算_万元': (int(hit_b) if hit_b is not None else '>500'),
                     '绿地面积占比': (round(hit_share, 4) if hit_share is not None else '')})
        print(f'{name}: 绿地区首次进入 ΔQ₃ 最优解的临界预算 = {hit_b} 万元'
              f'（绿地面积占比 {hit_share:.1%}）' if hit_b else f'{name}: 500 万元内绿地区未进入')
    path = os.path.join(OUT_DIR, 'm5_sens_green_budget.csv')
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print('saved:', path)


def main():
    print('=== M5-A 敏感性主表（frac 模式）===')
    run_main_table()
    print()
    print('=== 绿地区临界预算扫描（步长 5 万元，100–500 万）===')
    run_green_budget()
    print('done')


if __name__ == '__main__':
    main()
