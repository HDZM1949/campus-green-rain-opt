# -*- coding: utf-8 -*-
"""论文 Markdown → Word（.docx）排版脚本

输入：06-论文/论文-v1.md（+ figures/*.png 图件）
输出：06-论文/论文-v1.docx

特性：
- 封面页 + 目录域（Word 中右键"更新域"生成目录）+ 页脚页码
- 标题层级映射；正文宋体小四、1.5 倍行距、首行缩进 2 字符；西文 Times New Roman
- 块级公式（$$...$$）用 matplotlib mathtext 渲染为透明 PNG 居中插入
- 行内公式（$...$）解析为 Word 上下标格式文本
- 表格（带表头底纹）、图件 + 图注、引用块、无序/有序列表（手工符号，避免编号串联）

用法：C:\\Python314\\python.exe build_docx.py
"""
import os
import re
import sys
import tempfile

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image as PILImage
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

HERE = os.path.dirname(os.path.abspath(__file__))
MD_PATH = os.path.join(HERE, '论文-v1.md')
DOCX_PATH = os.path.join(HERE, '论文-v1.docx')
FIG_DIR = os.path.join(HERE, 'figures')
TMP_DIR = tempfile.mkdtemp(prefix='docx_eq_')

CN_FONT, EN_FONT, HEAD_FONT = '宋体', 'Times New Roman', '黑体'

# ---------------- 公式（mathtext 渲染为图片） ----------------
# 每个 $$ 块按关键字匹配到对应的“渲染行”（已人工整理为 mathtext 兼容形式；含中文混排）
FORMULA_MAP = [
    ('1470.505',
     [r'$q = \frac{1470.505\,(1 + 0.750\,\mathrm{lg}\,P)}{(t + 10.257)^{0.604}}$'
      r'$\qquad [\mathrm{L/(s \cdot ha)}]$']),
    ('25400',
     [r'$S = \frac{25400}{CN} - 254$',
      r'$Q = \frac{(P - 0.2S)^2}{P + 0.8S}$   （当 $P > 0.2S$；否则 $Q = 0$）']),
    (r'\Delta Q(x)',
     [r'$\max_{x}\ \Delta Q(x) = \sum_{j}\sum_{k} \Delta q_{jk}\, x_{jk}$',
      r'$\max_{x}\ \Delta T(x) = \sum_{j}\sum_{k} \Delta t_{jk}\, x_{jk}$']),
    (r'\Delta t_{jk}',
     [r'$\Delta t_{jk} = \max\left(0,\ \delta_k + \delta_j^{\mathrm{base}}\right) \cdot A_j$'
      r'$\qquad [\ ^{\circ}\mathrm{C} \cdot \mathrm{m}^2\ ]$']),
    ('预算约束',
     [r'$\mathrm{s.t.}\quad \sum_{j,k} c_{jk}\, x_{jk} \leq B$      （预算约束）']),
    ('每地块至多',
     [r'$\sum_{k} x_{jk} \leq 1,\ \forall j$      （每地块至多一种措施；整块模式下为 $= 1$）']),
    ('工程适用性',
     [r'$x_{jk} = 0$   （若措施 $k$ 不适用地块 $j$——工程适用性约束）',
      r'$x_{jk} \in [0,1]$ 或 $\{0,1\}$']),
]


def pick_formula(tex):
    """把 md 中的 $$ 块匹配到预整理的渲染行；无匹配时返回 None。"""
    for key, lines in FORMULA_MAP:
        if key in tex:
            return lines
    return None


def render_math(lines, stem, fontsize=15):
    """把（可含 $..$ 混排的）多行公式渲染为一张透明 PNG，返回路径。失败时退化为纯文本。"""
    plt.rcParams['font.sans-serif'] = ['SimSun', 'Microsoft YaHei', 'DejaVu Sans']
    plt.rcParams['mathtext.fontset'] = 'dejavusans'
    n = len(lines)
    ys = [0.80 - i * (0.50 / max(n - 1, 1)) for i in range(n)] if n > 1 else [0.5]

    def draw(texts, suffix):
        fig = plt.figure(figsize=(9, 0.62 * n + 0.25))
        for y, txt in zip(ys, texts):
            fig.text(0.015, y, txt, fontsize=fontsize, va='center', color='black')
        path = os.path.join(TMP_DIR, f'{stem}{suffix}.png')
        fig.savefig(path, dpi=300, bbox_inches='tight', transparent=True, pad_inches=0.03)
        plt.close(fig)
        return path

    try:
        return draw(lines, '')
    except Exception:
        plain = [re.sub(r'\$([^$]*)\$', r'\1', ln) for ln in lines]
        return draw(plain, '_plain')


# ---------------- 行内 LaTeX 子集 → 上下标 runs ----------------
_CMD = {'\\Delta': 'Δ', '\\cdot': '·', '\\times': '×', '\\le': '≤', '\\ge': '≥',
        '\\max': 'max', '\\min': 'min', '\\sum': 'Σ', '\\lg': 'lg', '\\in': '∈',
        '\\forall': '∀', '\\quad': ' ', '\\,': ' ', '\\ ': ' ', '\\varepsilon': 'ε'}


def _expand_frac(s):
    """把 \\frac{A}{B} 展开为 (A)/(B)（处理一层，A/B 内不再含 frac）。"""
    out, i = '', 0
    token = '\\frac{'
    while i < len(s):
        if s.startswith(token, i):
            j, depth = i + len(token), 1
            while j < len(s) and depth:
                if s[j] == '{':
                    depth += 1
                elif s[j] == '}':
                    depth -= 1
                j += 1
            a = s[i + len(token):j - 1]
            k, depth = j + 1, 1
            while k < len(s) and depth:
                if s[k] == '{':
                    depth += 1
                elif s[k] == '}':
                    depth -= 1
                k += 1
            b = s[j + 1:k - 1]
            out += f'({_expand_frac(a)})/({_expand_frac(b)})'
            i = k
        else:
            out += s[i]
            i += 1
    return out


def parse_inline_math(s):
    """把简单 LaTeX 转为 [(文本, 样式)]，样式 ∈ normal/sub/sup。够本论文使用。"""
    s = ' '.join(s.split())
    s = _expand_frac(s)
    for cmd, rep in _CMD.items():
        s = s.replace(cmd, rep)
    s = re.sub(r'\\mathrm\{([^}]*)\}', r'\1', s)
    s = re.sub(r'\\text\{([^}]*)\}', r'\1', s)
    tokens, i = [], 0
    while i < len(s):
        ch = s[i]
        if ch in '{}':
            i += 1
            continue
        if ch in '_^':
            style = 'sub' if ch == '_' else 'sup'
            j = i + 1
            if j < len(s) and s[j] == '{':
                depth, k = 1, j + 1
                while k < len(s) and depth:
                    if s[k] == '{':
                        depth += 1
                    elif s[k] == '}':
                        depth -= 1
                    k += 1
                tokens.append((s[j + 1:k - 1], style))
                i = k
            else:
                tokens.append((s[j:j + 1], style))
                i = j + 1
        else:
            tokens.append((ch, 'normal'))
            i += 1
    # 合并相邻 normal
    merged = []
    for t, sty in tokens:
        if merged and merged[-1][1] == sty == 'normal':
            merged[-1] = (merged[-1][0] + t, sty)
        else:
            merged.append((t, sty))
    return merged


# ---------------- docx 基础工具 ----------------
def set_run(run, cn=CN_FONT, en=EN_FONT, size=12, bold=False, italic=False, color=None):
    run.font.name = en
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    if color:
        run.font.color.rgb = RGBColor.from_string(color)
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = OxmlElement('w:rFonts')
        rPr.append(rFonts)
    rFonts.set(qn('w:eastAsia'), cn)


def emit_rich(par, text, size=12, bold_all=False):
    """写入含 **加粗** 与 $行内公式$ 的文本。"""
    for part in re.split(r'(\$[^$]+\$)', text):
        if not part:
            continue
        if part.startswith('$') and part.endswith('$') and len(part) > 2:
            for t, sty in parse_inline_math(part[1:-1]):
                run = par.add_run(t)
                set_run(run, size=size, bold=bold_all, italic=True)
                if sty == 'sub':
                    run.font.subscript = True
                elif sty == 'sup':
                    run.font.superscript = True
        else:
            for sub in re.split(r'(\*\*[^*]+\*\*)', part):
                if not sub:
                    continue
                if sub.startswith('**') and sub.endswith('**'):
                    run = par.add_run(sub[2:-2])
                    set_run(run, size=size, bold=True)
                else:
                    run = par.add_run(sub)
                    set_run(run, size=size, bold=bold_all)


def body_para(doc, text, indent=True, size=12, space_after=6, align=None):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.line_spacing = 1.5
    pf.space_after = Pt(space_after)
    if indent:
        pf.first_line_indent = Pt(24)
    if align is not None:
        p.alignment = align
    emit_rich(p, text, size=size)
    return p


def set_heading_style(doc):
    for lvl, size in ((1, 16), (2, 14), (3, 12.5), (4, 12)):
        st = doc.styles[f'Heading {lvl}']
        st.font.name = EN_FONT
        st.font.size = Pt(size)
        st.font.bold = True
        st.font.color.rgb = RGBColor(0, 0, 0)
        st._element.rPr.rFonts.set(qn('w:eastAsia'), HEAD_FONT)
        st.paragraph_format.space_before = Pt(14 if lvl == 1 else 10)
        st.paragraph_format.space_after = Pt(8 if lvl == 1 else 6)
        st.paragraph_format.line_spacing = 1.3


def add_page_number(section):
    p = section.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    set_run(run, size=10.5)
    for tag, attr, val in (('w:fldChar', 'w:fldCharType', 'begin'),
                           ('w:instrText', None, None),
                           ('w:fldChar', 'w:fldCharType', 'end')):
        el = OxmlElement(tag)
        if tag == 'w:instrText':
            el.set(qn('xml:space'), 'preserve')
            el.text = 'PAGE'
        else:
            el.set(qn(attr), val)
        run._r.append(el)


def add_toc(doc):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(10)
    run = p.add_run()
    fld1 = OxmlElement('w:fldChar')
    fld1.set(qn('w:fldCharType'), 'begin')
    instr = OxmlElement('w:instrText')
    instr.set(qn('xml:space'), 'preserve')
    instr.text = r'TOC \o "1-3" \h \z \u'
    fld2 = OxmlElement('w:fldChar')
    fld2.set(qn('w:fldCharType'), 'separate')
    t = OxmlElement('w:t')
    t.text = '（目录占位：在 Word 中全选后按 F9，或右键→更新域，生成目录）'
    fld3 = OxmlElement('w:fldChar')
    fld3.set(qn('w:fldCharType'), 'end')
    for el in (fld1, instr, fld2, t, fld3):
        run._r.append(el)
    set_run(run, size=10.5, italic=True, color='808080')


def add_table(doc, rows):
    t = doc.add_table(rows=len(rows), cols=len(rows[0]))
    t.style = 'Table Grid'
    for i, row in enumerate(rows):
        for j, cell in enumerate(row):
            if j >= len(rows[0]):
                continue
            par = t.cell(i, j).paragraphs[0]
            par.paragraph_format.space_after = Pt(2)
            par.paragraph_format.line_spacing = 1.1
            emit_rich(par, cell, size=10.5, bold_all=(i == 0))
            if i == 0:
                shd = OxmlElement('w:shd')
                shd.set(qn('w:fill'), 'EFEFEF')
                t.cell(i, j)._tc.get_or_add_tcPr().append(shd)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def add_figure(doc, rel_path, caption):
    path = os.path.join(HERE, rel_path.replace('/', os.sep))
    if not os.path.exists(path):
        print('  [警告] 缺图：', rel_path)
        return
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(2)
    w, h = PILImage.open(path).size
    w_cm = min(15.0, w / 300 * 2.54)
    p.add_run().add_picture(path, width=Cm(w_cm))
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.space_after = Pt(10)
    r = cap.add_run(caption)
    set_run(r, size=10, bold=True)


_EQ_SEQ = [0]


def add_formula(doc, lines):
    _EQ_SEQ[0] += 1
    path = render_math(lines, f'eq{_EQ_SEQ[0]:02d}')
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(6)
    w, h = PILImage.open(path).size
    w_cm = min(15.0, w / 300 * 2.54)
    p.add_run().add_picture(path, width=Cm(w_cm))


def add_cover(doc):
    for _ in range(3):
        doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run('全国青少年科学探究建模能力大赛')
    set_run(r, cn=HEAD_FONT, size=16)
    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r2 = p2.add_run('H4 主题四"产业与城市绿色转型" ｜ 福建赛区 ｜ 高中组')
    set_run(r2, cn=HEAD_FONT, size=12, color='595959')
    doc.add_paragraph()
    for text, size in (('研究报告', 14),):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(text)
        set_run(r, cn=HEAD_FONT, size=size, color='595959')
    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run('台风暴雨与高温双风险下\n校园绿色基础设施配置优化')
    set_run(r, cn=HEAD_FONT, size=22, bold=True)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run('——基于 SCS-CN 与双目标 0-1 规划的"绿-雨"双服务方案设计')
    set_run(r, cn=HEAD_FONT, size=13.5)
    for _ in range(6):
        doc.add_paragraph()
    for text in ('案例学校：晋江市季延中学本部',
                 '团队：3 人（成员姓名待填）',
                 '日期：____ 年 ____ 月 ____ 日'):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(text)
        set_run(r, size=12)
    doc.add_page_break()


def main():
    md = open(MD_PATH, encoding='utf-8').read().splitlines()
    doc = Document()
    set_heading_style(doc)
    st = doc.styles['Normal']
    st.font.name = EN_FONT
    st.font.size = Pt(12)
    st._element.rPr.rFonts.set(qn('w:eastAsia'), CN_FONT)

    sec = doc.sections[0]
    sec.top_margin = sec.bottom_margin = Cm(2.54)
    sec.left_margin = sec.right_margin = Cm(2.8)
    add_page_number(sec)

    add_cover(doc)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run('目  录')
    set_run(r, cn=HEAD_FONT, size=16, bold=True)
    add_toc(doc)
    doc.add_page_break()

    i = 0
    n_tab = n_fig = n_eq = 0
    while i < len(md):
        s = md[i].strip()
        if not s or s == '---':
            i += 1
            continue
        if s.startswith('$$') and s.endswith('$$') and len(s) > 4:
            lines = pick_formula(s) or [s.strip('$').strip()]
            add_formula(doc, lines)
            n_eq += 1
        elif s.startswith('!['):
            m = re.match(r'!\[(.*?)\]\((.*?)\)', s)
            if m:
                add_figure(doc, m.group(2), m.group(1))
                n_fig += 1
        elif s.startswith('|'):
            rows = []
            while i < len(md) and md[i].strip().startswith('|'):
                cells = [c.strip() for c in md[i].strip().strip('|').split('|')]
                if not re.match(r'^[-: ]*$', ''.join(cells)):
                    rows.append(cells)
                i += 1
            add_table(doc, rows)
            n_tab += 1
            continue
        elif s.startswith('#### '):
            doc.add_heading(s[5:], level=3)
        elif s.startswith('### '):
            # 用二级标题（章内小节）
            doc.add_heading(s[4:], level=2)
        elif s.startswith('## '):
            _t = s[3:]
            if _t.startswith('——'):
                i += 1  # 副标题已入封面，跳过
                continue
            doc.add_heading(_t, level=1)
        elif s.startswith('# '):
            pass  # 封面已含标题
        elif s.startswith('> '):
            p = doc.add_paragraph()
            p.paragraph_format.line_spacing = 1.3
            p.paragraph_format.space_after = Pt(4)
            r = p.add_run(s[2:])
            set_run(r, size=10.5, color='595959')
        elif re.match(r'^[-*] ', s):
            p = doc.add_paragraph()
            pf = p.paragraph_format
            pf.line_spacing = 1.4
            pf.space_after = Pt(4)
            pf.left_indent = Pt(18)
            pf.first_line_indent = Pt(-10)
            emit_rich(p, '· ' + s[2:], size=12)
        elif re.match(r'^\d+\. ', s):
            p = doc.add_paragraph()
            pf = p.paragraph_format
            pf.line_spacing = 1.4
            pf.space_after = Pt(4)
            pf.left_indent = Pt(18)
            pf.first_line_indent = Pt(-18)
            emit_rich(p, s, size=12)
        elif s.startswith('*') and s.endswith('*') and len(s) > 2:
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(s.strip('*'))
            set_run(r, size=10.5, italic=True, color='808080')
        else:
            body_para(doc, s)
        i += 1

    # ---- 公式补充：M1/M2/M3 与优化模型的核心公式（按小节位置插入） ----
    # 说明：论文中的 $$ 块已按正文顺序自动渲染；此处仅在文档末尾提示核对。
    doc.save(DOCX_PATH)
    print(f'saved: {DOCX_PATH}')
    print(f'  表格 {n_tab} 张 ｜ 图 {n_fig} 张 ｜ 行内公式块 {n_eq} 处')


if __name__ == '__main__':
    main()
