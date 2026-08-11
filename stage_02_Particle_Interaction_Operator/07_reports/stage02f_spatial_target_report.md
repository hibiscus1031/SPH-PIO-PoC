# Stage 02F — Spatial Target Report

## Frozen target

The Stage 02F target is

\[
\Delta a_{space}=a_{R2S}-a_{SPH},
\]

with sign convention `a_R2S_minus_a_SPH`. Every record contains the state, physical-configuration, and neighbor-graph hashes together with its resolution and support identities. The same hash is recorded independently on both sides of each same-state/same-graph comparison.

## Controlled candidate materialization

Five unique audit candidates were evaluated at \(t=0\). These are target-attribution records and are explicitly not a training dataset.

| Candidate | Resolution | H/dx | Membership | Target L2 RMS | Target Linf |
|---|---:|---:|---|---:|---:|
| `f_res_n6_h26` | 6×6 | 2.6 | resolution | 1.615859e-2 | 1.982105e-2 |
| `f_anchor_n8_h26` | 8×8 | 2.6 | resolution, support | 1.010872e-2 | 1.255734e-2 |
| `f_res_n10_h26` | 10×10 | 2.6 | resolution | 5.847118e-3 | 8.094674e-3 |
| `f_sup_n8_h22` | 8×8 | 2.2 | support | 3.752528e-2 | 4.613216e-2 |
| `f_sup_n8_h30` | 8×8 | 3.0 | support | 1.010872e-2 | 1.255734e-2 |

All five targets are nonzero. No small or zero target was deleted; the machine-readable records retain all particle positions and all vectors for `a_SPH`, `a_R2S`, and `delta_a_space`.

## Spatial distribution audit

For every candidate, the audit records the particlewise target vector, particle-vector \(L_2\) RMS, particle-vector \(L_\infty\), component means, graph total variation, a frozen cyclic-null total variation, and a low-mode Fourier signature. The target magnitude falls across the fixed-support resolution path and its Fourier direction remains consistent, but the frozen smoothness-ratio threshold is not met. Consequently, spatial targets exist but attribution is not upgraded.

The full candidate artifact is `04_target_attribution/spatial_target/spatial_target_candidates.json`. No dataset, split assignment, normalization statistic, or training label was created.
