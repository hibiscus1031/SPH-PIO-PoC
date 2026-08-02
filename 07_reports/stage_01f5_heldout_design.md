# Stage 01F5 Held-out 设计

## 身份冻结

严格沿用 Stage 01F4 已封存且无旧轨迹的配置：N28、粒子数 784、`dx=2/28`、`H/dx=4.75`、`t_final=0.015`。时间步为 `1e-3, 5e-4, 2.5e-4, 1.25e-4, 6.25e-5`；共同时间为 `0.000, 0.001, ..., 0.015` 共 16 个，不允许插值。

六个 reference ID 与十个 RK2 ID 已在机器矩阵中逐条冻结，每个 ID 对应独立未来输出目录。Stage 01F3B/F3C 数据不得补入本矩阵。

## H1–H5

- H1：position/velocity 的 endpoint 和 integrated time error 均逐级下降。
- H2：四个 global fitted order 均不低于 1.80。
- H3：最细 total error 距空间平台均不超过 1%。
- H4：最细 time/space ratio 均不超过 1%。
- H5：reference、source、守恒、topology、resource 与 determinism 全部通过。

Held-out 不要求 cross term 与主配置同号，不要求从平台同一方向接近，也不要求 total exact error 严格单调。

## 独立性

N28 的身份来自 Stage 01F4 的事前封存，本阶段未根据任何新数值结果改变它。其参数、共同时间、参考层级、运行 ID、门限与重复 ID 在第一条未来轨迹之前冻结。
