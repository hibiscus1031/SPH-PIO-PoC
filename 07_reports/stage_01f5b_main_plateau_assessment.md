# Stage 01F5B main plateau assessment

`e_total = e_space + e_time`; therefore `||e_total||² = ||e_space||² + ||e_time||² + 2<e_space,e_time>`. Cross-term sign and platform-approach direction are diagnostics, not gates.

| MMS | dt | combination | cross term | cosine | reconstruction residual | approach |
|---|---:|---|---:|---:|---:|---|
| MMS_A | 0.001 | position-endpoint | 5.8981858e-12 | 0.99999875 | 1.06e-25 | above |
| MMS_A | 0.001 | position-integrated | 1.4088494e-12 | 0.99986294 | 4.04e-26 | above |
| MMS_A | 0.001 | velocity-endpoint | 2.4587869e-08 | 0.99999614 | 3.92e-21 | above |
| MMS_A | 0.001 | velocity-integrated | 1.4484049e-08 | 0.98183676 | 1.13e-21 | above |
| MMS_A | 0.0005 | position-endpoint | 1.4934488e-12 | 0.99999885 | 1.09e-25 | above |
| MMS_A | 0.0005 | position-integrated | 3.5979722e-13 | 0.99971174 | 1.65e-26 | above |
| MMS_A | 0.0005 | velocity-endpoint | 5.7333716e-09 | 0.99999436 | 1.34e-21 | above |
| MMS_A | 0.0005 | velocity-integrated | 3.4928871e-09 | 0.97849733 | 3.46e-22 | above |
| MMS_A | 0.00025 | position-endpoint | 3.7561322e-13 | 0.9999989 | 3.91e-26 | above |
| MMS_A | 0.00025 | position-integrated | 9.0871234e-14 | 0.99959222 | 6.8e-26 | above |
| MMS_A | 0.00025 | velocity-endpoint | 1.3807719e-09 | 0.9999932 | 3.1e-21 | above |
| MMS_A | 0.00025 | velocity-integrated | 8.5680838e-10 | 0.97661422 | 1.49e-21 | above |
| MMS_A | 0.000125 | position-endpoint | 9.4177441e-14 | 0.99999892 | 2.59e-27 | above |
| MMS_A | 0.000125 | position-integrated | 2.2831363e-14 | 0.99952222 | 6.31e-27 | above |
| MMS_A | 0.000125 | velocity-endpoint | 3.3856591e-10 | 0.99999254 | 4.56e-21 | above |
| MMS_A | 0.000125 | velocity-integrated | 2.121251e-10 | 0.9756131 | 1.05e-21 | above |
| MMS_A | 6.25e-05 | position-endpoint | 2.3578167e-14 | 0.99999893 | 4.06e-26 | above |
| MMS_A | 6.25e-05 | position-integrated | 5.7219285e-15 | 0.99948475 | 5.25e-26 | above |
| MMS_A | 6.25e-05 | velocity-endpoint | 8.3809576e-11 | 0.99999219 | 2.1e-21 | above |
| MMS_A | 6.25e-05 | velocity-integrated | 5.2770054e-11 | 0.97509679 | 4.13e-23 | above |
| MMS_B | 0.001 | position-endpoint | 5.9326766e-12 | 0.37476504 | 8.24e-26 | above |
| MMS_B | 0.001 | position-integrated | 1.4141608e-12 | 0.37606424 | 3.45e-26 | above |
| MMS_B | 0.001 | velocity-endpoint | 2.5669991e-08 | 0.1336742 | 4.07e-21 | above |
| MMS_B | 0.001 | velocity-integrated | 1.4639677e-08 | 0.16742726 | 1.7e-22 | above |
| MMS_B | 0.0005 | position-endpoint | 1.5021342e-12 | 0.37064982 | 1.48e-25 | above |
| MMS_B | 0.0005 | position-integrated | 3.6110555e-13 | 0.37174482 | 1e-25 | above |
| MMS_B | 0.0005 | velocity-endpoint | 5.9984535e-09 | 0.12805865 | 4.32e-21 | above |
| MMS_B | 0.0005 | velocity-integrated | 3.5311135e-09 | 0.16426428 | 5.83e-22 | above |
| MMS_B | 0.00025 | position-endpoint | 3.7779205e-13 | 0.36855238 | 1.82e-25 | above |
| MMS_B | 0.00025 | position-integrated | 9.1195783e-14 | 0.36955438 | 4.07e-26 | above |
| MMS_B | 0.00025 | velocity-endpoint | 1.446335e-09 | 0.12511676 | 5.29e-21 | above |
| MMS_B | 0.00025 | velocity-integrated | 8.6627619e-10 | 0.16261044 | 8.83e-22 | above |
| MMS_B | 0.000125 | position-endpoint | 9.472306e-14 | 0.36749448 | 2.87e-25 | above |
| MMS_B | 0.000125 | position-integrated | 2.2912177e-14 | 0.36845201 | 3.17e-26 | above |
| MMS_B | 0.000125 | velocity-endpoint | 3.5486656e-10 | 0.12361035 | 2.86e-21 | above |
| MMS_B | 0.000125 | velocity-integrated | 2.1448072e-10 | 0.16176511 | 7.02e-22 | above |
| MMS_B | 6.25e-05 | position-endpoint | 2.3714689e-14 | 0.36696343 | 4.13e-25 | above |
| MMS_B | 6.25e-05 | position-integrated | 5.7420924e-15 | 0.36789921 | 2.06e-26 | above |
| MMS_B | 6.25e-05 | velocity-endpoint | 8.78733e-11 | 0.1228479 | 7.59e-23 | above |
| MMS_B | 6.25e-05 | velocity-integrated | 5.3357509e-11 | 0.16133772 | 1.68e-21 | above |

| Gate | Result |
|---|---|
| P1 | PASS |
| P2 | PASS |
| P3 | PASS |
