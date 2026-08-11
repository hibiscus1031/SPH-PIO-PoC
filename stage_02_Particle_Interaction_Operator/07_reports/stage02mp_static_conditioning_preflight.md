# Stage 02M-P — Static conditioning preflight

| run | scaled loss | epsilon-dominated fraction | major modules |
|---|---:|---:|---|
| K0_seed20261211 | 0.997940 | 0.049247 | PASS |
| K0_seed20261212 | 0.994185 | 0.050717 | PASS |
| K0_seed20261213 | 1.002933 | 0.049247 | PASS |
| K1_seed20261211 | 1.009960 | 0.049020 | PASS |
| K1_seed20261212 | 0.997913 | 0.049746 | PASS |
| K1_seed20261213 | 1.010004 | 0.048656 | PASS |
| K2_seed20261211 | 1.001404 | 0.080034 | PASS |
| K2_seed20261212 | 0.994837 | 0.057264 | PASS |
| K2_seed20261213 | 0.999526 | 0.085067 | PASS |

9/9 finite forward/backward通过。K1/K2 的 scaled loss范围 `0.994837`–`1.010004`，epsilon-dominated fraction范围 `0.048656`–`0.085067`，均满足预冻结门；weight-decay-dominated fraction=0，所有主要模块 finite nonzero gradient fraction≥0.10。参数 hash未变，optimizer/scheduler step为0。
