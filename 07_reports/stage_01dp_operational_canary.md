# Stage 01D-P Maximum-horizon Operational Canary

三次 canary 均使用 N32、dt=1.25e-4、1600 steps、t_final=0.2、H/dx=5、c_s=20、nu=0.02、
regular layout、float64 CPU、默认 GC、`torch.no_grad()`与正常动态邻域重建。

| run | steps | finite | GC | no_grad | topology | pair residual max | viscous power max | current RSS | peak RSS | RSS Δquartile | RSS relative | time ratio | system avail min | pass |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| stage01dp_canary_r1 | 1600 | True | True | True | True | 4.57e-18 | -0.657 | 308183040 | 308183040 | 20963328 | 0.0730 | 1.0089 | 0.3827 | True |
| stage01dp_canary_r2 | 1600 | True | True | True | True | 4.57e-18 | -0.657 | 308658176 | 308658176 | 19759104 | 0.0684 | 1.0072 | 0.3801 | True |
| stage01dp_canary_r3 | 1600 | True | True | True | True | 4.57e-18 | -0.657 | 300957696 | 300957696 | 17661952 | 0.0623 | 1.0066 | 0.3761 | True |

这些结果只用于运行政策验证；没有计算或输出收敛率、误差阶或 GCI，也不属于未来正式 V2 数据。
