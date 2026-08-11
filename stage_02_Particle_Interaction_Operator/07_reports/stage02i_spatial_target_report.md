# Stage 02I — Spatial Target Inventory

All seven preregistered targets use `a_reference_minus_a_sph`. Each record contains state/configuration/graph and reference hashes; resolution, support, and disorder identities; all three acceleration fields; primary and secondary targets; reference difference; magnitude statistics and quantiles; graph total variation; Fourier signature; topology; and deterministic-repeat evidence.

| Candidate | N | H/dx | Disorder | Primary target L2 RMS | Linf | Graph TV RMS |
|---|---:|---:|---|---:|---:|---:|
| `i_res_n12_h26_regular` | 12 | 2.6 | regular | 5.768921e-2 | 7.655933e-2 | 5.183060e-2 |
| `i_anchor_n16_h26_regular` | 16 | 2.6 | regular | 3.145011e-2 | 4.306750e-2 | 2.187227e-2 |
| `i_res_n20_h26_regular` | 20 | 2.6 | regular | 1.876450e-2 | 2.612221e-2 | 1.059666e-2 |
| `i_sup_n16_h22_regular` | 16 | 2.2 | regular | 7.029424e-2 | 9.592735e-2 | 4.120782e-2 |
| `i_sup_n16_h30_regular` | 16 | 3.0 | regular | 3.145011e-2 | 4.306750e-2 | 2.373913e-2 |
| `i_dis_n16_h26_jitter05` | 16 | 2.6 | jitter-5% | 5.037586e-2 | 1.662013e-1 | 6.208904e-2 |
| `i_dis_n16_h26_jitter10` | 16 | 2.6 | jitter-10% | 9.451070e-2 | 3.696447e-1 | 1.313572e-1 |

No zero, small, nonmonotone, or direction-inconsistent target was deleted. These records are controlled target candidates, not a materialized dataset. Their training eligibility is uniformly `not_yet_evaluated`.

Machine inventory: `04_target_attribution/qualified_spatial_targets/targets/spatial_target_candidates.json`.
