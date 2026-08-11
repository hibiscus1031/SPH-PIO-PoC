# Stage 02J-V Hard-Negative Calibration

Each of 24 development case/control combinations used 512 preregistered realizations and 256 permutation nulls per realization. Seeds used the frozen `stage02jv || case || control || realization` SHA-256 rule without screening.

| Case | Hard negative | False positives | Raw rate | One-sided 95% CP upper | Status |
|---|---|---:|---:|---:|---|
| crossmode_a_n12_h26 | FULL_PARTICLE_PERMUTATION | 7/512 | 0.013672 | 0.025526 | PASS |
| crossmode_a_n12_h26 | GAUSSIAN_WHITE_MATCHED_RMS | 3/512 | 0.005859 | 0.015074 | PASS |
| crossmode_a_n12_h26 | INDEPENDENT_COMPONENT_PERMUTATION | 7/512 | 0.013672 | 0.025526 | PASS |
| crossmode_a_n12_h26 | NYQUIST_CHECKERBOARD_MATCHED_RMS | 0/512 | 0.000000 | 0.005834 | PASS |
| crossmode_a_n16_h26 | FULL_PARTICLE_PERMUTATION | 2/512 | 0.003906 | 0.012245 | PASS |
| crossmode_a_n16_h26 | GAUSSIAN_WHITE_MATCHED_RMS | 1/512 | 0.001953 | 0.009232 | PASS |
| crossmode_a_n16_h26 | INDEPENDENT_COMPONENT_PERMUTATION | 3/512 | 0.005859 | 0.015074 | PASS |
| crossmode_a_n16_h26 | NYQUIST_CHECKERBOARD_MATCHED_RMS | 0/512 | 0.000000 | 0.005834 | PASS |
| crossmode_a_n20_h26 | FULL_PARTICLE_PERMUTATION | 7/512 | 0.013672 | 0.025526 | PASS |
| crossmode_a_n20_h26 | GAUSSIAN_WHITE_MATCHED_RMS | 4/512 | 0.007812 | 0.017788 | PASS |
| crossmode_a_n20_h26 | INDEPENDENT_COMPONENT_PERMUTATION | 1/512 | 0.001953 | 0.009232 | PASS |
| crossmode_a_n20_h26 | NYQUIST_CHECKERBOARD_MATCHED_RMS | 0/512 | 0.000000 | 0.005834 | PASS |
| i_anchor_n16_h26_regular | FULL_PARTICLE_PERMUTATION | 2/512 | 0.003906 | 0.012245 | PASS |
| i_anchor_n16_h26_regular | GAUSSIAN_WHITE_MATCHED_RMS | 5/512 | 0.009766 | 0.020423 | PASS |
| i_anchor_n16_h26_regular | INDEPENDENT_COMPONENT_PERMUTATION | 4/512 | 0.007812 | 0.017788 | PASS |
| i_anchor_n16_h26_regular | NYQUIST_CHECKERBOARD_MATCHED_RMS | 0/512 | 0.000000 | 0.005834 | PASS |
| i_res_n12_h26_regular | FULL_PARTICLE_PERMUTATION | 2/512 | 0.003906 | 0.012245 | PASS |
| i_res_n12_h26_regular | GAUSSIAN_WHITE_MATCHED_RMS | 5/512 | 0.009766 | 0.020423 | PASS |
| i_res_n12_h26_regular | INDEPENDENT_COMPONENT_PERMUTATION | 2/512 | 0.003906 | 0.012245 | PASS |
| i_res_n12_h26_regular | NYQUIST_CHECKERBOARD_MATCHED_RMS | 0/512 | 0.000000 | 0.005834 | PASS |
| i_res_n20_h26_regular | FULL_PARTICLE_PERMUTATION | 7/512 | 0.013672 | 0.025526 | PASS |
| i_res_n20_h26_regular | GAUSSIAN_WHITE_MATCHED_RMS | 4/512 | 0.007812 | 0.017788 | PASS |
| i_res_n20_h26_regular | INDEPENDENT_COMPONENT_PERMUTATION | 5/512 | 0.009766 | 0.020423 | PASS |
| i_res_n20_h26_regular | NYQUIST_CHECKERBOARD_MATCHED_RMS | 0/512 | 0.000000 | 0.005834 | PASS |

All combinations pass `CP upper <= 0.05`; the maximum upper bound is `0.025525872900`. Sign flip was excluded from this false-positive rate exactly as preregistered.
