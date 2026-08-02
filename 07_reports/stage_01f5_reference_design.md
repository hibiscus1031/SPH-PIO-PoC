# Stage 01F5 半离散参考设计

## 三层参考

主配置和 held-out 的 MMS-A/MMS-B 分别建立三层半离散参考。未来方法固定为 production sparse SPH RHS 与 `scipy.solve_ivp(method="DOP853")`；位置连续 unwrapped，仅在场量和邻域评价时 periodic wrap。项目 RK2 不得用于生成参考。

| level | rtol | atol | max_step |
|---|---:|---:|---:|
| baseline | `1e-12` | `1e-14` | `3.125e-5` |
| tighter | `1e-13` | `1e-15` | `1.5625e-5` |
| third | `1e-13` | `1e-15` | `7.8125e-6` |

## 资格要求

- 三层全部状态 finite。
- baseline/tighter 与 tighter/third 敏感性按字段、按共主范数分别评价。
- reference uncertainty 按字段和范数分别取匹配敏感性证据，不使用单一全局常数。
- 每个解至少抽查 10 个状态的 sparse/dense acceleration。
- reciprocal cutoff crossing 合法；不要求 edge identity 恒定。
- structural topology defects 必须为零。

## 主配置 reference IDs

- MMS-A：`f5_ref_main_a_baseline`、`f5_ref_main_a_tighter`、`f5_ref_main_a_third`。
- MMS-B：`f5_ref_main_b_baseline`、`f5_ref_main_b_tighter`、`f5_ref_main_b_third`。

## Held-out reference IDs

- MMS-A：`f5_ref_hold_a_baseline`、`f5_ref_hold_a_tighter`、`f5_ref_hold_a_third`。
- MMS-B：`f5_ref_hold_b_baseline`、`f5_ref_hold_b_tighter`、`f5_ref_hold_b_third`。

## MMS-B 空间连续参考

N16/N24/N32/N48 分别生成 baseline/tighter/third，合计 12 个独立未来 reference ID。它们必须分别完成 sensitivity；不得用 Stage 01F3B 的旧参考替代。
