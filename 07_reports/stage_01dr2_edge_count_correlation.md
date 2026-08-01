# Stage 01D-R2 Edge-count Correlation

## 模型与阈值

对每个 D run 拟合冻结模型：

`live_tensor_bytes = beta0 + beta_edge * edge_count + beta_step * step`

`unknown_live_bytes = gamma0 + gamma_edge * edge_count + gamma_step * step`

估计器为 Huber IRLS；每个模型使用 `500`
次预登记 bootstrap。β_step 近零上限为
`4096.0` B/step，
γ_step 上限为 `1024.0`
B/step，且两者 95% CI 均须包含 0。

## 结果

| run | β_edge B/edge | β_step B/step | β_step 95% CI | γ_step B/step | γ_step 95% CI | PASS |
|---|---|---|---|---|---|---|
| stage01dr2_d_r1 | 48.000000 | 0.000000 | [-0.000000, 0.000000] | 0.000000 | [0.000000, 0.000000] | True |
| stage01dr2_d_r2 | 48.000000 | 0.000000 | [-0.000000, 0.000000] | 0.000000 | [0.000000, 0.000000] | True |
| stage01dr2_d_r3 | 48.000000 | 0.000000 | [-0.000000, 0.000000] | 0.000000 | [0.000000, 0.000000] | True |
| stage01dr2_d_confirm_2000 | 48.000000 | 0.000000 | [-0.000000, 0.000000] | 0.000000 | [0.000000, 0.000000] | True |

该多变量判定不会把 total live bytes 对 step 的一元正相关直接解释为 retention。
