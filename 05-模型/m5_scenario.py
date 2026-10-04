# -*- coding: utf-8 -*-
"""M5-B 情景分析（日程 D11；论文 8.3；图 T11 素材）

降雨情景：1/3/5/10/50 年一遇（60 min）+ 3 年一遇 120 min
        + 台风"杜苏芮"极端（泉州平均 186.5 mm、晋江安海镇 263.9 mm 日雨量的单场事件近似）。
对每个情景：
  (a) 固定基准方案评估——B=100 万三档方案在不同雨量下的削减量与削减率；
  (b) 重新优化——该情景下重算 Pareto 与三档方案，观察配置迁移。
输出：输出/m5_scen_table.csv
用法：C:\\Python314\\python.exe m5_scenario.py
"""
import csv
import os
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

from m5_common import (OUT_DIR, build_options, fmt_chosen, load_parcels, load_ptab,
                       pareto, q0_total, trio)

B_MAIN = 100.0
N_EPS = 41


def main():
    parcels = load_parcels()
    total_area = sum(p['area'] for p in parcels)
    p60 = load_ptab(60)
    p120 = load_ptab(120)

    scen = [
        ('1年一遇 60min', p60[1]),
        ('3年一遇 60min（主口径）', p60[3]),
        ('5年一遇 60min', p60[5]),
        ('10年一遇 60min', p60[10]),
        ('50年一遇 60min', p60[50]),
        ('3年一遇 120min', p120[3]),
        ('杜苏芮·泉州平均（日雨量近似）', 186.5),
        ('杜苏芮·安海镇（日雨量近似）', 263.9),
    ]

    opts_base, _ = build_options()
    front_base = pareto(opts_base, B_MAIN, 'frac', n_eps=N_EPS)
    t_base = trio(front_base)
    plans = {'径流优先': t_base['径流优先']['chosen'],
             '均衡': t_base['均衡']['chosen'],
             '降温优先': t_base['降温优先']['chosen']}
    print('基准三档方案（B=100 万）:')
    for lab, r in t_base.items():
        print(f"  {lab}: ΔQ3 {r['dq']:.1f} m³ | ΔT {r['dt']:.0f} ℃·m² | {fmt_chosen(r['chosen'])}")
    print()

    rows = []
    for name, p in scen:
        q0 = q0_total(p)
        coef = q0 * 1000.0 / (p * total_area)
        opts_s, _ = build_options(p_event=p)
        rec = {'情景': name, '雨量P_mm': p,
               '现状产流Q0_m3': round(q0, 1), '等效径流系数': round(coef, 3)}
        for lab in ('径流优先', '均衡', '降温优先'):
            dq = sum(x * opts_s[k]['dq'] for k, x in plans[lab])
            rec[f'{lab}_ΔQ3_m3'] = round(dq, 1)
            rec[f'{lab}_削减率'] = round(dq / q0, 4)
        front_s = pareto(opts_s, B_MAIN, 'frac', n_eps=N_EPS)
        t_s = trio(front_s)
        rq = t_s['径流优先']
        rec['重优化_ΔQ3max_m3'] = round(rq['dq'], 1)
        rec['重优化_ΔQ3max_削减率'] = round(rq['dq'] / q0, 4)
        rec['重优化_径流优先摘要'] = fmt_chosen(rq['chosen'])
        rows.append(rec)
        print(f"{name:>22} | P={p:6.1f} mm | Q0={q0:8.1f} m³ | 径流优先 ΔQ3={rec['径流优先_ΔQ3_m3']:7.1f}"
              f"（{rec['径流优先_削减率']:.1%}） | 重优化 ΔQ3max={rec['重优化_ΔQ3max_m3']:7.1f}"
              f"（{rec['重优化_ΔQ3max_削减率']:.1%}）")

    path = os.path.join(OUT_DIR, 'm5_scen_table.csv')
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print('saved:', path)


if __name__ == '__main__':
    main()
