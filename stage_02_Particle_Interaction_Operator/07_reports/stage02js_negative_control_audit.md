# Stage 02J-S Negative-Control Audit

Five preregistered controls were evaluated for 64 fixed-seed realizations on each of six development resolution cases. A case/control false-positive rate above 0.05 fails the frozen operational rule.

| Control | Aggregate false positives | Aggregate rate | Maximum case rate | Status |
|---|---:|---:|---:|---|
| FULL_PARTICLE_PERMUTATION | 4/384 | 0.010417 | 0.031250 | PASS |
| INDEPENDENT_COMPONENT_PERMUTATION | 1/384 | 0.002604 | 0.015625 | PASS |
| RANDOM_PARTICLE_SIGN_FLIP | 14/384 | 0.036458 | 0.078125 | FAIL |
| NYQUIST_CHECKERBOARD_MATCHED_RMS | 0/384 | 0.000000 | 0.000000 | PASS |
| GAUSSIAN_WHITE_MATCHED_RMS | 1/384 | 0.002604 | 0.015625 | PASS |

Failed case/control combinations:

| Case | Control | False positives | Rate |
|---|---|---:|---:|
| i_anchor_n16_h26_regular | RANDOM_PARTICLE_SIGN_FLIP | 5/64 | 0.078125 |
| crossmode_a_n12_h26 | RANDOM_PARTICLE_SIGN_FLIP | 4/64 | 0.062500 |

Although the RANDOM_PARTICLE_SIGN_FLIP aggregate rate is 0.036458, two preregistered case rates exceed 0.05. The threshold, seeds, controls, and aggregation records were not modified after observation. Therefore negative-control discrimination is `FAIL`, and the held-out gate remains closed.
