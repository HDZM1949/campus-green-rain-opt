# 模型代码（Python 3.14，系统解释器 C:\Python314\python.exe）

> 运行：`C:\Python314\python.exe m#_xxx.py`（控制台 GBK，脚本已做 UTF-8 输出重配置）
> 图件统一输出到 `06-论文/figures/`（矢量 PDF + 300dpi PNG）

## 模块清单

| 文件 | 功能 | 输入 | 输出 |
|---|---|---|---|
| `m1_design_storm.py` | 暴雨强度公式 → 各重现期设计雨量 | 公式参数 | `输出/P_T_表.csv` |
| `m2_scs_cn.py` | SCS-CN 产流函数（库） | — | — |
| `m2_run_baseline.py` | 现状产流 Q₀ 评估 | 地块表 + P_T + CN | `输出/现状产流_Q0.csv` |
| `make_param_table.py` | 地块参数表生成/维护 | 地块表 | `输入/地块参数表.csv` |
| `m5_common.py` | **公共模块**：参数化措施系数（CN/单价/降温/雨量扰动），M4/M5 单一数据源 | 地块表 + P_T | `opts`（内存） |
| `m4_build_options.py` | 单地块措施选项表（报表；系数源 = m5_common） | m5_common | `输出/措施选项表.csv`（含"工程可行"列） |
| `m4_optimize.py` | 双模式双目标优化（ε-约束 + scipy.milp）；frac/binary 对照 | m5_common + 预算 B | `输出/pareto_{frac,binary}_B*.csv`、`三档方案_B100.csv` |
| `m5_sensitivity.py` | 敏感性（CN/单价/降温/预算）+ 绿地区临界预算扫描 | m5_common | `输出/m5_sens_indicators.csv`、`m5_sens_green_budget.csv` |
| `m5_scenario.py` | 降雨情景（1–50 年 / 3 年 120min / 杜苏芮极端）：固定配置评估 + 重优化 | m5_common | `输出/m5_scen_table.csv` |
| `m5_montecarlo.py` | Monte Carlo 稳健性（N=500，三参数联合抽样） | m5_common | `输出/m5_mc_{samples,summary,parcels}.csv` |

## 口径约定（重要）

1. **系数单一数据源**：所有系数（造价 c、ΔQ、ΔT）由 `m5_common.build_options()` 生成；
   M4/M5/报表同值。CSV 仅作报表输出，**不**作为计算输入（避免舍入噪声破坏"同类地块效率相等"的对称性）。
2. **字典序 tie-breaker**：`m4_optimize.solve` 对等价最优解族（简并）按"编号优先"唯一化（λ=1e-4）；
   binary 模式下该项为常数、无影响。
3. **工程可行集**：措施适用性约束（`m4_optimize.FEASIBLE`）决定各地块可选措施；
   效率比较仅在"工程可行=Y"的组合内进行。
4. 所有中间结果落盘（`输出/`），保证可复现：脚本按 m1 → m2 → m5_common → m4 → m5 顺序可全量重跑。
