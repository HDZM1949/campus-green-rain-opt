# -*- coding: utf-8 -*-
"""论文图件生成（批次 1：T1 / T7 / T9 / T10 / T11 / T12）

数据来源：
  05-模型/输出/*.csv（M1–M5 结果）；04-数据/场地（Bing 底图 + 地块数字化坐标）
输出：
  06-论文/figures/T*.png（300 dpi 预览）+ T*.pdf（矢量）+ 图注清单.md
用法：
  C:\\Python314\\python.exe make_figures.py            # 生成全部
  C:\\Python314\\python.exe make_figures.py T7 T9      # 只生成指定图号
口径：
  按 mathodology-figure-presets 代码模板 + 统一版式（蓝 #0072B2 / 橙 #D55E00 /
  绿 #009E73 / 紫 #CC79A7 / 灰 #7A7A7A）；保存用 save_figure(fig, stem, dpi=300)。
  地图为"数字化边界重绘示意图"，底图淡化处理并注明 Bing Maps 来源。
"""
import csv
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from matplotlib.colors import TwoSlopeNorm, to_rgba
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch, Patch, Polygon

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MODEL_OUT = os.path.join(ROOT, '05-模型', '输出')
DATA_DIR = os.path.join(ROOT, '04-数据', '场地')
FIG_DIR = os.path.join(HERE, 'figures')
sys.path.insert(0, os.path.join(HERE, 'tools'))
from matplotlib_templates import save_figure  # noqa: E402

# ---------- 全局版式 ----------
for _f in ('C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/simhei.ttf'):
    if os.path.exists(_f):
        try:
            font_manager.fontManager.addfont(_f)
        except Exception:
            pass
plt.rcParams.update({
    'font.sans-serif': ['Microsoft YaHei', 'SimHei', 'DejaVu Sans'],
    'axes.unicode_minus': False,
    'font.size': 9,
    'axes.titlesize': 10,
    'axes.labelsize': 9,
    'xtick.labelsize': 8.5,
    'ytick.labelsize': 8.5,
    'legend.fontsize': 8.5,
    'axes.edgecolor': '#555555',
    'axes.linewidth': 0.8,
    'pdf.fonttype': 42,
    'ps.fonttype': 42,
    'figure.dpi': 110,
})
BLUE, ORANGE, GREEN, PINK, GRAY = '#0072B2', '#D55E00', '#009E73', '#CC79A7', '#7A7A7A'
YELLOW = '#E69F00'
# 数学符号（mathtext；避开雅黑缺失的 Unicode 上下标字形）
DQ3 = r'$\Delta Q_3$'
DTQ = r'$\Delta T$'
DQ3MAX = r'$\Delta Q_3^{\mathrm{max}}$'
DTMAX = r'$\Delta T^{\mathrm{max}}$'
Q0S = r'$Q_0$'

# ---------- 场地几何（与 04-数据/tools/make_parcels_v2.py 数字化坐标一致） ----------
M_PER_PX = 0.5423
CROP_BOX = (200, 40, 1200, 1040)   # left, top, right, bottom（px）
CAMPUS = [(98, 20), (288, 20), (308, 345), (266, 452), (104, 460)]
PARCELS = [
    ('P01', '田径场西侧看台带', '硬化', [(113, 145), (130, 145), (130, 322), (113, 322)]),
    ('P02', '田径场北缓冲绿带', '草地', [(130, 108), (216, 108), (216, 140), (130, 140)]),
    ('P03', '跑道东侧缓冲带', '草地', [(222, 145), (243, 145), (243, 326), (222, 326)]),
    ('P04', '球场区（塑胶场地）', '球场', [(245, 155), (294, 155), (294, 328), (245, 328)]),
    ('P05', '球场北侧绿地', '草地', [(246, 122), (290, 122), (290, 152), (246, 152)]),
    ('P06', '北区楼间绿地', '草地', [(150, 40), (250, 40), (250, 106), (150, 106)]),
    ('P07', '东侧路旁绿带', '林地', [(270, 35), (298, 35), (342, 338), (308, 338)]),
    ('P08', '南区林下绿地', '林地', [(176, 312), (230, 312), (230, 388), (176, 388)]),
    ('P09', '小型运动场及周边', '球场', [(234, 340), (288, 340), (288, 404), (234, 404)]),
    ('P10', '宿舍区周边', '硬化', [(122, 408), (262, 408), (262, 472), (122, 472)]),
    ('P11', '西北角绿地', '草地', [(104, 40), (148, 40), (148, 143), (104, 143)]),
    ('P12', '东南角空地', '待核', [(262, 388), (302, 388), (302, 452), (262, 452)]),
]
TYPE_COLOR = {'草地': GREEN, '林地': '#1B5E20', '硬化': GRAY, '球场': ORANGE, '待核': YELLOW}
GRADE_COLOR = {'A': ORANGE, 'B': BLUE, 'C': GRAY}


def m2px(u, v):
    return u / M_PER_PX, v / M_PER_PX


# ---------- 数据读取 ----------
def read_csv(name, folder=MODEL_OUT):
    with open(os.path.join(folder, name), encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def parcel_best_efficiency():
    """每地块在工程可行措施内的最大 ΔQ₃/万元（数据源：措施选项表.csv）。"""
    best = {}
    for r in read_csv('措施选项表.csv'):
        if r['工程可行'] != 'Y' or r['措施'] == '保持现状':
            continue
        v = float(r['ΔQ_3年每万元_m3'])
        best[r['编号']] = max(best.get(r['编号'], 0.0), v)
    return best


def grade_of(v):
    return 'A' if v >= 2.0 else ('B' if v >= 0.5 else 'C')


# ---------- 地图底图 ----------
def map_ax(ax):
    img = plt.imread(os.path.join(DATA_DIR, '季延中学_卫星_bing_z18.png'))
    l, t, r, b = CROP_BOX
    crop = img[t:b, l:r]
    h, w = crop.shape[:2]
    if crop.ndim == 3 and crop.shape[2] == 4:
        crop = crop[..., :3]
    gray = crop.mean(axis=2, keepdims=True).repeat(3, axis=2) * 0.35 + crop * 0.65  # 淡化+低饱和
    ax.imshow(gray, extent=[0, w, h, 0], alpha=0.85)
    pts = [m2px(u, v) for u, v in CAMPUS]
    xs = [p[0] for p in pts] + [pts[0][0]]
    ys = [p[1] for p in pts] + [pts[0][1]]
    ax.plot(xs, ys, '-', color='#00C8E0', lw=2.0, alpha=.95)
    ax.set_xlim(120, 1010)
    ax.set_ylim(1000, 0)
    ax.set_aspect('equal')
    ax.axis('off')
    return ax


def draw_parcels(ax, color_of, alpha=0.6):
    for pid, name, typ, poly in PARCELS:
        pts = [m2px(u, v) for u, v in poly]
        c = color_of(pid, typ)
        ax.add_patch(Polygon(pts, closed=True, facecolor=to_rgba(c, alpha),
                             edgecolor=c, lw=1.8))
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        ax.text(cx, cy, pid, color='white', fontsize=9, ha='center', va='center',
                path_effects=[pe.withStroke(linewidth=2.8, foreground='#1a1a1a')])

def add_scalebar(ax):
    x0, y0 = 150, 958
    x1 = x0 + 50.0 / M_PER_PX
    ax.plot([x0, x1], [y0, y0], color='white', lw=2.5,
            path_effects=[pe.withStroke(linewidth=4, foreground='#333333')])
    ax.text((x0 + x1) / 2, y0 - 16, '50 m', color='white', fontsize=8.5, ha='center',
            path_effects=[pe.withStroke(linewidth=2.5, foreground='#333333')])


# ---------- T1 研究区与地块编号图 ----------
def fig_t1():
    fig, ax = plt.subplots(figsize=(6.2, 5.6), layout='constrained')
    map_ax(ax)
    draw_parcels(ax, lambda pid, typ: TYPE_COLOR[typ])
    add_scalebar(ax)
    handles = [Patch(facecolor=TYPE_COLOR[k], alpha=.6, edgecolor=TYPE_COLOR[k], label=k)
               for k in ('硬化', '球场', '草地', '林地', '待核')]
    handles.append(Line2D([], [], color='#00C8E0', lw=2, label='校园轮廓'))
    ax.legend(handles=handles, loc='lower right', frameon=True, framealpha=.9,
              title='现状下垫面', title_fontsize=8.5, borderpad=.6)
    ax.set_title('研究区（晋江市季延中学本部）与 12 个候选改造地块', fontsize=11, pad=8)
    return fig


# ---------- T7 Pareto 前沿与三档方案 ----------
def fig_t7():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.4, 3.9), layout='constrained')
    cmap_b = {50: GRAY, 100: BLUE, 200: GREEN, 400: PINK}
    for b in (50, 100, 200, 400):
        rows = read_csv(f'pareto_frac_B{int(b)}.csv')
        dq = np.array([float(x['ΔQ3_m3']) for x in rows])
        dt = np.array([float(x['ΔT_℃m2']) for x in rows])
        ax1.plot(dq, dt, '-o', color=cmap_b[b], lw=2.0 if b == 100 else 1.1,
                 ms=5 if b == 100 else 3.5, label=f'B = {b} 万元',
                 zorder=5 if b == 100 else 2)
    ax1.set_xlabel(f'径流削减量 {DQ3}（m³，3 年一遇 60 min 场次）')
    ax1.set_ylabel(f'降温收益 {DTQ}（℃·m²，面积累计）')
    ax1.set_title('(a) 四档预算的 Pareto 前沿', fontsize=10)
    ax1.legend(frameon=False, loc='upper left')
    ax1.grid(alpha=.25, lw=.6)

    rows = read_csv('pareto_frac_B100.csv')
    dq = np.array([float(x['ΔQ3_m3']) for x in rows])
    dt = np.array([float(x['ΔT_℃m2']) for x in rows])
    ax2.plot(dq, dt, '-o', color=BLUE, lw=2.0, ms=5, label='Pareto 前沿（B = 100 万元）')
    trio = {r['方案']: r for r in read_csv('三档方案_B100.csv')}
    anno = {'径流优先型': ((0, -36), ORANGE, '*', 'center'),
            '均衡型': ((10, -6), GREEN, 'D', 'left'),
            '降温优先型': ((0, 14), PINK, 'P', 'center')}
    for name, (off, c, mk, ha) in anno.items():
        r = trio[name]
        x, y = float(r['ΔQ3_m3']), float(r['ΔT_℃m2'])
        ax2.scatter([x], [y], marker=mk, s=150, c=c, zorder=6)
        ax2.annotate(f'{name}\n{DQ3} {x:.1f} m³ · {DTQ} {y:,.0f}',
                     (x, y), textcoords='offset points', xytext=off,
                     fontsize=8.5, color=c, fontweight='bold', ha=ha)
    ax2.set_xlabel(f'径流削减量 {DQ3}（m³）')
    ax2.set_ylabel(f'降温收益 {DTQ}（℃·m²）')
    ax2.set_title('(b) B = 100 万元前沿与三档推荐方案', fontsize=10)
    ax2.legend(frameon=False, loc='upper right')
    ax2.grid(alpha=.25, lw=.6)
    ax2.set_xlim(212, 262)
    ax2.set_ylim(29700, 36600)
    return fig


# ---------- T9 优先改造地图 ----------
def fig_t9():
    eff = parcel_best_efficiency()
    print('T9 效率分级（可行性内最大值）:',
          {p: (round(eff[p], 2), grade_of(eff[p])) for p in sorted(eff)})
    fig = plt.figure(figsize=(10.2, 4.9), layout='constrained')
    gs = fig.add_gridspec(1, 2, width_ratios=[1.5, 1])
    ax = fig.add_subplot(gs[0, 0])
    axb = fig.add_subplot(gs[0, 1])

    map_ax(ax)
    draw_parcels(ax, lambda pid, typ: GRADE_COLOR[grade_of(eff[pid])])
    add_scalebar(ax)
    handles = [Patch(facecolor=GRADE_COLOR['A'], alpha=.6, edgecolor=GRADE_COLOR['A'],
                     label='A 优先区（≥ 2.0 m³/万元）'),
               Patch(facecolor=GRADE_COLOR['B'], alpha=.6, edgecolor=GRADE_COLOR['B'],
                     label='B 后备区（0.5–2.0 m³/万元）'),
               Patch(facecolor=GRADE_COLOR['C'], alpha=.6, edgecolor=GRADE_COLOR['C'],
                     label='C 远期区（< 0.5 m³/万元）')]
    ax.legend(handles=handles, loc='lower right', frameon=True, framealpha=.9,
              title='优先改造等级', title_fontsize=8.5, borderpad=.6)
    ax.set_title('(a) 优先改造等级地图', fontsize=10, pad=6)

    order = sorted(eff, key=lambda p: eff[p])
    y = np.arange(len(order))
    colors = [GRADE_COLOR[grade_of(eff[p])] for p in order]
    names = {p[0]: p[1] for p in PARCELS}
    axb.barh(y, [eff[p] for p in order], color=colors, alpha=.85, height=.62)
    for i, p in enumerate(order):
        axb.text(eff[p] + .05, i, f'{eff[p]:.2f}', va='center', fontsize=8)
    axb.set_yticks(y, [f'{p} {names[p]}' for p in order], fontsize=8)
    axb.set_xlabel('单位投资径流效益（m³/万元，3 年一遇 60 min）')
    axb.set_xlim(0, 3.0)
    axb.set_title('(b) 各地块可行措施内的最高效率', fontsize=10)
    axb.grid(axis='x', alpha=.25, lw=.6)
    return fig


# ---------- T10 敏感性热图 ----------
def fig_t10():
    rows = {r['情景']: r for r in read_csv('m5_sens_indicators.csv')}
    base = rows['基准']
    b_rq_dt = float(base['径流优先_ΔT_℃m2'])
    b_ct_dq = float(base['降温优先_ΔQ3_m3'])
    order = ['CN −10%', 'CN +10%', '单价 −20%', '单价 +20%',
             '降温系数 −30%', '降温系数 +30%', '预算 50 万', '预算 200 万', '预算 400 万']
    cols = [(DQ3MAX, lambda r: float(r['ΔQ3_max_变化率'])),
            (f'{DTQ}\n（径流优先方案）', lambda r: float(r['径流优先_ΔT_℃m2']) / b_rq_dt - 1),
            (f'{DQ3}\n（降温优先方案）', lambda r: float(r['降温优先_ΔQ3_m3']) / b_ct_dq - 1),
            (DTMAX, lambda r: float(r['ΔT_max_变化率']))]
    M = np.array([[fn(rows[s]) for _, fn in cols] for s in order])

    fig = plt.figure(figsize=(10.2, 4.9), layout='constrained')
    gs = fig.add_gridspec(1, 2, width_ratios=[1.55, 1])
    ax = fig.add_subplot(gs[0, 0])
    axb = fig.add_subplot(gs[0, 1])

    norm = TwoSlopeNorm(vmin=-0.45, vcenter=0.0, vmax=2.9)
    im = ax.imshow(M, cmap='RdBu_r', norm=norm, aspect='auto')
    for (i, j), v in np.ndenumerate(M):
        txt = '0' if abs(v) < 5e-3 else f'{v * 100:+.0f}%'
        ax.text(j, i, txt, ha='center', va='center', fontsize=8.5,
                color='white' if abs(v) > 0.6 else '#222222')
    ax.set_xticks(range(len(cols)), [c for c, _ in cols], fontsize=8.5)
    ax.set_yticks(range(len(order)), order, fontsize=8.5)
    ax.set_title('(a) 关键指标相对基准的变化率（B = 100 万元）', fontsize=10)
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.colorbar(im, ax=ax, label='变化率（%，0 为白色）')

    gb = read_csv('m5_sens_green_budget.csv')
    names = [r['情形'] for r in gb]
    vals = [float(r['临界预算_万元']) for r in gb]
    y = np.arange(len(names))[::-1]
    cols_b = [ORANGE if n == '基准' else BLUE for n in names]
    axb.barh(y, vals, color=cols_b, alpha=.85, height=.6)
    for yy, v, n in zip(y, vals, names):
        axb.text(v + 6, yy, f'{v:.0f} 万', va='center', fontsize=8.5)
    axb.set_yticks(y, names, fontsize=8.5)
    axb.set_xlabel('临界预算（万元）')
    axb.set_xlim(0, 540)
    axb.set_title('(b) 绿地区进入最优解的临界预算', fontsize=10)
    axb.axvline(100, color=GRAY, ls=':', lw=1)
    axb.text(105, len(names) - 0.55, '基准预算 100 万', color=GRAY, fontsize=8, va='top')
    axb.grid(axis='x', alpha=.25, lw=.6)
    return fig


# ---------- T11 情景对比 ----------
def fig_t11():
    rows = read_csv('m5_scen_table.csv')
    rows.sort(key=lambda r: float(r['雨量P_mm']))
    short = {'1年一遇 60min': '1 年一遇\n60 min',
             '3年一遇 60min（主口径）': '3 年一遇\n60 min（主口径）',
             '5年一遇 60min': '5 年一遇\n60 min',
             '10年一遇 60min': '10 年一遇\n60 min',
             '50年一遇 60min': '50 年一遇\n60 min',
             '3年一遇 120min': '3 年一遇\n120 min',
             '杜苏芮·泉州平均（日雨量近似）': '杜苏芮\n泉州平均',
             '杜苏芮·安海镇（日雨量近似）': '杜苏芮\n安海镇'}
    x = np.arange(len(rows))
    labels = [f"{short.get(r['情景'], r['情景'])}\n{r['雨量P_mm']} mm" for r in rows]
    q0 = [float(r['现状产流Q0_m3']) for r in rows]

    fig, (ax, axb) = plt.subplots(1, 2, figsize=(10.4, 4.1), layout='constrained',
                                  width_ratios=[1.75, 1])
    ax2 = ax.twinx()
    ax2.bar(x, q0, color='#E8E8E8', width=.6, zorder=0)
    ax2.set_ylabel(f'现状产流 {Q0S}（m³，灰柱，右轴）', color='#666666')
    ax2.tick_params(axis='y', colors='#666666')
    ax2.set_ylim(0, max(q0) * 1.55)
    ax2.set_zorder(0)
    ax.set_zorder(1)
    ax.patch.set_visible(False)

    styles = {'径流优先': (BLUE, 'o', '-'), '均衡': (GREEN, 'D', '-'), '降温优先': (PINK, 'P', '-')}
    for lab, (c, mk, ls) in styles.items():
        ys = [float(r[f'{lab}_削减率']) * 100 for r in rows]
        ax.plot(x, ys, ls, marker=mk, color=c, lw=1.8, ms=5.5, label=f'{lab}型方案')
    re_x = [i for i, r in enumerate(rows) if '杜苏芮' in r['情景']]
    re_y = [float(rows[i]['重优化_ΔQ3max_削减率']) * 100 for i in re_x]
    ax.plot(re_x, re_y, 'x', ms=10, mew=2.2, color=ORANGE,
            label=f'重优化 {DQ3MAX}（极端情景差异显著）')

    ax.set_xticks(x, labels, fontsize=8)
    ax.set_xlabel('降雨情景（按事件雨量升序）')
    ax.set_ylabel('径流削减率（%，相对该情景现状产流）')
    ax.set_ylim(0, 13.5)
    ax.set_title('(a) 各情景下的径流削减率（B = 100 万元基准方案）', fontsize=10)
    ax.legend(frameon=False, loc='upper right')
    ax.grid(axis='y', alpha=.25, lw=.6)
    # (b) 极端情景：三档方案与重优化上限对比（反超可视化）
    r = rows[-1]
    q0x = float(r['现状产流Q0_m3'])
    bars = [('径流优先型', float(r['径流优先_ΔQ3_m3']), BLUE),
            ('均衡型', float(r['均衡_ΔQ3_m3']), GREEN),
            ('降温优先型', float(r['降温优先_ΔQ3_m3']), PINK),
            ('重优化上限', float(r['重优化_ΔQ3max_m3']), ORANGE)]
    xx = np.arange(len(bars))
    axb.bar(xx, [b[1] for b in bars], color=[b[2] for b in bars], width=.62, alpha=.9)
    for i, (lab, v, c) in enumerate(bars):
        axb.text(i, v + 12, f'{v:.1f}', ha='center', fontsize=9, fontweight='bold', color=c)
        axb.text(i, v * 0.5, f'{v / q0x * 100:.1f}%', ha='center', fontsize=8.5, color='white')
    axb.set_xticks(xx, [b[0] for b in bars], fontsize=8.5)
    axb.set_ylabel(f'径流削减量 {DQ3}（m³）')
    axb.set_ylim(0, 620)
    axb.set_title('(b) 极端情景（杜苏芮·安海镇 263.9 mm）\n降温优先型的径流削减反超', fontsize=10)
    axb.grid(axis='y', alpha=.25, lw=.6)
    return fig


# ---------- T12 Monte Carlo 稳健性 ----------
def fig_t12():
    s = read_csv('m5_mc_samples.csv')
    dq = np.array([float(r['径流优先_ΔQ3_m3']) for r in s])
    dt = np.array([float(r['降温优先_ΔT_℃m2']) for r in s])

    fig, axes = plt.subplots(1, 3, figsize=(10.4, 3.5), layout='constrained',
                             width_ratios=[1, 1, 1.35])
    for ax, vals, ref, name, unit in (
            (axes[0], dq, 248.9, f'径流优先型 {DQ3}', 'm³'),
            (axes[1], dt, 35000.0, f'降温优先型 {DTQ}', '℃·m²')):
        q5, q95 = np.percentile(vals, [5, 95])
        ax.hist(vals, bins=28, color=BLUE, alpha=.75, edgecolor='white', lw=.5)
        ax.axvspan(q5, q95, color=BLUE, alpha=.10, zorder=0)
        ax.axvline(ref, color=ORANGE, lw=1.8, label=f'基准情景 {ref:,.0f}')
        ax.axvline(float(np.median(vals)), color=GREEN, ls='--', lw=1.4,
                   label=f'中位数 {np.median(vals):,.0f}')
        ax.set_xlabel(f'{name}（{unit}）')
        ax.set_ylabel('频数（N = 500）')
        ax.legend(frameon=False)
        ax.set_title(f'({"ab"[axes.tolist().index(ax)]}) 分布（5–95%：{q5:,.0f}–{q95:,.0f}）',
                     fontsize=10)
    axb = axes[2]
    p = read_csv('m5_mc_parcels.csv')
    items = [(f"{r['编号']}×{r['措施']}", float(r['径流优先_入选频率']),
              float(r['降温优先_入选频率'])) for r in p]
    items.sort(key=lambda t: max(t[1], t[2]))
    y = np.arange(len(items))
    axb.barh(y + .19, [t[1] * 100 for t in items], height=.36, color=BLUE, label='径流优先解')
    axb.barh(y - .19, [t[2] * 100 for t in items], height=.36, color=PINK, label='降温优先解')
    for i, t in enumerate(items):
        axb.text(t[1] * 100 + 1.5, i + .19, f'{t[1] * 100:.0f}%', va='center', fontsize=8)
        if t[2] > 0:
            axb.text(t[2] * 100 + 1.5, i - .19, f'{t[2] * 100:.0f}%', va='center', fontsize=8)
    axb.set_yticks(y, [t[0] for t in items], fontsize=8.5)
    axb.set_xlabel('入选频率（%）')
    axb.set_xlim(0, 108)
    axb.legend(frameon=False, loc='lower center', bbox_to_anchor=(0.5, -0.30), ncols=2)
    axb.set_title('(c) 最优解投向结构稳定性', fontsize=10)
    axb.grid(axis='x', alpha=.25, lw=.6)
    return fig


# ---------- T4 下垫面构成与面积 ----------
def fig_t4():
    rows = read_csv('地块参数表.csv', os.path.join(ROOT, '05-模型', '输入'))
    core = [r for r in rows if r['编号'] != 'REM']
    rem = next(r for r in rows if r['编号'] == 'REM')
    core.sort(key=lambda r: -float(r['面积_m2']))

    fig, (ax, axb) = plt.subplots(1, 2, figsize=(9.8, 3.9), layout='constrained',
                                  width_ratios=[1.25, 1])
    y = np.arange(len(core))[::-1]
    ax.barh(y, [float(r['面积_m2']) for r in core],
            color=[TYPE_COLOR[r['现状类型']] for r in core], alpha=.85, height=.62)
    for yy, r in zip(y, core):
        ax.text(float(r['面积_m2']) + 90, yy, f"{float(r['面积_m2']):,.0f}", va='center', fontsize=8)
    ax.set_yticks(y, [f"{r['编号']} {r['名称']}" for r in core], fontsize=8)
    ax.set_xlabel('面积（m²）')
    ax.set_xlim(0, 11000)
    ax.set_title('(a) 12 个候选地块面积（合计 58,964 m²）', fontsize=10)
    ax.grid(axis='x', alpha=.25, lw=.6)

    agg = {}
    for r in core:
        agg[r['现状类型']] = agg.get(r['现状类型'], 0.0) + float(r['面积_m2'])
    agg['REM（建筑与道路）'] = float(rem['面积_m2'])
    items = sorted(agg.items(), key=lambda kv: -kv[1])
    total = sum(v for _, v in items)
    y2 = np.arange(len(items))[::-1]
    axb.barh(y2, [v for _, v in items],
             color=[TYPE_COLOR.get(k, '#B0B0B0') for k, _ in items], alpha=.85, height=.6)
    for yy, (k, v) in zip(y2, items):
        axb.text(v + 350, yy, f'{v:,.0f}（{v / total * 100:.0f}%）', va='center', fontsize=8)
    axb.set_yticks(y2, [k for k, _ in items], fontsize=8.5)
    axb.set_xlabel('面积（m²）')
    axb.set_xlim(0, 33500)
    axb.set_title('(b) 校园下垫面构成（数字化合计 84,599 m²）', fontsize=10)
    axb.grid(axis='x', alpha=.25, lw=.6)
    return fig


# ---------- T6 设计暴雨与现状产流 ----------
def fig_t6():
    pt = read_csv('P_T_表.csv')
    q0 = read_csv('现状产流_Q0.csv')
    fig, axes = plt.subplots(1, 3, figsize=(10.6, 3.2), layout='constrained')

    ax = axes[0]
    for dur, c in ((30, GRAY), (60, BLUE), (120, GREEN), (180, PINK)):
        rows = sorted([r for r in pt if int(r['历时t_min']) == dur], key=lambda r: int(r['重现期T_年']))
        ax.plot([int(r['重现期T_年']) for r in rows], [float(r['雨量P_mm']) for r in rows],
                '-o', color=c, ms=4, lw=1.6, label=f'{dur} min')
    ax.set_xscale('log')
    ax.set_xticks([1, 2, 3, 5, 10, 20, 50], ['1', '2', '3', '5', '10', '20', '50'])
    ax.set_xlabel('重现期 T（年，对数轴）')
    ax.set_ylabel('设计雨量 P（mm，事件口径）')
    ax.set_title('(a) 设计暴雨：雨量—重现期', fontsize=10)
    ax.legend(frameon=False, title='历时', title_fontsize=8.5)
    ax.grid(alpha=.25, lw=.6)

    for ax, col, ylab, title in ((axes[1], '总产流Q0_m3', f'现状产流 {Q0S}（m³）', '(b) 现状产流评估'),
                                 (axes[2], '等效径流系数', '等效径流系数', '(c) 等效径流系数')):
        for dur, c, mk in ((60, BLUE, 'o'), (120, GREEN, 'D')):
            rows = sorted([r for r in q0 if int(r['历时_min']) == dur], key=lambda r: int(r['重现期T_年']))
            ax.plot([int(r['重现期T_年']) for r in rows], [float(r[col]) for r in rows],
                    '-', marker=mk, color=c, ms=5, lw=1.8, label=f'{dur} min')
        ax.set_xticks([1, 3, 5, 10], ['1', '3', '5', '10'])
        ax.set_xlabel('重现期 T（年）')
        ax.set_ylabel(ylab)
        ax.set_title(title, fontsize=10)
        ax.legend(frameon=False)
        ax.grid(alpha=.25, lw=.6)
    return fig


# ---------- T8 现状与方案对比 ----------
def fig_t8():
    q0 = float([r for r in read_csv('现状产流_Q0.csv')
                if int(r['重现期T_年']) == 3 and int(r['历时_min']) == 60][0]['总产流Q0_m3'])
    trio = {r['方案']: r for r in read_csv('三档方案_B100.csv')}
    order = ['径流优先型', '均衡型', '降温优先型']
    cols = {'径流优先型': ORANGE, '均衡型': GREEN, '降温优先型': PINK}

    fig, (ax, axb) = plt.subplots(1, 2, figsize=(9.0, 3.6), layout='constrained')
    names = ['现状'] + order
    cut = [0.0] + [float(trio[k]['ΔQ3_m3']) for k in order]
    rest = [q0] + [q0 - c for c in cut[1:]]
    x = np.arange(len(names))
    ax.bar(x, rest, color='#D8D8D8', width=.6, label='未削减产流')
    ax.bar(x, cut, bottom=rest, color=[GRAY] + [cols[k] for k in order], width=.6,
           label=f'削减量 {DQ3}')
    for i in range(1, len(names)):
        ax.text(i, rest[i] + cut[i] + 45, f"−{cut[i]:.1f} m³\n（{cut[i] / q0 * 100:.1f}%）",
                ha='center', fontsize=8, color=cols[names[i]], fontweight='bold')
    ax.axhline(q0, color=GRAY, ls=':', lw=1)
    ax.text(0.01, q0 + 40, f'现状产流 {q0:,.1f} m³', fontsize=8, color=GRAY,
            transform=ax.get_yaxis_transform())
    ax.set_xticks(x, names, fontsize=9)
    ax.set_ylabel('3 年一遇 60 min 场次产流（m³）')
    ax.set_ylim(0, q0 * 1.24)
    ax.set_title('(a) 三档方案的径流削减效果（B = 100 万元）', fontsize=10)
    ax.legend(frameon=False, loc='upper right')
    ax.grid(axis='y', alpha=.25, lw=.6)

    dts = [float(trio[k]['ΔT_℃m2']) for k in order]
    axb.bar(np.arange(3), dts, color=[cols[k] for k in order], width=.55, alpha=.9)
    for i, v in enumerate(dts):
        axb.text(i, v + 600, f'{v:,.0f}', ha='center', fontsize=9, fontweight='bold')
    axb.set_xticks(np.arange(3), order, fontsize=9)
    axb.set_ylabel(f'降温收益 {DTQ}（℃·m²）')
    axb.set_ylim(0, 40200)
    axb.set_title('(b) 三档方案的降温收益', fontsize=10)
    axb.grid(axis='y', alpha=.25, lw=.6)
    return fig


# ---------- T2 技术路线图 ----------
def fig_t2():
    fig, ax = plt.subplots(figsize=(8.8, 4.4), layout='constrained')
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6)
    ax.axis('off')

    def box(x, y, w, h, title, body, fc):
        ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h,
                                    boxstyle='round,pad=0.06,rounding_size=0.12',
                                    facecolor=fc, edgecolor='#3a3a3a', lw=1.0, alpha=.94))
        ax.text(x, y + h / 2 - 0.24, title, ha='center', va='top', fontsize=9.5,
                fontweight='bold', color='white')
        ax.text(x, y - 0.16, body, ha='center', va='center', fontsize=8, color='white')

    def arrow(p1, p2):
        ax.annotate('', xy=p2, xytext=p1,
                    arrowprops=dict(arrowstyle='-|>', color='#666666', lw=1.6))

    w, h = 3.0, 1.6
    box(1.8, 4.7, w, h, '① 现实问题', '台风暴雨与高温双风险\n校园改造预算有限', GRAY)
    box(5.0, 4.7, w, h, '② 问题数学化', '卫星影像 → 12 个候选地块\n公开资料检索参数（含来源）', BLUE)
    box(8.2, 4.7, w, h, '③ 模型链 M1–M3', '设计暴雨 → SCS-CN 产流\n→ 经验降温响应', GREEN)
    box(8.2, 1.6, w, h, '④ 配置优化 M4', f'双目标（{DQ3}、{DTQ}）0-1 规划\nε-约束 + scipy.milp 精确求解', ORANGE)
    box(5.0, 1.6, w, h, '⑤ 检验 M5', '敏感性 / 降雨情景\nMonte Carlo 稳健性', PINK)
    box(1.8, 1.6, w, h, '⑥ 决策输出', 'Pareto 前沿 → 三档方案\n优先改造地图 + 改造建议书', '#4B4B8F')
    arrow((3.3, 4.7), (3.5, 4.7))
    arrow((6.5, 4.7), (6.7, 4.7))
    arrow((8.2, 3.9), (8.2, 2.4))
    arrow((6.7, 1.6), (6.5, 1.6))
    arrow((3.5, 1.6), (3.3, 1.6))
    return fig


# ---------- T3 求解流程与伪代码 ----------
def fig_t3():
    fig, ax = plt.subplots(figsize=(8.8, 4.8), layout='constrained')
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 7.4)
    ax.axis('off')

    def box(x, y, w, h, text, fc, fs=8.5):
        ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h,
                                    boxstyle='round,pad=0.05,rounding_size=0.10',
                                    facecolor=fc, edgecolor='#3a3a3a', lw=1.0, alpha=.94))
        ax.text(x, y, text, ha='center', va='center', fontsize=fs, color='white')

    def arrow(p1, p2):
        ax.annotate('', xy=p2, xytext=p1,
                    arrowprops=dict(arrowstyle='-|>', color='#666666', lw=1.5))

    x0, w, h = 2.4, 4.2, 0.86
    box(x0, 6.7, w, h, f'输入：地块×措施系数表（造价 c、{DQ3}、{DTQ}）', BLUE)
    box(x0, 5.5, w, h, '约束：预算 Σc·x ≤ B；每地块至多一项；工程适用性', GRAY)
    box(x0, 4.3, w, h, f'ε-约束扫描：ε = 0…{DTMAX}，对每个 ε 求 max {DQ3}', ORANGE)
    box(x0, 3.1, w, h, 'scipy.milp（HiGHS）精确求解 → 去重', ORANGE)
    box(x0, 1.9, w, h, 'Pareto 前沿（B=100 万：6 点）', GREEN)
    box(x0, 0.7, w, h, '三档方案：径流优先 / 均衡 / 降温优先', PINK)
    for y in (6.2, 5.0, 3.8, 2.6, 1.4):
        arrow((x0, y + 0.17), (x0, y + 0.0))

    ax.add_patch(FancyBboxPatch((5.35, 1.15), 4.5, 5.1,
                                boxstyle='round,pad=0.10',
                                facecolor='#F5F5F5', edgecolor='#888888', lw=1.0))
    ax.text(7.6, 5.9, '求解模型（每个 ε）', ha='center', fontsize=11, fontweight='bold')
    ax.text(7.6, 4.15,
            'max  ΔQ3(x) = Σ_jk Δq_jk·x_jk\n'
            's.t.  Σ_jk c_jk·x_jk ≤ B       （预算）\n'
            '      Σ_k x_jk ≤ 1,  x_jk ≥ 0    （地块）\n'
            '      x_jk = 0，若措施 k 不适用地块 j\n'
            '      Σ_jk Δt_jk·x_jk ≥ ε         （ε-约束）',
            ha='center', va='center', fontsize=11.5, linespacing=1.45)
    ax.text(7.6, 2.0, '双模式对照：frac（比例 LP）/ binary（整块 0-1）',
            ha='center', fontsize=9.5, color='#333333')
    ax.annotate('', xy=(5.2, 4.3), xytext=(4.55, 4.3),
                arrowprops=dict(arrowstyle='-|>', color='#666666', lw=1.5))
    return fig


FIGS = {'T1': fig_t1, 'T2': fig_t2, 'T3': fig_t3, 'T4': fig_t4, 'T6': fig_t6, 'T7': fig_t7,
        'T8': fig_t8, 'T9': fig_t9, 'T10': fig_t10, 'T11': fig_t11, 'T12': fig_t12}

CAPTIONS = {
    'T1': ('研究区与候选改造地块。底图参考 Bing Maps（影像时间未知），地块边界为影像数字化'
           '重绘示意（近似 ±5–10%）；青色线为校园轮廓。数据：04-数据/场地（坐标见 '
           'tools/make_parcels_v2.py）；复现：python make_figures.py T1'),
    'T2': ('技术路线图：从现实问题到决策输出的六阶段转化'
           '（问题 → 数据化 → 模型链 M1–M3 → 优化 M4 → 检验 M5 → 输出）。'
           '复现：python make_figures.py T2'),
    'T3': ('求解流程与优化模型：ε-约束扫描 + scipy.milp 精确求解；右侧为每个 ε 的'
           '优化模型（预算、地块、工程适用性与 ε-约束）。复现：python make_figures.py T3'),
    'T4': ('下垫面构成。(a) 12 个候选地块面积（按现状类型着色）；(b) 校园下垫面构成'
           '（数字化合计 84,599 m²，含其余区域 REM；面积为影像数字化近似值）。'
           '数据：05-模型/输入/地块参数表.csv；复现：python make_figures.py T4'),
    'T6': ('设计暴雨与现状产流。(a) 各历时设计雨量随重现期变化（泉州暴雨强度公式，事件口径）；'
           '(b) 现状产流 Q₀；(c) 等效径流系数。数据：输出/P_T_表.csv、现状产流_Q0.csv；'
           '复现：python make_figures.py T6'),
    'T7': ('Pareto 前沿与三档推荐方案。(a) 四档预算（50/100/200/400 万元）下'
           '径流削减 ΔQ₃ 与降温收益 ΔT 的非支配解；预算越大前沿整体右移，'
           '两目标始终此消彼长。(b) B=100 万元前沿上的三档方案：径流优先（248.9 m³）、'
           '均衡（226.4 m³ / 34,125 ℃·m²）、降温优先（35,000 ℃·m²）。'
           '数据：05-模型/输出/pareto_frac_B*.csv、三档方案_B100.csv；复现：python make_figures.py T7'),
    'T8': ('现状与三档方案对比（3 年一遇 60 min，B=100 万元）。(a) 削减量占现状产流的比例'
           '（灰条为未削减产流，彩条为削减量）；(b) 三档方案的降温收益。'
           '数据：输出/三档方案_B100.csv、现状产流_Q0.csv；复现：python make_figures.py T8'),
    'T9': ('优先改造等级地图。(a) 按"工程可行措施内最高单位投资径流效益（3 年一遇 60 min）"'
           '分级：A ≥2.0、B 0.5–2.0、C <0.5 m³/万元；硬化/球场区（P01/P04/P09/P10）为 A 级。'
           '(b) 各地块效率排序。数据：措施选项表.csv（工程可行=Y）；复现：python make_figures.py T9'),
    'T10': ('参数敏感性。(a) 关键指标相对基准的变化率：ΔQ₃ 对 CN 最敏感（−10% 时 −41%），'
            '降温系数仅影响 ΔT，单价缩放与预算缩放等价（齐次性）。(b) 绿地区进入'
            'ΔQ₃ 最优解的临界预算（判据：绿地面积占比 >0.1%，步长 5 万）。'
            '数据：m5_sens_indicators.csv、m5_sens_green_budget.csv；复现：python make_figures.py T10'),
    'T11': ('降雨情景对比。三条实线为基准方案（B=100 万元）在三档取向下的径流削减率，'
            '灰柱为该情景现状产流 Q₀（右轴）；"×"为重优化上限。设计暴雨范围内'
            '（1–50 年）三档方案排序稳定；杜苏芮极端情景下降温优先型的削减率反超'
            '（双目标共向）。数据：m5_scen_table.csv；复现：python make_figures.py T11'),
    'T12': ('Monte Carlo 稳健性（N=500，种子 20260926，CN±10%、单价±20%、降温系数±30% 联合均匀抽样）。'
            '(a)(b) 两目标上限的分布与基准情景对比；(c) 最优解投向结构的入选频率——'
            '硬化区（P01/P04/P09）透水铺装占比 85–86%，绿地区 0/500 进入，'
            '与临界预算 395 万元自洽。数据：m5_mc_*.csv；复现：python make_figures.py T12'),
}


def main():
    which = sys.argv[1:] or list(FIGS)
    made = []
    for key in which:
        if key not in FIGS:
            print('未知图号:', key)
            continue
        fig = FIGS[key]()
        stem = os.path.join(FIG_DIR, f'{key}_{ {"T1": "研究区与地块编号", "T2": "技术路线图", "T3": "求解流程与伪代码", "T4": "下垫面构成", "T6": "设计暴雨与现状产流", "T7": "Pareto前沿与三档方案", "T8": "现状与方案对比", "T9": "优先改造地图", "T10": "敏感性热图", "T11": "情景对比", "T12": "MC稳健性"}[key] }')
        paths = save_figure(fig, stem, dpi=300)
        plt.close(fig)
        print('saved:', paths[0].name, '+', paths[1].name)
        made.append(key)

    cap_path = os.path.join(FIG_DIR, '图注清单.md')
    with open(cap_path, 'w', encoding='utf-8', newline='') as f:
        f.write('# 图注清单（批次 1）\n\n> 生成脚本：`06-论文/make_figures.py`；'
                '版式：mathodology-figure-presets（300 dpi PNG + 矢量 PDF）。\n\n')
        for key, cap in CAPTIONS.items():
            f.write(f'## {key}\n\n{cap}\n\n')
    print('captions:', cap_path)


if __name__ == '__main__':
    main()
