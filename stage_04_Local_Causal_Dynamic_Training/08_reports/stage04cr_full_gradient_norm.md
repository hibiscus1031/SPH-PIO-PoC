# Stage 04C-R Full Gradient Norms

Two complete reverse executions produced 864 arm/group/context rows and 2,592 component gradients. Deterministic-repeat failures: 0; parameter hash changes: 0. Each row retains L2, RMS, Linf, exact nonzero/finite counts, sign balance and decade histogram. No optimizer was instantiated.

| Arm | Component | Min L2 | Median L2 | Max L2 | L2≥1e-14 | Rows |
|---|---|---|---|---|---|---|
| D1 | L_x | 4.248e-19 | 2.471e-17 | 6.962e-16 | 0 | 144 |
| D1 | L_v | 1.385e-14 | 6.169e-12 | 1.770e-10 | 144 | 144 |
| D1 | L_rho | 8.144e-23 | 2.085e-14 | 1.655e-12 | 89 | 144 |
| D2 | L_x | 2.390e-20 | 1.279e-17 | 7.294e-16 | 0 | 216 |
| D2 | L_v | 1.541e-13 | 3.696e-12 | 1.870e-10 | 216 | 216 |
| D2 | L_rho | 6.519e-23 | 1.108e-14 | 1.729e-12 | 120 | 216 |
| D3 | L_x | 1.368e-21 | 2.649e-17 | 1.182e-15 | 0 | 504 |
| D3 | L_v | 4.688e-16 | 7.027e-12 | 3.006e-10 | 468 | 504 |
| D3 | L_rho | 1.109e-24 | 1.465e-14 | 2.777e-12 | 258 | 504 |

Full gradients are component-dependent: position gradients are generally below 1e−14, velocity gradients are often above 1e−12, and density gradients cluster near the detectability boundary. Thus “all parameters are dead” is contradicted.
