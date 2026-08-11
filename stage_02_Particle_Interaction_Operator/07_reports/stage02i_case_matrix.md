# Stage 02I — Preregistered Case Matrix

The matrix was frozen before target evaluation and contains exactly seven unique cases. Case deletion, replacement, or favorable additions after observing results are prohibited.

| Case | N | H/dx | Layout | Path membership | Seed | Stage 02H scope |
|---|---:|---:|---|---|---:|---|
| `i_res_n12_h26_regular` | 12 | 2.6 | regular | resolution | 120026 | covered |
| `i_anchor_n16_h26_regular` | 16 | 2.6 | regular | resolution/support/disorder | 160026 | covered |
| `i_res_n20_h26_regular` | 20 | 2.6 | regular | resolution | 200026 | covered |
| `i_sup_n16_h22_regular` | 16 | 2.2 | regular | support | 160026 | extension required |
| `i_sup_n16_h30_regular` | 16 | 3.0 | regular | support | 160026 | extension required |
| `i_dis_n16_h26_jitter05` | 16 | 2.6 | jitter-5% | disorder | 314159 | extension required |
| `i_dis_n16_h26_jitter10` | 16 | 2.6 | jitter-10% | disorder | 161803 | extension required |

The jitter seeds are read directly from the frozen Stage 02H candidate matrix. All cases use the analytic periodic-vortex state at \(t=0\), a 2D periodic unit domain, and CPU float64 evaluation.

Preregistered matrix: `04_target_attribution/qualified_spatial_targets/case_matrix/preregistered_stage02i_case_matrix.yaml`.
