# -*- coding: utf-8 -*-
"""M2 产流：SCS-CN 模型（分区）

    Q = (P - 0.2S)^2 / (P + 0.8S),   S = 25400/CN - 254
    Q, P 单位 mm；S 单位 mm。

说明：本模块为纯函数库，由 m4/m5 在"地块参数表"就绪后调用。
      CN 取值来源与敏感性设置记录于《建模日志.md》。
"""


def potential_retention(cn):
    """最大潜在滞留量 S（mm）"""
    if not 30 <= cn <= 100:
        raise ValueError('CN 应在 30~100 之间')
    return 25400.0 / cn - 254.0


def runoff_depth_mm(p_mm, cn):
    """事件产流深 Q（mm）"""
    s = potential_retention(cn)
    ia = 0.2 * s
    if p_mm <= ia:
        return 0.0
    return (p_mm - ia) ** 2 / (p_mm + 0.8 * s)


def runoff_volume_m3(p_mm, cn, area_m2):
    """事件产流总量（m³）"""
    return runoff_depth_mm(p_mm, cn) * area_m2 / 1000.0


if __name__ == '__main__':
    # 模块自检（仅验证公式实现，不构成项目数据）
    for cn in (60, 75, 90, 98):
        print(f'CN={cn}: S={potential_retention(cn):.1f} mm, '
              f'P=55mm -> Q={runoff_depth_mm(55, cn):.1f} mm')
