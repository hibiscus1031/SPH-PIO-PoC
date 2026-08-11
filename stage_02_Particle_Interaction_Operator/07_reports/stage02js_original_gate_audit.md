# Stage 02J-S Original Gate Audit

## v0.1 preservation and exact reproduction

The historical contract remains: one PCG64 particle permutation with seed `20260207`, graph-total-variation ratio, and threshold `ratio <= 0.8`. It is not corrected, deleted, or overwritten.

| Case | Reproduced ratio | v0.1 gate | Comparison |
|---|---:|---|---|
| crossmode_a_n12_h26 | 0.823610993618 | FAIL | exact |
| crossmode_a_n16_h22 | 0.519246748619 | PASS | computed; no archived ratio |
| crossmode_a_n16_h26 | 0.656964389634 | PASS | exact |
| crossmode_a_n16_h30 | 0.725735867170 | PASS | computed; no archived ratio |
| crossmode_a_n20_h26 | 0.549244132789 | PASS | exact |
| i_anchor_n16_h26_regular | 0.487646611470 | PASS | exact |
| i_res_n12_h26_regular | 0.638268176839 | PASS | exact |
| i_res_n20_h26_regular | 0.397925379374 | PASS | exact |
| i_sup_n16_h22_regular | 0.410667524074 | PASS | computed; no archived ratio |
| i_sup_n16_h30_regular | 0.531863624254 | PASS | computed; no archived ratio |

All six development rows with archived ratios reproduced with zero ratio and graph-TV drift. Four development support rows had no archived v0.1 ratio and were deterministically computed without inventing a historical comparison. The requested 20-case reproduction was not completed: DIAGONAL_B and MIXED_C remained sealed after the negative-control gate failed.

## Single-seed sensitivity

| Resolution case | Historical ratio | 256-ratio range | Historical percentile | fraction passing 0.8 |
|---|---:|---:|---:|---:|
| crossmode_a_n12_h26 | 0.823610993618 | 0.804668–0.853586 | 0.511719 | 0.000000 |
| crossmode_a_n16_h26 | 0.656964389634 | 0.646640–0.680370 | 0.210938 | 1.000000 |
| crossmode_a_n20_h26 | 0.549244132789 | 0.536082–0.558990 | 0.742188 | 1.000000 |
| i_anchor_n16_h26_regular | 0.487646611470 | 0.481103–0.501577 | 0.164062 | 1.000000 |
| i_res_n12_h26_regular | 0.638268176839 | 0.618554–0.650511 | 0.812500 | 1.000000 |
| i_res_n20_h26_regular | 0.397925379374 | 0.392819–0.404892 | 0.363281 | 1.000000 |

Within the development scope, the 256 preregistered case-hashed permutations did not reverse any resolution-case v0.1 verdict: CROSSMODE N12 failed for every null, while the other five resolution cases passed for every null. This demonstrates development-scope seed stability; it does not establish v0.1 necessity or sufficiency on sealed families.
