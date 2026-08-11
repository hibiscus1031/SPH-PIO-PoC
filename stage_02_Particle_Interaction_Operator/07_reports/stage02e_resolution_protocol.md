# Stage 02E — Resolution Study Report

机器结果见 `../04_target_attribution/resolution_study/resolution_study.json`。

## 1. Separation design

Resolution path 固定 H/dx=2.6、regular layout 和 periodic-vortex initial condition，仅改变 N6×6、N8×8、
N10×10。因此本路径不再把 resolution 与 support/disorder 永久绑定。

## 2. Raw target observations

| resolution | target L2 | target Linf |
|---|---:|---:|
| N6×6 | 4.5627e-8 | 5.6107e-8 |
| N8×8 | 1.7612e-7 | 2.1641e-7 |
| N10×10 | 3.2535e-7 | 4.3813e-7 |

Magnitude 随 N 增加；相邻 resolution 的 Fourier-signature direction cosine 分别约0.9999985和0.9999997。
Graph smoothness 与 deterministic reverse-null 的比值约1，不能据此确认优于非结构 null 的 spatial
smoothness。

## 3. Attribution, not performance

该 raw trend 不是离散误差收敛结果：同状态 sparse–dense instantaneous assembly L2 为0，而 target 几乎100%
由五点时间导数 reference component 闭合；window sensitivity 与 target 同量级。因此即使 magnitude 和 direction
呈系统趋势，也只能标记为 reference-temporal-error trend，不能成为 resolution-dependent correction 证据。

Resolution attribution status：`DIAGNOSTIC_REFERENCE_TEMPORAL_ERROR_TREND_NOT_DISCRETIZATION_TREND`。
