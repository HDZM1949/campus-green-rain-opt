# -*- coding: utf-8 -*-
"""地块划分初稿 v2（按特写核对修正坐标后重绘）。

坐标：裁剪米坐标 (u,v)；原点 = 全图 px (200,40)；1 m = 1/0.5423 px
输出：04-数据/场地/地块划分_初稿.png、地块表_初稿.csv（覆盖 v1 输出）
"""
import csv
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(ROOT, '..', '场地'))
M_PER_PX = 0.5423

im = Image.open(os.path.join(OUT, '季延中学_卫星_bing_z18.png')).convert('RGB')
crop = im.crop((200, 40, 1200, 1040))
d = ImageDraw.Draw(crop, 'RGBA')
try:
    f18 = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 20)
    f14 = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 15)
    f30 = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 30)
except Exception:
    f18 = f14 = f30 = ImageFont.load_default()


def P(u, v):
    return (u / M_PER_PX, v / M_PER_PX)


campus = [(98, 20), (288, 20), (308, 345), (266, 452), (104, 460)]
pts = [P(u, v) for u, v in campus]
d.line(pts + [pts[0]], fill=(0, 255, 255, 255), width=3)

step = 50.0 / M_PER_PX
x = 0.0
while x < crop.size[0]:
    d.line([(x, 0), (x, crop.size[1])], fill=(255, 0, 0, 40))
    x += step
y = 0.0
while y < crop.size[1]:
    d.line([(0, y), (crop.size[0], y)], fill=(255, 0, 0, 40))
    y += step

COL = {'草地': (0, 158, 115), '林地': (27, 94, 32), '硬化': (120, 120, 120),
       '球场': (213, 94, 0), '待核': (230, 159, 0)}

parcels = [
    ('P01', '田径场西侧看台带', '硬化', [(113, 145), (130, 145), (130, 322), (113, 322)], ''),
    ('P02', '田径场北缓冲绿带', '草地', [(130, 108), (216, 108), (216, 140), (130, 140)], ''),
    ('P03', '跑道东侧缓冲带', '草地', [(222, 145), (243, 145), (243, 326), (222, 326)], ''),
    ('P04', '球场区（塑胶场地）', '球场', [(245, 155), (294, 155), (294, 328), (245, 328)], ''),
    ('P05', '球场北侧绿地', '草地', [(246, 122), (290, 122), (290, 152), (246, 152)], '待核：北侧节点'),
    ('P06', '北区楼间绿地', '草地', [(150, 40), (250, 40), (250, 106), (150, 106)], '待核：校区北界未定'),
    ('P07', '东侧路旁绿带', '林地', [(270, 35), (298, 35), (342, 338), (308, 338)], '待核：道路线位近似'),
    ('P08', '南区林下绿地', '林地', [(176, 312), (230, 312), (230, 388), (176, 388)], ''),
    ('P09', '小型运动场及周边', '球场', [(234, 340), (288, 340), (288, 404), (234, 404)], '新增场地，含周边铺装'),
    ('P10', '宿舍区周边', '硬化', [(122, 408), (262, 408), (262, 472), (122, 472)], '待核：建筑归属'),
    ('P11', '西北角绿地', '草地', [(104, 40), (148, 40), (148, 143), (104, 143)], '待核'),
    ('P12', '东南角空地', '待核', [(262, 388), (302, 388), (302, 452), (262, 452)], '待核'),
]


def area_m2(poly):
    s = 0.0
    for i in range(len(poly)):
        u1, v1 = poly[i]
        u2, v2 = poly[(i + 1) % len(poly)]
        s += u1 * v2 - u2 * v1
    return abs(s) / 2


rows = []
for pid, name, typ, poly, note in parcels:
    pts2 = [P(u, v) for u, v in poly]
    d.polygon(pts2, fill=COL[typ] + (80,), outline=COL[typ] + (255,))
    cx = sum(u for u, _ in poly) / len(poly)
    cy = sum(v for _, v in poly) / len(poly)
    d.text(P(cx, cy), pid, font=f18, fill=(255, 255, 255, 255), anchor='mm',
           stroke_width=2, stroke_fill=(0, 0, 0, 255))
    rows.append([pid, name, typ, round(area_m2(poly)), note])

d.rectangle([8, 8, 190, 8 + 22 * len(COL) + 12], fill=(0, 0, 0, 130))
yy = 16
for k, c in COL.items():
    d.rectangle([16, yy, 36, yy + 14], fill=c + (255,))
    d.text((42, yy - 2), k, font=f14, fill=(255, 255, 255, 255))
    yy += 22
d.text((210, 16), '地块划分初稿 v2（待踏勘核对）', font=f30,
       fill=(255, 255, 0, 255), stroke_width=2, stroke_fill=(0, 0, 0, 255))

crop.save(os.path.join(OUT, '地块划分_初稿.png'))

with open(os.path.join(OUT, '地块表_初稿.csv'), 'w', encoding='utf-8-sig', newline='') as fh:
    w = csv.writer(fh)
    w.writerow(['编号', '名称', '现状类型(初判)', '面积_m2(近似)', '备注',
                '候选改造类型1', '候选改造类型2', '踏勘确认'])
    for r in rows:
        w.writerow(r + ['', '', ''])

print('parcels:', len(rows), '| total approx area:', sum(r[3] for r in rows), 'm2')
print('saved (overwrite) 地块划分_初稿.png / 地块表_初稿.csv')
