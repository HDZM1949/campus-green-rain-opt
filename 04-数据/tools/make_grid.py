# -*- coding: utf-8 -*-
"""在 Bing z18 底图上绘制 50 m 米制网格（地块划分用工作图）。
输出: 04-数据/场地/校园_网格_50m.png
说明: 网格坐标标注为「距裁剪原点（全图 px 200,40）的米数」；
      裁剪米坐标 (u,v) -> 全图 px = (200 + u/0.5423, 40 + v/0.5423)
"""
import math
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(ROOT, '..', '场地'))
M_PER_PX = 0.5423  # z18 @ 24.76°N（与 bounds_*.json 的 m_per_px_approx 一致）

SRC = os.path.join(OUT, '季延中学_卫星_bing_z18.png')
im = Image.open(SRC).convert('RGB')
print('source size', im.size)

x0, y0, x1, y1 = 200, 40, 1200, 1040
crop = im.crop((x0, y0, x1, y1))
w, h = crop.size
d = ImageDraw.Draw(crop, 'RGBA')

try:
    font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 16)
    font_b = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 20)
except Exception:
    font = font_b = ImageFont.load_default()

step = 50.0 / M_PER_PX
xs = [i * step for i in range(int(w / step) + 1)]
ys = [i * step for i in range(int(h / step) + 1)]
for i, x in enumerate(xs):
    major = (i % 2 == 0)
    d.line([(x, 0), (x, h)], fill=(255, 0, 0, 110 if major else 60),
           width=2 if major else 1)
    if major:
        d.text((x + 3, 4), f'{int(round(x * M_PER_PX))}',
               fill=(255, 40, 40, 255), font=font)
for j, y in enumerate(ys):
    major = (j % 2 == 0)
    d.line([(0, y), (w, y)], fill=(255, 0, 0, 110 if major else 60),
           width=2 if major else 1)
    if major:
        d.text((4, y + 3), f'{int(round(y * M_PER_PX))}',
               fill=(255, 40, 40, 255), font=font)

bar = 100.0 / M_PER_PX
d.rectangle([12, h - 36, 12 + bar, h - 28], fill=(255, 255, 0, 230))
d.text((12, h - 62), '100 m', fill=(255, 255, 0, 255), font=font_b)
d.polygon([(w - 40, 72), (w - 28, 112), (w - 52, 112)], fill=(255, 255, 255, 230))
d.text((w - 56, 114), 'N', fill=(255, 255, 255, 255), font=font_b)

out = os.path.join(OUT, '校园_网格_50m.png')
crop.save(out)
print('saved', out, crop.size, '| step px', round(step, 1), '| origin full px', (x0, y0))
