# -*- coding: utf-8 -*-
"""校园"绿-雨"配置优化器 · 命令行主程序

用法示例：
  python optimizer.py                       # 演示模式：预算 100 万元，输出完整报告
  python optimizer.py --budget 200          # 指定预算（万元）
  python optimizer.py --mode binary         # 整块实施（0-1）模式
  python optimizer.py --scenario 263.9      # 情景评估：事件雨量 263.9 mm（杜苏芮·安海）
  python optimizer.py --scan                # 预算扫描（50/100/200/400 万元）摘要
  python optimizer.py --export 导出结果      # 导出 Pareto 前沿与三档方案 CSV
  python optimizer.py --list                # 打印地块与措施参数表
"""
import argparse
import os
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

import core


def hr(ch='─', n=68):
    return ch * n


def main():
    ap = argparse.ArgumentParser(
        description='校园"绿-雨"配置优化器：台风暴雨与高温双风险下的绿色基础设施配置优化',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument('--budget', type=float, default=100.0, help='改造预算（万元）')
    ap.add_argument('--mode', choices=['frac', 'binary'], default='frac',
                    help='frac=面积比例（连续）；binary=整块实施（0-1）')
    ap.add_argument('--scenario', type=float, default=None, help='事件雨量（mm），覆盖主设计情景')
    ap.add_argument('--eps', type=int, default=41, help='ε-约束扫描点数')
    ap.add_argument('--scan', action='store_true', help='预算扫描摘要（50/100/200/400 万元）')
    ap.add_argument('--export', default=None, help='导出结果目录（生成两个 CSV）')
    ap.add_argument('--list', action='store_true', help='打印地块与措施参数表')
    args = ap.parse_args()

    ptab = core.load_design_storm()
    p_main = args.scenario if args.scenario is not None else ptab[core.T_MAIN]
    parcels = core.load_parcels()
    total_area = sum(p['area'] for p in parcels)

    print(hr('='))
    print('  校园"绿-雨"配置优化器  v1.0')
    print(f'  案例：晋江市季延中学本部 ｜ 候选地块 12 块 · '
          f'{sum(p["area"] for p in parcels if p["id"] != "REM"):,.0f} m²'
          f'（校园数字化合计 {total_area:,.0f} m²）')
    print(hr('='))

    # ---------- 现状评估 ----------
    q0 = core.q0_total(p_main)
    coef = q0 * 1000.0 / (p_main * total_area)
    print(f'\n【1】现状评估（' + ('主设计情景：3 年一遇 60 min' if args.scenario is None
          else '自定义事件情景（事件雨量口径）') + f'，雨量 {p_main:.1f} mm）')
    print(f'     现状产流 Q₀ = {q0:,.1f} m³ ｜ 等效径流系数 {coef:.3f}')

    if args.list:
        print(f'\n【附】地块与措施参数（来源见《使用说明.md》）')
        print(f'  {"地块":<6}{"名称":<16}{"面积m²":>9}  {"类型":<5}{"CN":>4}   可行措施')
        for pc in parcels:
            if pc['id'] == 'REM':
                continue
            feas = '、'.join(m for m in core.MEASURE_ORDER
                            if m in core.FEASIBLE[pc['type']])
            print(f'  {pc["id"]:<6}{pc["name"]:<14}{pc["area"]:>9,.0f}  '
                  f'{pc["type"]:<5}{pc["cn"]:>4.0f}   {feas}')
        print(f'\n  措施参数：', end='')
        print('；'.join(f'{m}（CN {v["cn"] if v["cn"] else "—"}，'
                        f'{v["unit"]:.0f} 元/m²，ΔT {v["dt"]:.0f} ℃/m²）'
                        for m, v in core.MEASURES.items() if m != '保持现状'))

    # ---------- 优化求解 ----------
    mode_name = '面积比例（连续）' if args.mode == 'frac' else '整块实施（0-1）'
    opts, _ = core.build_options(p_event=args.scenario)
    front = core.pareto(opts, args.budget, mode=args.mode, n_eps=args.eps)
    if not front:
        print('\n[错误] 该预算下无可行解，请提高预算或检查参数。')
        return 1
    dq_min, dq_max = min(r['dq'] for r in front), max(r['dq'] for r in front)
    dt_min, dt_max = min(r['dt'] for r in front), max(r['dt'] for r in front)
    print(f'\n【2】优化求解（预算 B = {args.budget:.0f} 万元，模式：{mode_name}）')
    print(f'     ε-约束扫描 {args.eps} 点 → Pareto 前沿 {len(front)} 个非支配解')
    print(f'     前沿范围：ΔQ₃ ∈ [{dq_min:,.1f}, {dq_max:,.1f}] m³'
          f'（削减率 {dq_min / q0 * 100:.1f}%–{dq_max / q0 * 100:.1f}%）；'
          f'ΔT ∈ [{dt_min:,.0f}, {dt_max:,.0f}] ℃·m²')
    if len(front) == 1:
        print('     注意：本情景下 Pareto 前沿退化为单点——两目标“共向”，径流与降温的最优解一致')

    # ---------- 三档方案 ----------
    t = core.trio(front)
    print(f'\n【3】三档推荐方案（B = {args.budget:.0f} 万元）')
    for name, key in (('① 径流优先型', '径流优先'), ('② 均衡型', '均衡'), ('③ 降温优先型', '降温优先')):
        r = t[key]
        print(f'   {name}：ΔQ₃ = {r["dq"]:,.1f} m³（削减率 {r["dq"] / q0 * 100:.1f}%）'
              f' ｜ ΔT = {r["dt"]:,.0f} ℃·m² ｜ 造价 {r["cost"] / 10000:.1f} 万元')
        print(f'        投向：{core.fmt_chosen(r["chosen"])}')
    if len(front) < 3:
        print('   （提示：该预算/模式下 Pareto 前沿点数较少，三档方案可能重合，属正常现象）')

    # ---------- 模式对照 ----------
    if args.mode == 'frac':
        fb = core.pareto(opts, args.budget, mode='binary', n_eps=args.eps)
        if fb:
            dq_b = max(r['dq'] for r in fb)
            print(f'\n【4】模式对照（整块实施）')
            print(f'     同预算 ΔQ₃ 上限 {dq_b:,.1f} m³'
                  f'（比面积比例模式低 {(1 - dq_b / dq_max) * 100:.0f}%）')

    # ---------- 结论提示 ----------
    print(f'\n【5】结论提示')
    print('     · 优先投向：硬化/球场区（A 级优先区，单位投资效益最高）')
    print('     · 绿地区进入最优解的临界预算 ≈ 395 万元（基准参数下）')
    print('     · 极端台风情景（强降雨）下，雨水花园的径流效率反超透水铺装')
    print('     · 详细口径与检验见《论文 v1》第 6–7 章')

    # ---------- 预算扫描 ----------
    if args.scan:
        print(f'\n【6】预算扫描（{mode_name}模式）')
        print(f'   {"预算":>8}  {"前沿点":>5}  {"ΔQ₃ 范围 (m³)":>24}  {"ΔT 范围 (℃·m²)":>28}')
        for b in (50.0, 100.0, 200.0, 400.0):
            f = core.pareto(opts, b, mode=args.mode, n_eps=args.eps)
            if not f:
                continue
            print(f'   {b:>6.0f}万  {len(f):>5}  '
                  f'[{min(r["dq"] for r in f):>8,.1f}, {max(r["dq"] for r in f):>8,.1f}]  '
                  f'[{min(r["dt"] for r in f):>12,.0f}, {max(r["dt"] for r in f):>12,.0f}]')

    # ---------- 导出 ----------
    if args.export:
        out = args.export
        os.makedirs(out, exist_ok=True)
        p1 = os.path.join(out, 'Pareto前沿.csv')
        with open(p1, 'w', encoding='utf-8-sig', newline='') as f:
            f.write('点编号,造价_元,ΔQ3_m3,ΔT_℃m2,方案摘要\n')
            for i, r in enumerate(front):
                f.write(f'{i},{r["cost"]:.0f},{r["dq"]:.1f},{r["dt"]:.1f},'
                        f'{core.fmt_chosen(r["chosen"])}\n')
        p2 = os.path.join(out, '三档方案.csv')
        with open(p2, 'w', encoding='utf-8-sig', newline='') as f:
            f.write('方案,造价_元,ΔQ3_m3,削减率,ΔT_℃m2,明细\n')
            for name, key in (('径流优先型', '径流优先'), ('均衡型', '均衡'), ('降温优先型', '降温优先')):
                r = t[key]
                f.write(f'{name},{r["cost"]:.0f},{r["dq"]:.1f},'
                        f'{r["dq"] / q0:.4f},{r["dt"]:.1f},{core.fmt_chosen(r["chosen"])}\n')
        print(f'\n【导出】已生成：\n     {p1}\n     {p2}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
