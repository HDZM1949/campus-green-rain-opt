# -*- coding: utf-8 -*-
"""M5-C Monte Carlo 稳健性（日程 D12；论文 8.4；图 T12 素材）

对不确定性参数联合抽样（N=500，frac 模式，B=100 万）：
  CN ±10% 均匀；单价 ±20% 均匀；降温系数 ±30% 均匀
统计：三档方案目标值分布、最优解投向结构（硬化区 vs 绿地区）频率、
     关键地块入选频率、相对基准的达标概率。
输出：输出/m5_mc_samples.csv；输出/m5_mc_summary.csv；输出/m5_mc_parcels.csv
用法：C:\\Python314\\python.exe m5_montecarlo.py
"""
import csv
import os
import sys
from collections import defaultdict

import numpy as np

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

from m5_common import (GREEN, HARD, OUT_DIR, build_options, fmt_chosen, pareto, trio)

N = 500
SEED = 20260926
B_MAIN = 100.0
N_EPS = 11


def main():
    rng = np.random.default_rng(SEED)
    cn_s = rng.uniform(0.90, 1.10, N)
    ct_s = rng.uniform(0.80, 1.20, N)
    dt_s = rng.uniform(0.70, 1.30, N)

    # 基准（用于达标率比较）
    opts0, _ = build_options()
    f0 = pareto(opts0, B_MAIN, 'frac', n_eps=N_EPS)
    t0 = trio(f0)
    dq_ref = max(r['dq'] for r in f0)
    dt_ref = max(r['dt'] for r in f0)
    print(f'基准: ΔQ3max={dq_ref:.1f} m³, ΔTmax={dt_ref:.0f} ℃·m²')

    samples = []
    acc_q = defaultdict(lambda: [0, 0.0])   # (pid, m) -> [入选次数, 占比合计]（径流优先解）
    acc_t = defaultdict(lambda: [0, 0.0])   # 同上（降温优先解）
    top_count = defaultdict(int)

    for i in range(N):
        opts, _ = build_options(cn_scale=cn_s[i], cost_scale=ct_s[i], dt_scale=dt_s[i])
        front = pareto(opts, B_MAIN, 'frac', n_eps=N_EPS)
        t = trio(front)
        rq, rb, rt = t['径流优先'], t['均衡'], t['降温优先']
        for k, x in rq['chosen']:
            acc_q[k][0] += 1
            acc_q[k][1] += x
        for k, x in rt['chosen']:
            acc_t[k][0] += 1
            acc_t[k][1] += x
        if rq['chosen']:
            top = max(rq['chosen'], key=lambda tt: tt[1])[0]
            top_count[f'{top[0]}×{top[1]}'] += 1
        samples.append({
            'cn_scale': round(float(cn_s[i]), 4),
            'cost_scale': round(float(ct_s[i]), 4),
            'dt_scale': round(float(dt_s[i]), 4),
            '径流优先_ΔQ3_m3': round(rq['dq'], 1),
            '径流优先_ΔT_℃m2': round(rq['dt']),
            '均衡_ΔQ3_m3': round(rb['dq'], 1),
            '均衡_ΔT_℃m2': round(rb['dt']),
            '降温优先_ΔQ3_m3': round(rt['dq'], 1),
            '降温优先_ΔT_℃m2': round(rt['dt']),
            '径流优先_硬化区占比': round(sum(x for (p, _m), x in rq['chosen'] if p in HARD), 4),
            '径流优先_绿地区占比': round(sum(x for (p, _m), x in rq['chosen'] if p in GREEN), 4),
        })
        if (i + 1) % 100 == 0:
            print(f'... {i + 1}/{N}')

    dq = np.array([s['径流优先_ΔQ3_m3'] for s in samples])
    dtv = np.array([s['降温优先_ΔT_℃m2'] for s in samples])
    green_share = np.array([s['径流优先_绿地区占比'] for s in samples])
    dq_bal = np.array([s['均衡_ΔQ3_m3'] for s in samples])

    q = lambda a, p: float(np.percentile(a, p))
    summary = [
        ('样本数', N), ('随机种子', SEED),
        ('ΔQ3max 中位数_m3', round(q(dq, 50), 1)),
        ('ΔQ3max 5%分位_m3', round(q(dq, 5), 1)),
        ('ΔQ3max 95%分位_m3', round(q(dq, 95), 1)),
        ('ΔQ3max 变异系数', round(float(dq.std() / dq.mean()), 4)),
        ('ΔQ3max ≥ 基准×0.9 的比例', round(float((dq >= 0.9 * dq_ref).mean()), 4)),
        ('ΔTmax 中位数_℃m2', round(q(dtv, 50))),
        ('ΔTmax 5%分位_℃m2', round(q(dtv, 5))),
        ('ΔTmax 95%分位_℃m2', round(q(dtv, 95))),
        ('ΔTmax 变异系数', round(float(dtv.std() / dtv.mean()), 4)),
        ('ΔTmax ≥ 基准×0.9 的比例', round(float((dtv >= 0.9 * dt_ref).mean()), 4)),
        ('均衡型 ΔQ3 中位数_m3', round(q(dq_bal, 50), 1)),
        ('径流优先解含绿地区(>0.1%)的样本比例', round(float((green_share > 1e-3).mean()), 4)),
        ('绿地区占比中位数', round(q(green_share, 50), 4)),
        ('主要投入地块（径流优先解）', '; '.join(f'{k} {v / N:.0%}' for k, v in
                                             sorted(top_count.items(), key=lambda kv: -kv[1])[:3])),
    ]
    with open(os.path.join(OUT_DIR, 'm5_mc_summary.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['指标', '值'])
        w.writerows(summary)
    print('\n--- 汇总 ---')
    for k, v in summary:
        print(f'{k}: {v}')

    with open(os.path.join(OUT_DIR, 'm5_mc_samples.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(samples[0].keys()))
        w.writeheader()
        w.writerows(samples)

    with open(os.path.join(OUT_DIR, 'm5_mc_parcels.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['编号', '措施', '径流优先_入选频率', '径流优先_平均占比',
                    '降温优先_入选频率', '降温优先_平均占比'])
        keys = sorted(set(acc_q) | set(acc_t))
        for k in keys:
            w.writerow([k[0], k[1],
                        round(acc_q[k][0] / N, 4), round(acc_q[k][1] / N, 4),
                        round(acc_t[k][0] / N, 4), round(acc_t[k][1] / N, 4)])
    print('saved: m5_mc_samples.csv / m5_mc_summary.csv / m5_mc_parcels.csv')
    print('done')


if __name__ == '__main__':
    main()
