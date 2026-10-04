# -*- coding: utf-8 -*-
"""M2 现状评估：按重现期计算校园现状产流量 Q0（事件口径）。

输入：
  输入/地块参数表.csv   列：编号, 名称, 面积_m2, 现状类型, CN_现状, 备注
                        （其中 编号=REM 表示"其余区域：建筑与道路等"）
  输出/P_T_表.csv       M1 生成的各重现期/历时设计雨量
输出：
  输出/现状产流_Q0.csv  每个 (重现期, 历时) 下：地块产流、REM 产流、总产流、等效径流系数
用法：
  C:\\Python314\\python.exe m2_run_baseline.py
"""
import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
IN_DIR = os.path.join(HERE, '输入')
OUT_DIR = os.path.join(HERE, '输出')

T_LIST = [1, 3, 5, 10]
DUR_LIST = [60, 120]   # min


def potential_retention(cn):
    if not 30 <= cn <= 100:
        raise ValueError(f'CN 超范围: {cn}')
    return 25400.0 / cn - 254.0


def runoff_depth_mm(p_mm, cn):
    s = potential_retention(cn)
    ia = 0.2 * s
    if p_mm <= ia:
        return 0.0
    return (p_mm - ia) ** 2 / (p_mm + 0.8 * s)


def load_parcels():
    path = os.path.join(IN_DIR, '地块参数表.csv')
    rows = []
    with open(path, encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            rows.append({
                'id': r['编号'].strip(),
                'name': r['名称'].strip(),
                'area': float(r['面积_m2']),
                'type': r['现状类型'].strip(),
                'cn': float(r['CN_现状']),
            })
    return rows


def load_p_table():
    path = os.path.join(OUT_DIR, 'P_T_表.csv')
    table = {}
    with open(path, encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            table[(int(r['重现期T_年']), int(r['历时t_min']))] = float(r['雨量P_mm'])
    return table


def main():
    parcels = load_parcels()
    ptab = load_p_table()
    out_rows = []
    for t in T_LIST:
        for dur in DUR_LIST:
            p_mm = ptab[(t, dur)]
            q_vol = {}
            for pc in parcels:
                q_mm = runoff_depth_mm(p_mm, pc['cn'])
                q_vol[pc['id']] = q_mm * pc['area'] / 1000.0   # m3
            total = sum(q_vol.values())
            total_area = sum(pc['area'] for pc in parcels)
            coef = total * 1000.0 / (p_mm * total_area)
            out_rows.append({
                '重现期T_年': t, '历时_min': dur, '雨量P_mm': p_mm,
                '地块产流合计_m3': round(sum(v for k, v in q_vol.items() if k != 'REM'), 1),
                'REM产流_m3': round(q_vol.get('REM', 0.0), 1),
                '总产流Q0_m3': round(total, 1),
                '等效径流系数': round(coef, 3),
            })
            for k, v in q_vol.items():
                out_rows[-1][f'Q_{k}_m3'] = round(v, 1)

    path = os.path.join(OUT_DIR, '现状产流_Q0.csv')
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)
    print(f'saved: {path}')
    for r in out_rows:
        print(r['重现期T_年'], '年 |', r['历时_min'], 'min | P=', r['雨量P_mm'],
              'mm | Q0=', r['总产流Q0_m3'], 'm3 | 径流系数', r['等效径流系数'])


if __name__ == '__main__':
    main()
