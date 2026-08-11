# Stage 02I — Support and Disorder Audit

## Support path

At fixed N16 regular layout, target L2 RMS values for `H/dx=2.2, 2.6, 3.0` are 0.07029, 0.03145, and 0.03145. Their maximum/minimum ratio is 2.2351, and adjacent direction cosines are 0.999946 and 1.000000. These pass the frozen Stage 02F support rules.

Kernel-active neighbors increase from 12 at `H/dx=2.2` to 20 at 2.6 and 3.0. The 3.0 graph includes four zero-kernel-weight exterior edges per particle, or 1024 directed edges total; these are recorded rather than silently removed. All topology and reference-agreement checks pass.

`support consistency = PASS`

## Disorder path

At fixed N16 and `H/dx=2.6`, relative to regular layout:

| Disorder | L2 amplification | Linf amplification | Reference-discrepancy amplification | Fourier direction cosine | Geometry isotropy minimum |
|---|---:|---:|---:|---:|---:|
| regular | 1.000 | 1.000 | 1.000 | 1.0000 | 1.0000 |
| jitter-5% | 1.602 | 3.859 | 2.261 | 0.9825 | 0.9211 |
| jitter-10% | 3.005 | 8.583 | 1.412 | 0.9601 | 0.8561 |

All disorder cases pass reference qualification, state/configuration alignment, topology, uncertainty, spatial-operator compatibility, and deterministic repetition. The amplification is retained as distribution-shift evidence; no post-hoc monotonic threshold is introduced.

Machine audits: `04_target_attribution/qualified_spatial_targets/attribution/support_attribution.json` and `disorder_audit.json`.
