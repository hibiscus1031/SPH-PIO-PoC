# Stage 02J Jitter OOD Registry

The two Stage 02I jitter records are registered read-only with role `distribution_shift_diagnostic_only`.

| case | L2 amplification vs regular anchor | Linf amplification | conservation residual | node/y | zeroth defect RMS | minimum isotropy |
|---|---:|---:|---:|---:|---:|---:|
| jitter05 | 1.602 | 3.859 | 3.7199e-3 | 3.2354e-3 | 1.3402e-2 | 0.9211 |
| jitter10 | 3.005 | 8.583 | 1.2002e-2 | 9.6131e-3 | 2.7888e-2 | 0.8561 |

The registry preserves each original target hash, `node_residual_only` classification, particle-quadrature contamination reason, L2/Linf amplification, conservation residual, node residual, geometry metrics, and Fourier/analytic reference uncertainty.

For both records:

- `training_label_permitted=false`;
- `normalization_fit_permitted=false`;
- `pair_force_supervision_permitted=false`;
- `split_membership=none`;
- `target_modified=false`;
- `conservation_projection_used=false`.

The registry does not claim that jitter has been repaired.

