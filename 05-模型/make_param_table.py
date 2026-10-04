# -*- coding: utf-8 -*-
"""从《地块表_初稿.csv》生成《地块参数表.csv》（含 CN 现状取值 + REM 其余区域）。

规则：
  现状类型 -> CN（来源：USACE HEC / SCS TR-55 表 2-2a，土壤组按 C 组取值）
    硬化 98 | 球场 98 | 草地 74（good） | 林地 70（woods good） | 待核 86
  REM（其余区域：建筑与道路为主）CN = 95，面积 = 数字化校园轮廓 - 地块合计
输出：05-模型/输入/地块参数表.csv
"""
import csv
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.abspath(os.path.join(ROOT, '..', '04-数据', '场地', '地块表_初稿.csv'))
OUT_DIR = os.path.join(ROOT, '输入')
os.makedirs(OUT_DIR, exist_ok=True)

CN_BY_TYPE = {'硬化': 98, '球场': 98, '草地': 74, '林地': 70, '待核': 86}

# 数字化校园轮廓（裁剪米坐标），用于计算 REM 面积
OUTLINE = [(98, 20), (288, 20), (308, 345), (266, 452), (104, 460)]


def shoelace(poly):
    s = 0.0
    for i in range(len(poly)):
        u1, v1 = poly[i]
        u2, v2 = poly[(i + 1) % len(poly)]
        s += u1 * v2 - u2 * v1
    return abs(s) / 2


outline_area = shoelace(OUTLINE)

rows = []
with open(SRC, encoding='utf-8-sig', newline='') as f:
    for r in csv.DictReader(f):
        pid = r['编号'].strip()
        typ = r['现状类型(初判)'].strip()
        if pid.startswith('P'):
            rows.append({
                '编号': pid,
                '名称': r['名称'].strip(),
                '面积_m2': float(r['面积_m2(近似)']),
                '现状类型': typ,
                'CN_现状': CN_BY_TYPE[typ],
                '备注': r['备注'].strip(),
            })

total_parcel = sum(r['面积_m2'] for r in rows)
rem_area = round(outline_area - total_parcel)
rows.append({
    '编号': 'REM',
    '名称': '其余区域（建筑与道路为主）',
    '面积_m2': rem_area,
    '现状类型': '混合',
    'CN_现状': 95,
    '备注': '面积=数字化轮廓−地块合计；未细分→敏感性 90–98',
})

path = os.path.join(OUT_DIR, '地块参数表.csv')
with open(path, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=['编号', '名称', '面积_m2', '现状类型', 'CN_现状', '备注'])
    w.writeheader()
    w.writerows(rows)

print('outline area =', round(outline_area), 'm2')
print('parcels total =', round(total_parcel), 'm2 | REM =', rem_area, 'm2')
print('saved:', path)
