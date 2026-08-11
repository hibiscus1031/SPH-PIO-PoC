# Stage 02I — Resolution Attribution

The primary path fixes regular layout and `H/dx=2.6`, then evaluates N12, N16, and N20. All refined thresholds and PCG64 seed 20260207 are read directly from the frozen Stage 02G contracts. The rejected cyclic-roll null is not used as an attribution gate.

| N | Target L2 RMS | Permuted-null ratio | Relative neighbor variation | Physical-gradient scale |
|---:|---:|---:|---:|---:|
| 12 | 5.768921e-2 | 0.6383 | 0.8984 | 6.0662 |
| 16 | 3.145011e-2 | 0.4876 | 0.6955 | 6.2609 |
| 20 | 1.876450e-2 | 0.3979 | 0.5647 | 6.3549 |

The high/low endpoint ratio is 0.3253. Adjacent low-mode direction cosines are 0.999978 and 0.999950. The physical-gradient-scale coefficient of variation is 0.01930. Target endpoint magnitude, direction, permuted-null ratio, strictly decreasing relative variation, and gradient-scale stability all pass.

`resolution trend = PASS`

No convergence order is computed or claimed.

Machine audit: `04_target_attribution/qualified_spatial_targets/attribution/resolution_attribution.json`.
