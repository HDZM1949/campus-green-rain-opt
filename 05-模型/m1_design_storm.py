# -*- coding: utf-8 -*-
"""M1 设计暴雨：暴雨强度公式 -> 各重现期/历时的设计雨量（事件雨量口径）

公式（泉州，含晋江）：
    q = A(1 + C·lgP) / (t + b)^n      [L/(s·ha)]，t 为历时(min)，P 为重现期(年)
    A=1470.505, C=0.750, b=10.257, n=0.604
来源：泉州城乡规划局答复（经第三方整理页转述），【原始出处待核实】；
     若后续找到晋江市专用公式，直接替换参数后复跑。

体积换算：雨量 P_mm = q × 60·t / 10000   （1 mm 水深 = 10000 L/ha）

用法：C:\\Python314\\python.exe m1_design_storm.py
输出：输出/P_T_表.csv
"""
import csv, math, os

A, C, b, n = 1470.505, 0.750, 10.257, 0.604
RETURN_PERIODS = [1, 2, 3, 5, 10, 20, 50]
DURATIONS_MIN = [30, 60, 120, 180]

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '输出')
os.makedirs(OUT_DIR, exist_ok=True)

rows = []
print(f"{'T(年)':>5} {'t(min)':>7} {'q[L/(s·ha)]':>12} {'P(mm)':>8}")
for T in RETURN_PERIODS:
    for t in DURATIONS_MIN:
        q = A * (1 + C * math.log10(T)) / (t + b) ** n
        P = q * 60.0 * t / 10000.0
        rows.append({'重现期T_年': T, '历时t_min': t,
                     '强度q_L_per_s_ha': round(q, 2), '雨量P_mm': round(P, 1)})
        print(f'{T:>5} {t:>7} {q:>12.1f} {P:>8.1f}')

path = os.path.join(OUT_DIR, 'P_T_表.csv')
with open(path, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
print('saved:', path)
