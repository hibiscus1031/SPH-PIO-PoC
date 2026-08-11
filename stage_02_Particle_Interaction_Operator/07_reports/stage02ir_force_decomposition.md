# Stage 02I-R Force Decomposition

## Definitions and method

For every frozen target and for pressure, viscosity, and total contributions, the audit computes

\[
F_{ref}=\sum_i m_i a_{ref,i},\qquad
F_{SPH}=\sum_i m_i a_{SPH,i},\qquad
F_{target}=\sum_i m_i\Delta a_i.
\]

It then verifies `F_target = F_ref - F_SPH`. All tabulated vectors below use float64 Kahan-compensated accumulation. Forward and reverse orders were also evaluated, and every compensated calculation repeated deterministically.

## Total-force results for all seven targets

| candidate | `F_ref` | `F_SPH` | `F_target` | `||F_target||` | normalized residual |
|---|---:|---:|---:|---:|---:|
| i_res_n12_h26_regular | (1.106e-17, 1.128e-17) | (9.758e-19, 2.060e-18) | (9.731e-18, 9.731e-18) | 1.376e-17 | 2.483e-16 |
| i_anchor_n16_h26_regular | (-3.740e-18, -6.614e-18) | (-8.403e-18, 4.554e-18) | (3.686e-18, -1.078e-17) | 1.139e-17 | 3.777e-16 |
| i_res_n20_h26_regular | (4.228e-18, 9.758e-19) | (-1.247e-18, -2.196e-18) | (5.839e-18, 2.253e-18) | 6.259e-18 | 3.481e-16 |
| i_sup_n16_h22_regular | (-3.740e-18, -6.614e-18) | (1.843e-18, -1.193e-18) | (-4.933e-18, -5.367e-18) | 7.290e-18 | 1.081e-16 |
| i_sup_n16_h30_regular | (-3.740e-18, -6.614e-18) | (-8.403e-18, 4.554e-18) | (3.686e-18, -1.078e-17) | 1.139e-17 | 3.777e-16 |
| i_dis_n16_h26_jitter05 | (1.021054e-4, -1.270418e-4) | (-4.987e-18, 1.030e-18) | (1.021054e-4, -1.270418e-4) | 1.629881e-4 | 3.719907e-3 |
| i_dis_n16_h26_jitter10 | (-6.877232e-4, -5.937028e-4) | (-1.334e-17, 2.819e-18) | (-6.877232e-4, -5.937028e-4) | 9.085407e-4 | 1.200237e-2 |

The five regular totals are at roundoff scale. The two jitter totals are finite and originate in `F_ref`, not in baseline `F_SPH`.

## Jitter pressure/viscosity/total decomposition

| candidate | component | `F_ref` | `F_SPH` | `F_target` | `||F_target||` | normalized residual |
|---|---|---:|---:|---:|---:|---:|
| jitter05 | pressure | (1.052257e-4, -1.243923e-4) | (-6.234e-18, 2.168e-19) | (1.052257e-4, -1.243923e-4) | 1.629291e-4 | 3.720178e-3 |
| jitter05 | viscosity | (-3.120279e-6, -2.649527e-6) | (8.809e-20, 5.760e-20) | (-3.120279e-6, -2.649527e-6) | 4.093426e-6 | 5.452967e-3 |
| jitter05 | total | (1.021054e-4, -1.270418e-4) | (-4.987e-18, 1.030e-18) | (1.021054e-4, -1.270418e-4) | 1.629881e-4 | 3.719907e-3 |
| jitter10 | pressure | (-6.723779e-4, -6.105816e-4) | (-1.323e-17, 1.952e-18) | (-6.723779e-4, -6.105816e-4) | 9.082412e-4 | 1.199582e-2 |
| jitter10 | viscosity | (-1.534522e-5, 1.687883e-5) | (-1.559e-19, 1.965e-19) | (-1.534522e-5, 1.687883e-5) | 2.281164e-5 | 1.710758e-2 |
| jitter10 | total | (-6.877232e-4, -5.937028e-4) | (-1.334e-17, 2.819e-18) | (-6.877232e-4, -5.937028e-4) | 9.085407e-4 | 1.200237e-2 |

## Numerical controls

All 21 component identities passed. Identity-closure norms are at or below `2.60e-18` for the jitter totals and at roundoff for regular cases. Maximum forward/reverse/Kahan order sensitivity in the jitter total targets is below `8.1e-19`. Repeated Kahan results are bitwise equal. Complete per-case vectors and order traces are retained in `force_decomposition.json`.

## Baseline SPH cancellation

Every case has reciprocal topology PASS with zero duplicate, missing reciprocal, omitted strict-support, or unexpected exterior edges. For pressure, viscosity, and total, the maximum `F_ij + F_ji` residual is exactly zero by the frozen algebraic construction. The global SPH normalized residuals are of order `1e-17`, below the Stage 01 limit `1e-10`. Therefore `SPH_PAIRWISE_CONSERVATION_FAILURE` is not triggered.

