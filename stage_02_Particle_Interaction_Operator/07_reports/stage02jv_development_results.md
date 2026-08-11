# Stage 02J-V Development Results

| Case | p_mag | p_dir | p_any | Real-target gate |
|---|---:|---:|---:|---|
| crossmode_a_n12_h26 | 0.778210116732 | 0.003891050584 | 0.007782101167 | PASS |
| crossmode_a_n16_h26 | 0.003891050584 | 0.003891050584 | 0.007782101167 | PASS |
| crossmode_a_n20_h26 | 0.003891050584 | 0.003891050584 | 0.007782101167 | PASS |
| i_anchor_n16_h26_regular | 0.003891050584 | 0.003891050584 | 0.007782101167 | PASS |
| i_res_n12_h26_regular | 0.003891050584 | 0.003891050584 | 0.007782101167 | PASS |
| i_res_n20_h26_regular | 0.003891050584 | 0.003891050584 | 0.007782101167 | PASS |

All six development real targets passed `p_any<=0.01` and the four frozen non-null gates.

| Family | M applicability | M slope | D applicability | D slope | Result |
|---|---|---:|---|---:|---|
| FAMILY_PV_EXISTING | HARD | -0.042582248653 | HARD | -0.115510085779 | PASS |
| FAMILY_CROSSMODE_A | DIAGNOSTIC | -0.006693554195 | HARD | -0.177224442754 | PASS |

For CROSSMODE_A, low-resolution magnitude is non-significant (`p_mag=0.778210116732`), so M refinement is diagnostic; direction is significant and its endpoint/slope refinement passes. No convergence order is claimed.
