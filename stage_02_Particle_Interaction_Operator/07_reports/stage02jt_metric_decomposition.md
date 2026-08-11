# Stage 02J-T Metric Decomposition

The original v0.2 `S_h` was not redefined. For every active reciprocal undirected edge, the audit used `E_mag=(q_i-q_j)^2` and `E_dir=max(0, ||delta_i-delta_j||^2-E_mag)`, followed by the frozen distance and RMS normalization.

| Case | S_h | M_h | D_h | closure abs. error | Status |
|---|---:|---:|---:|---:|---|
| crossmode_a_n12_h26 | 0.848145202653 | 0.399753799232 | 0.748028866276 | 0.000e+00 | PASS |
| crossmode_a_n16_h22 | 0.645788711572 | 0.378509884061 | 0.523233530713 | 0.000e+00 | PASS |
| crossmode_a_n16_h26 | 0.671032826313 | 0.414112673574 | 0.528011124480 | 0.000e+00 | PASS |
| crossmode_a_n16_h30 | 0.671032826313 | 0.414112673574 | 0.528011124480 | 0.000e+00 | PASS |
| crossmode_a_n20_h26 | 0.551529166095 | 0.386366690842 | 0.393579980769 | 0.000e+00 | PASS |
| i_anchor_n16_h26_regular | 0.494230389667 | 0.256990012269 | 0.422160883627 | 2.776e-17 | PASS |
| i_res_n12_h26_regular | 0.642568022969 | 0.303451905228 | 0.566401452466 | 1.665e-16 | PASS |
| i_res_n20_h26_regular | 0.400162462059 | 0.218287407922 | 0.335381280908 | 4.163e-17 | PASS |
| i_sup_n16_h22_regular | 0.500767971271 | 0.271169423948 | 0.420993710839 | 8.327e-17 | PASS |
| i_sup_n16_h30_regular | 0.494230389667 | 0.256990012269 | 0.422160883627 | 2.776e-17 | PASS |

All 10 development cases satisfy `S_h^2=M_h^2+D_h^2`. The maximum absolute closure error is `1.665e-16`, within the frozen float64 tolerance. The `max(0,·)` operation was used only on the edgewise roundoff residual.
