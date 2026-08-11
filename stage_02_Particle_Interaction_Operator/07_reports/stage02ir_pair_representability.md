# Stage 02I-R Pair Representability

## General antisymmetric vector-pair gate

For nodal force `y_i = m_i Delta a_i`, the audit builds the incidence operator of the frozen reciprocal graph and solves `B f = y`, with pair antisymmetry imposed by edge orientation. This is the linear-momentum compatibility hard gate. No least-squares result is written back to a target.

| candidate | general exact | normalized projection residual | central exact | central normalized residual | torque residual |
|---|---:|---:|---:|---:|---:|
| i_res_n12_h26_regular | PASS | 1.108e-15 | PASS | 3.015e-14 | -1.827e-17 |
| i_anchor_n16_h26_regular | PASS | 2.099e-15 | PASS | 8.388e-14 | 2.939e-17 |
| i_res_n20_h26_regular | PASS | 3.657e-15 | PASS | 1.711e-13 | 9.769e-17 |
| i_sup_n16_h22_regular | PASS | 3.425e-15 | PASS | 7.602e-13 | 1.739e-16 |
| i_sup_n16_h30_regular | PASS | 1.673e-15 | PASS | 1.183e-13 | 2.122e-16 |
| i_dis_n16_h26_jitter05 | FAIL | 3.23544e-3 | FAIL | 3.23544e-3 | -7.072e-9 |
| i_dis_n16_h26_jitter10 | FAIL | 9.61310e-3 | FAIL | 9.61310e-3 | 1.886e-7 |

All graphs are connected. For the N=16 graph, the vector incidence rank is 510 with null-space dimension 4610 across 2560 undirected edge-vector unknowns. The connected-graph obstruction is the non-zero nodal-force sum, so the jitter targets are not exactly representable by any antisymmetric vector pair force.

## Central-force diagnostic

The central constraint `f_ij parallel r_ij` is evaluated separately. It is not a hard gate in Stage 02I-R. All five regular cases remain solvable within tolerance. For each jitter case, its residual equals the general-pair residual to numerical precision because the zero-sum obstruction is already limiting. Periodic torque is reported under the wrapped-position/minimum-image convention and is not used to override the linear-momentum gate.

## Explicit jitter decomposition

The least-squares analysis retains `y = y_pair + y_node` without replacement of `y`:

| candidate | `||y||` | `||y_pair||` | `||y_node||` | `||y_node||/||y||` | node/reference-difference ratio |
|---|---:|---:|---:|---:|---:|
| jitter05 | 3.148491e-3 | 3.148475e-3 | 1.018676e-5 | 3.23544e-3 | 5.92993e9 |
| jitter10 | 5.906919e-3 | 5.906646e-3 | 5.678379e-5 | 9.61310e-3 | 5.29308e10 |

Full per-particle spatial distributions and discrete Fourier signatures of `y_pair` and `y_node` are retained in `jitter_pair_node_decomposition.json`. The node magnitude is nearly uniform for the connected incidence projection; correlations with zeroth defect, first moment, and anisotropy are weak. Crucially, both node residuals are many orders above the Fourier/analytic reference difference.

`y_pair` is an audit-only projection. `projection_written_back_to_target=false` for every case, and `original_target_replaced=false` globally.

