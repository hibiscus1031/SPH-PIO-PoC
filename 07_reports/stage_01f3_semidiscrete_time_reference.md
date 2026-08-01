# Stage 01F3 semidiscrete DOP853 time reference

配置为 N16、`H/dx=4.06155281280883`、`t_final=0.01`。RHS 使用项目冻结的 SPH 半离散算子与 source，但不使用项目 RK2；unwrapped positions 仅在邻域和场评价时 wrap。

| solution | position sensitivity Linf | velocity sensitivity Linf | baseline nfev | tighter nfev | topology identity |
|---|---:|---:|---:|---:|---|
| MMS-A | 2.4425e-15 | 5.0737e-14 | 3875 | 7715 | PASS: 1 identity |
| MMS-B | 2.5535e-15 | 3.1641e-14 | 3875 | 7715 | FAIL: 28 / 27 identities |

MMS-B 两套参考均 finite、数值敏感性远低于 `1e-9`，所有 topology structural defects 为 0；但 baseline edge count 在 12480–12672 间变化并出现 28 个 edge identity，tighter reference 出现 27 个 identity。这属于未预登记的拓扑切换，违反 reference topology identity 硬门。

半离散参考状态：**FAIL**。因此未授权报告任何半离散 RK2 时间阶。
