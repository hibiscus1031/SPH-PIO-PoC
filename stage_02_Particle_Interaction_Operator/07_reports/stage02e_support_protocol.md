# Stage 02E — Support Separation Report

机器结果见 `../04_target_attribution/support_study/support_study.json`。

## 1. Fixed-N design

Support path 固定 N8×8、regular layout 和 periodic-vortex initial condition，只改变 H/dx=2.2、2.6、3.0。
这与固定 H/dx 的 resolution path 组成正交分离设计。

## 2. Raw observations

| H/dx | target L2 | target Linf |
|---:|---:|---:|
| 2.2 | 1.3329e-7 | 1.6342e-7 |
| 2.6 | 1.7612e-7 | 2.1641e-7 |
| 3.0 | 1.7612e-7 | 2.1641e-7 |

相邻 Fourier direction cosine 约0.9999957与1.0。H/dx=2.6和3.0相同，是因为 cubic-spline kernel 在2h
之外权重为零；扩大 neighbor cutoff 没有增加非零 kernel contribution。该平台是 support-contract audit 事实，
不是精度声明。

## 3. Attribution

与 resolution path 相同，instantaneous sparse/dense assembly component 为零；观测 target 来自 R2 temporal
derivative approximation。Support consistency 因而保持 diagnostic，不能从 raw support trend 推断空间修正。
