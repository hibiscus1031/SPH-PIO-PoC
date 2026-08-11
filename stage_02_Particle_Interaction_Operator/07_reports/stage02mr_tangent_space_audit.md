# Stage 02M-R — Tangent-space audit

K0/K1/K2 × 3 seeds × initialization/selected 共 18 点完成。whole-network 使用 matrix-free JVP/VJP/LSQR，固定 `atol=btol=1e-8`、30 iterations；final head 仅显式形成至多 66 列的小 Jacobian。所有点无 parameter writeback、无新 checkpoint、无 validation/test target。

| architecture | seed | selected whole-network Q | selected head-only Q | classification |
|---|---:|---:|---:|---|
| K0 | 20261201 | 0.385774 | 0.196081 | HEAD_OPTIMIZATION_GAP |
| K0 | 20261202 | 0.325650 | 0.286579 | WHOLE_NETWORK_NONLINEAR_OR_UNRESOLVED |
| K0 | 20261203 | 0.354228 | 0.187969 | HEAD_OPTIMIZATION_GAP |
| K1 | 20261201 | 0.591960 | 0.159343 | HEAD_OPTIMIZATION_GAP |
| K1 | 20261202 | 0.595810 | 0.271999 | WHOLE_NETWORK_NONLINEAR_OR_UNRESOLVED |
| K1 | 20261203 | 0.595075 | 0.158108 | HEAD_OPTIMIZATION_GAP |
| K2 | 20261201 | 0.645921 | 0.628281 | WHOLE_NETWORK_NONLINEAR_OR_UNRESOLVED |
| K2 | 20261202 | 0.551789 | 0.516646 | WHOLE_NETWORK_NONLINEAR_OR_UNRESOLVED |
| K2 | 20261203 | 0.703381 | 0.576372 | WHOLE_NETWORK_NONLINEAR_OR_UNRESOLVED |

K1 selected 的 20261201 与 20261203 在 head-only 局部投影分别达到 0.159343 和 0.158108，满足门槛，而历史 K1 train gate 为 0/3，构成 `HEAD_OPTIMIZATION_GAP` 支持。K2 各点未达到 0.25，不能由本审计推出相对架构优劣。whole-network LSQR 在冻结 iteration limit 内未收敛到已知 head-only 可行子空间，因此其 Q 是迭代受限上界，而非函数类不可达下界。
