# -*- coding: utf-8 -*-
"""M4-A 单地块措施选项表（v3：数据源统一到 m5_common.build_options）

本脚本不再自算系数，而是调用公共模块（与 m4_optimize / m5_* 使用完全相同的数值），
仅负责生成"给人看"的报告表：输出/措施选项表.csv

参数口径（来源见 04-数据/公开资料/参数来源说明.md）：
  措施        等效CN  单价元/m2  ΔT系数℃/m2
  保持现状     原CN      0          0
  雨水花园      66      200         7    ← 简易型取区间低段（150–800）
  下沉式绿地    68       45         6    ← 区间 40–50
  透水铺装      80      130         4    ← 区间 60–200
注：ΔQ_3年每万元 为"单措施假设"下的效率，其中"工程可行=N"的组合在优化模型中
    不可选（适用性约束），仅作假设参照；论文中比较效率须限定在可行集内
    （口径说明见 05-模型/建模日志.md 的 M5 节）。
"""
import csv
import os
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

from m4_optimize import FEASIBLE, MEASURE_ORDER
from m5_common import OUT_DIR, build_options

T_LIST = [1, 3, 5, 10]


def main():
    opts, parcels = build_options()
    pinfo = {p['id']: p for p in parcels}
    rows = []
    for pid in sorted(pinfo):
        if pid == 'REM':
            continue
        for m in MEASURE_ORDER:
            k = (pid, m)
            if k not in opts:
                continue
            o = opts[k]
            area = pinfo[pid]['area']
            cost = o['cost']
            row = {'编号': pid, '名称': pinfo[pid]['name'], '面积_m2': area,
                   '现状类型': o['type'], '措施': m, 'CN_新': round(o['cn'], 1),
                   '工程可行': 'Y' if m in FEASIBLE[o['type']] else 'N',
                   '造价_元': round(cost),
                   'ΔT_pm2_℃': round(o['dt'] / area, 1),
                   'ΔT每万元_℃m2': round(o['dt'] * 10000.0 / cost, 1) if cost else 0.0,
                   'ΔT_收益_℃m2': round(o['dt'])}
            for t in T_LIST:
                row[f'ΔQ_{t}年_m3'] = round(o['dq_by_t'][t], 2)
            row['ΔQ_3年每万元_m3'] = round(o['dq_by_t'][3] * 10000.0 / cost, 2) if cost else 0.0
            rows.append(row)

    path = os.path.join(OUT_DIR, '措施选项表.csv')
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print('saved:', path, '| rows', len(rows))
    print('\n--- 预览：P04 球场区（8477 m2，球场） ---')
    for r in rows:
        if r['编号'] == 'P04':
            print(r['措施'], '| 可行性', r['工程可行'], '| 造价', r['造价_元'],
                  '| ΔQ3', r['ΔQ_3年_m3'], 'm3 | ΔT', r['ΔT_收益_℃m2'], '℃m2',
                  '| ΔQ3/万', r['ΔQ_3年每万元_m3'], '| ΔT/万', r['ΔT每万元_℃m2'])


if __name__ == '__main__':
    main()
