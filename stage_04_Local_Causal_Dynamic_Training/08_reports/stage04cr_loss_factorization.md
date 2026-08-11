# Stage 04C-R Loss Factorization

For every component and original parameter direction, `dL/dε = 2 mean(e·z)` was reconstructed against the historical reverse derivative. All 2,592 rows pass the frozen absolute ≤1e−12 or relative ≤1e−8 gate. Maximum absolute error: 5.493e-25; maximum relative error: 1.826e-08.

| Primary row reason | Count | Share |
|---|---|---|
| TASK_RESIDUAL_TOO_SMALL | 1316 | 50.8% |
| GROUP_DIRECTION_PROJECTION_DILUTION | 672 | 25.9% |
| UNRESOLVED | 604 | 23.3% |

These row-level unique reasons are heterogeneous, which is the direct evidence for the overall mixed/unresolved state.
