# Stage 02J-T Statistical Calibration

The audit evaluated six development resolution cases, five controls, 512 preregistered realizations per case/control, and 256 case-hashed permutations per realization. Seeds follow the exact frozen SHA-256 construction and were not screened or replaced.

| Case | Control | Joint FP | Raw rate | One-sided 95% CP upper | Status |
|---|---|---:|---:|---:|---|
| crossmode_a_n12_h26 | FULL_PARTICLE_PERMUTATION | 0/512 | 0.000000 | 0.005834 | PASS |
| crossmode_a_n12_h26 | GAUSSIAN_WHITE_MATCHED_RMS | 0/512 | 0.000000 | 0.005834 | PASS |
| crossmode_a_n12_h26 | INDEPENDENT_COMPONENT_PERMUTATION | 0/512 | 0.000000 | 0.005834 | PASS |
| crossmode_a_n12_h26 | NYQUIST_CHECKERBOARD_MATCHED_RMS | 0/512 | 0.000000 | 0.005834 | PASS |
| crossmode_a_n12_h26 | RANDOM_PARTICLE_SIGN_FLIP | 0/512 | 0.000000 | 0.005834 | PASS |
| crossmode_a_n16_h26 | FULL_PARTICLE_PERMUTATION | 0/512 | 0.000000 | 0.005834 | PASS |
| crossmode_a_n16_h26 | GAUSSIAN_WHITE_MATCHED_RMS | 0/512 | 0.000000 | 0.005834 | PASS |
| crossmode_a_n16_h26 | INDEPENDENT_COMPONENT_PERMUTATION | 0/512 | 0.000000 | 0.005834 | PASS |
| crossmode_a_n16_h26 | NYQUIST_CHECKERBOARD_MATCHED_RMS | 0/512 | 0.000000 | 0.005834 | PASS |
| crossmode_a_n16_h26 | RANDOM_PARTICLE_SIGN_FLIP | 2/512 | 0.003906 | 0.012245 | PASS |
| crossmode_a_n20_h26 | FULL_PARTICLE_PERMUTATION | 0/512 | 0.000000 | 0.005834 | PASS |
| crossmode_a_n20_h26 | GAUSSIAN_WHITE_MATCHED_RMS | 0/512 | 0.000000 | 0.005834 | PASS |
| crossmode_a_n20_h26 | INDEPENDENT_COMPONENT_PERMUTATION | 0/512 | 0.000000 | 0.005834 | PASS |
| crossmode_a_n20_h26 | NYQUIST_CHECKERBOARD_MATCHED_RMS | 0/512 | 0.000000 | 0.005834 | PASS |
| crossmode_a_n20_h26 | RANDOM_PARTICLE_SIGN_FLIP | 0/512 | 0.000000 | 0.005834 | PASS |
| i_anchor_n16_h26_regular | FULL_PARTICLE_PERMUTATION | 0/512 | 0.000000 | 0.005834 | PASS |
| i_anchor_n16_h26_regular | GAUSSIAN_WHITE_MATCHED_RMS | 0/512 | 0.000000 | 0.005834 | PASS |
| i_anchor_n16_h26_regular | INDEPENDENT_COMPONENT_PERMUTATION | 0/512 | 0.000000 | 0.005834 | PASS |
| i_anchor_n16_h26_regular | NYQUIST_CHECKERBOARD_MATCHED_RMS | 0/512 | 0.000000 | 0.005834 | PASS |
| i_anchor_n16_h26_regular | RANDOM_PARTICLE_SIGN_FLIP | 2/512 | 0.003906 | 0.012245 | PASS |
| i_res_n12_h26_regular | FULL_PARTICLE_PERMUTATION | 0/512 | 0.000000 | 0.005834 | PASS |
| i_res_n12_h26_regular | GAUSSIAN_WHITE_MATCHED_RMS | 0/512 | 0.000000 | 0.005834 | PASS |
| i_res_n12_h26_regular | INDEPENDENT_COMPONENT_PERMUTATION | 0/512 | 0.000000 | 0.005834 | PASS |
| i_res_n12_h26_regular | NYQUIST_CHECKERBOARD_MATCHED_RMS | 0/512 | 0.000000 | 0.005834 | PASS |
| i_res_n12_h26_regular | RANDOM_PARTICLE_SIGN_FLIP | 7/512 | 0.013672 | 0.025526 | PASS |
| i_res_n20_h26_regular | FULL_PARTICLE_PERMUTATION | 0/512 | 0.000000 | 0.005834 | PASS |
| i_res_n20_h26_regular | GAUSSIAN_WHITE_MATCHED_RMS | 0/512 | 0.000000 | 0.005834 | PASS |
| i_res_n20_h26_regular | INDEPENDENT_COMPONENT_PERMUTATION | 0/512 | 0.000000 | 0.005834 | PASS |
| i_res_n20_h26_regular | NYQUIST_CHECKERBOARD_MATCHED_RMS | 0/512 | 0.000000 | 0.005834 | PASS |
| i_res_n20_h26_regular | RANDOM_PARTICLE_SIGN_FLIP | 0/512 | 0.000000 | 0.005834 | PASS |

All 30 case/control combinations pass the required `Clopper–Pearson upper <= 0.05` gate. The largest upper bound is `0.025525872900` (PV N12, RANDOM_PARTICLE_SIGN_FLIP, 7/512). Raw rate alone was not used as the qualification gate.
