# Stage 01F5B main time requalification

The primary temporal error is the vector difference `q_RK2 - q_semidiscrete`, evaluated for position and velocity with endpoint vector-L2 and 16-time integrated vector-RMS norms.

| Dataset | MMS | Combination | fitted p | fine local median | fine time/platform | total/platform distance |
|---|---|---|---:|---:|---:|---:|
| main | MMS_A | position_endpoint | 1.9920475 | 1.9968622 | 7.3610472e-06 | 7.3610393e-06 |
| main | MMS_A | position_integrated | 1.986433 | 1.9945476 | 7.6356116e-06 | 7.6316774e-06 |
| main | MMS_A | velocity_endpoint | 2.0475093 | 2.0211073 | 1.9223496e-06 | 1.9223346e-06 |
| main | MMS_A | velocity_integrated | 2.0218358 | 2.0094689 | 2.9500574e-06 | 2.8765917e-06 |
| main | MMS_B | position_endpoint | 1.9847637 | 1.993753 | 2.0141895e-05 | 7.3915142e-06 |
| main | MMS_B | position_integrated | 1.9790369 | 1.9914213 | 2.078525e-05 | 7.6470637e-06 |
| main | MMS_B | velocity_endpoint | 2.0165426 | 2.0072156 | 1.6367171e-05 | 2.0108045e-06 |
| main | MMS_B | velocity_integrated | 2.0112137 | 2.0048639 | 1.799492e-05 | 2.9034171e-06 |

| Gate | Result |
|---|---|
| T1 | PASS |
| T2 | PASS |
| T3 | PASS |
| T4 | PASS |
| T5 | PASS |
