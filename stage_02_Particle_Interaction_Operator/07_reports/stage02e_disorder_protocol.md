# Stage 02E — Disorder and State-Family Report

机器结果见 `../04_target_attribution/disorder_study/disorder_study.json`。

## 1. Disorder path

固定 N8×8、H/dx=2.6 和 periodic vortex，比较 regular、5% jitter、10% jitter；两个 jitter seeds 在 matrix
中预先冻结，未按结果筛选。

| disorder | target L2 | target Linf |
|---|---:|---:|
| regular | 1.7612e-7 | 2.1641e-7 |
| jitter 5% | 1.8043e-7 | 2.6412e-7 |
| jitter 10% | 1.7779e-7 | 3.0048e-7 |

L2 非单调，Linf 增加；Fourier direction cosine 从 regular→5% 约0.9965、5%→10% 约0.9798。Spatial
smoothness ratio 对所用 reverse-null 约1，故 non-random spatial structure 没有得到独立确认。

## 2. State-family path

固定 N8×8、H/dx=2.6、regular，periodic-vortex target L2 约1.7612e-7；compressive-wave target L2 约
4.0596e-8。不同 initial-condition families 已覆盖，避免单 trajectory 扩展。

## 3. Attribution boundary

Disorder/state 差异只能说明 reference-temporal approximation 对状态和布局敏感。由于 assembly spatial component
为零/roundoff，不能把其结构称为可学习 discretization correction，更不能关联 Stage 01H 的 shear diagnosis
声称 operator corrected。
