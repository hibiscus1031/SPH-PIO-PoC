# Stage 01F2 internal/external balance

每个 start 和 midpoint force stage 分开保存 `F_internal`、`F_external`、`F_total` 与 `F_total-(F_internal+F_external)`。内部压力和黏性仍由 Stage 01C 冻结的粒子对算子产生；MMS source 只在加速度层相加。

六条动态轨迹的最大内外力组装缺陷为 `4.615396055124392e-16`，最大质量加权动量更新缺陷为 `1.4246638363167506e-17`。所有 pair-force residual 最大值为 0，normalized internal-force residual 保持在 float64 舍入尺度，viscous power 未超过正向容差。

受迫问题未施加总动量恒定要求；比较量为离散动量变化与 midpoint 内、外冲量之和。

结论：balance audit **PASS**。
