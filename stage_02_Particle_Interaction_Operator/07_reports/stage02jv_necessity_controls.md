# Stage 02J-V Necessity Controls

## Necessity argument

A vector correction may be spatially identifiable through magnitude, direction, or both. Requiring simultaneous component significance is therefore not necessary. The sole prospective statistic was `p_any=min(1,2*min(p_mag,p_dir))`, with the factor 2 frozen before execution.

| Case | Control | p_mag | p_dir | p_any | Status |
|---|---|---:|---:|---:|---|
| i_res_n12_h26_regular | MAGNITUDE_ONLY_SMOOTH | 0.003891050584 | 1.000000000000 | 0.007782101167 | PASS |
| i_res_n12_h26_regular | DIRECTION_ONLY_SMOOTH | 0.003891050584 | 0.003891050584 | 0.007782101167 | PASS |
| i_res_n12_h26_regular | JOINT_SMOOTH | 0.003891050584 | 0.003891050584 | 0.007782101167 | PASS |
| i_res_n12_h26_regular | CONSTANT_VECTOR | 1.000000000000 | 1.000000000000 | 1.000000000000 | PASS |
| i_anchor_n16_h26_regular | MAGNITUDE_ONLY_SMOOTH | 0.003891050584 | 1.000000000000 | 0.007782101167 | PASS |
| i_anchor_n16_h26_regular | DIRECTION_ONLY_SMOOTH | 1.000000000000 | 0.003891050584 | 0.007782101167 | PASS |
| i_anchor_n16_h26_regular | JOINT_SMOOTH | 0.003891050584 | 0.003891050584 | 0.007782101167 | PASS |
| i_anchor_n16_h26_regular | CONSTANT_VECTOR | 1.000000000000 | 1.000000000000 | 1.000000000000 | PASS |
| i_res_n20_h26_regular | MAGNITUDE_ONLY_SMOOTH | 0.003891050584 | 1.000000000000 | 0.007782101167 | PASS |
| i_res_n20_h26_regular | DIRECTION_ONLY_SMOOTH | 0.003891050584 | 0.003891050584 | 0.007782101167 | PASS |
| i_res_n20_h26_regular | JOINT_SMOOTH | 0.003891050584 | 0.003891050584 | 0.007782101167 | PASS |
| i_res_n20_h26_regular | CONSTANT_VECTOR | 1.000000000000 | 1.000000000000 | 1.000000000000 | PASS |
| crossmode_a_n12_h26 | MAGNITUDE_ONLY_SMOOTH | 0.003891050584 | 1.000000000000 | 0.007782101167 | PASS |
| crossmode_a_n12_h26 | DIRECTION_ONLY_SMOOTH | 0.003891050584 | 0.003891050584 | 0.007782101167 | PASS |
| crossmode_a_n12_h26 | JOINT_SMOOTH | 0.003891050584 | 0.003891050584 | 0.007782101167 | PASS |
| crossmode_a_n12_h26 | CONSTANT_VECTOR | 1.000000000000 | 1.000000000000 | 1.000000000000 | PASS |
| crossmode_a_n16_h26 | MAGNITUDE_ONLY_SMOOTH | 0.003891050584 | 1.000000000000 | 0.007782101167 | PASS |
| crossmode_a_n16_h26 | DIRECTION_ONLY_SMOOTH | 0.003891050584 | 0.003891050584 | 0.007782101167 | PASS |
| crossmode_a_n16_h26 | JOINT_SMOOTH | 0.003891050584 | 0.003891050584 | 0.007782101167 | PASS |
| crossmode_a_n16_h26 | CONSTANT_VECTOR | 1.000000000000 | 1.000000000000 | 1.000000000000 | PASS |
| crossmode_a_n20_h26 | MAGNITUDE_ONLY_SMOOTH | 0.003891050584 | 1.000000000000 | 0.007782101167 | PASS |
| crossmode_a_n20_h26 | DIRECTION_ONLY_SMOOTH | 1.000000000000 | 0.003891050584 | 0.007782101167 | PASS |
| crossmode_a_n20_h26 | JOINT_SMOOTH | 0.003891050584 | 0.003891050584 | 0.007782101167 | PASS |
| crossmode_a_n20_h26 | CONSTANT_VECTOR | 1.000000000000 | 1.000000000000 | 1.000000000000 | PASS |

All 18 learnable positive-control cases passed. The six CONSTANT_VECTOR cases uniquely produced `M_h=D_h=0`, `p_mag=p_dir=p_any=1` and passed zero-variation handling; they were not treated as learnable corrections.

RANDOM_PARTICLE_SIGN_FLIP was retained as `DIRECTION_ABLATION_CONTROL`, not a hard negative: all 384/384 magnitude mappings were preserved, 320 realizations had `p_any<=0.01`, and none contributed to hard-negative false-positive counts.
