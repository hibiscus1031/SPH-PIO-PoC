# Stage 02G — Resolution Extension Design and Audit

## Frozen design

Before executing the extension, the resolution family was fixed as 12×12, 16×16, and 20×20. `H/dx=2.6`, the analytic periodic-vortex physical state at \(t=0\), cubic-spline kernel, smoothing length, EOS, strict support rule, and regular particle geometry were held fixed. Level removal and replacement after observing results were prohibited.

“Fixed physical state” denotes the same analytic field definition and timestamp sampled on each prescribed resolution, not reuse of an incompatible particle array across different N.

## Results

| Resolution | Target L2 RMS | Target Linf | R2S bias / target | Decorrelated-null ratio | Relative neighbor variation |
|---:|---:|---:|---:|---:|---:|
| 12×12 | 3.075490e-3 | 4.299987e-3 | 17.7664 | 0.6414 | 0.9039 |
| 16×16 | 4.608980e-4 | 7.433327e-4 | 68.4086 | 0.6980 | 1.0023 |
| 20×20 | 1.732677e-3 | 2.697818e-3 | 11.7850 | 0.4191 | 0.5936 |

The high-to-low endpoint target ratio is 0.5634 and passes the non-increasing endpoint test. The fixed-seed decorrelated-null ratios all pass the 0.8 limit. The physical-gradient scales are 6.1028, 9.0231, and 6.6795, giving a coefficient of variation of 0.1737, below the frozen 0.25 bound.

However, adjacent low-mode Fourier direction cosines are −0.0845 and 0.4339, below the frozen 0.95 requirement. Relative neighbor variation is not strictly decreasing, and the R2S bias-to-target bound fails. These failures are retained without changing N or any threshold.

## Resolution-trend status

`resolution trend = DIAGNOSTIC`

The path is structurally valid and supplies three preselected levels, but magnitude alone does not close attribution. No convergence order or performance claim is made.

Design and results: `04_target_attribution/resolution_extension/resolution_extension_matrix.yaml` and `04_target_attribution/resolution_extension/resolution_extension_results.json`.
