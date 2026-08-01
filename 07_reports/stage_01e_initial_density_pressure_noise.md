# Stage 01E — Initial density and pressure noise

| support_family | layout | N | cases | density_rms_mean | EOS_pressure_rms_mean |
|---|---|---|---|---|---|
| constant_neighbor | regular | 16 | 1 | 0.0004157504550326525 | 0.166300182013061 |
| constant_neighbor | regular | 24 | 1 | 0.0004157504550325188 | 0.16630018201300753 |
| constant_neighbor | regular | 32 | 1 | 0.00041575045503263494 | 0.16630018201305397 |
| constant_neighbor | regular | 48 | 1 | 0.00041575045503269414 | 0.16630018201307767 |
| constant_neighbor | regular | 64 | 1 | 0.0004157504550326254 | 0.1663001820130501 |
| constant_neighbor | jitter_05 | 16 | 10 | 0.009005020750832815 | 3.602008300333126 |
| constant_neighbor | jitter_05 | 24 | 10 | 0.00905646143371476 | 3.622584573485904 |
| constant_neighbor | jitter_05 | 32 | 10 | 0.009182858885180282 | 3.673143554072113 |
| constant_neighbor | jitter_05 | 48 | 10 | 0.009139381842500894 | 3.6557527370003577 |
| constant_neighbor | jitter_05 | 64 | 10 | 0.009139151645015614 | 3.6556606580062456 |
| constant_neighbor | jitter_10 | 16 | 10 | 0.01798279353974911 | 7.193117415899644 |
| constant_neighbor | jitter_10 | 24 | 10 | 0.01809480741802523 | 7.237922967210091 |
| constant_neighbor | jitter_10 | 32 | 10 | 0.018350265002349594 | 7.340106000939837 |
| constant_neighbor | jitter_10 | 48 | 10 | 0.018268203812302358 | 7.307281524920942 |
| constant_neighbor | jitter_10 | 64 | 10 | 0.018264506082900894 | 7.305802433160357 |
| increasing_neighbor | regular | 16 | 1 | 0.0004157504550326525 | 0.166300182013061 |
| increasing_neighbor | regular | 24 | 1 | 0.00017698581884511235 | 0.07079432753804495 |
| increasing_neighbor | regular | 32 | 1 | 8.83203509945464e-05 | 0.03532814039781856 |
| increasing_neighbor | regular | 48 | 1 | 4.401800624208924e-05 | 0.017607202496835696 |
| increasing_neighbor | regular | 64 | 1 | 2.4790505465340765e-05 | 0.009916202186136307 |
| increasing_neighbor | jitter_05 | 16 | 10 | 0.009005020750832815 | 3.602008300333126 |
| increasing_neighbor | jitter_05 | 24 | 10 | 0.007128984335830433 | 2.851593734332173 |
| increasing_neighbor | jitter_05 | 32 | 10 | 0.005886035798919998 | 2.3544143195679994 |
| increasing_neighbor | jitter_05 | 48 | 10 | 0.004817895260436067 | 1.9271581041744266 |
| increasing_neighbor | jitter_05 | 64 | 10 | 0.004063796389833455 | 1.6255185559333822 |
| increasing_neighbor | jitter_10 | 16 | 10 | 0.01798279353974911 | 7.193117415899644 |
| increasing_neighbor | jitter_10 | 24 | 10 | 0.014249253343783333 | 5.699701337513333 |
| increasing_neighbor | jitter_10 | 32 | 10 | 0.011767048374690215 | 4.706819349876086 |
| increasing_neighbor | jitter_10 | 48 | 10 | 0.009633055447238545 | 3.853222178895418 |
| increasing_neighbor | jitter_10 | 64 | 10 | 0.008124612658002305 | 3.2498450632009224 |

完整 210-case 逐种子值位于 `results/initial_residual_matrix.csv`，其中同时保存 `analytic_pressure_rms`；其范围为 `0.249315–0.250776`，中位数为 `0.250005`。EOS pressure noise 是 kernel-sum density 偏差经 `c_s^2` 放大的结果；其与解析 TGV pressure 的差异是初始化/模型形式项，不等同于 pair operator residual。
