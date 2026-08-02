# Stage 01F3B MMS-A increasing-neighbor space matrix

The formal path uses `(N,H/dx)=(16,4.06155),(24,4.5),(32,5.04951),(48,5.5)` with frozen `dt_space=6.25e-5` and `t_final=0.02`. It is an increasing-neighbor consistency path, not fixed-stencil single-h refinement.

| N | position L2 | velocity L2 | density L2 | pressure L2 | edge count | topology events | peak RSS |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 8.6184e-5 | 6.8117e-3 | 4.0640e-4 | 1.6256e-1 | 12,544 | 0 | 282 MB |
| 24 | 4.8356e-5 | 3.6802e-3 | 2.0906e-4 | 8.3623e-2 | 39,744 | 0 | 335 MB |
| 32 | 3.4588e-5 | 2.5940e-3 | 1.1562e-4 | 4.6246e-2 | 82,944 | 0 | 406 MB |
| 48 | 1.8416e-5 | 1.3564e-3 | 6.3544e-5 | 2.5417e-2 | 223,488 | 0 | 607 MB |

All position, velocity, density and pressure errors decrease at every level. Global slopes are `1.389`, `1.453`, `1.713` and `1.713`, respectively. A-S1–A-S6: **PASS**. MMS-A maintained a constant topology identity as expected.

Full endpoint norms:

| N | pos L1 | pos L2 | pos Linf | vel L1 | vel L2 | vel Linf | rho L1 | rho L2 | rho Linf | p L1 | p L2 | p Linf |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 8.2668e-5 | 8.6184e-5 | 1.1753e-4 | 6.5338e-3 | 6.8117e-3 | 9.2885e-3 | 3.6629e-4 | 4.0640e-4 | 7.0193e-4 | 1.4652e-1 | 1.6256e-1 | 2.8077e-1 |
| 24 | 4.6345e-5 | 4.8356e-5 | 6.7303e-5 | 3.5272e-3 | 3.6802e-3 | 5.1208e-3 | 1.8035e-4 | 2.0906e-4 | 3.9297e-4 | 7.2141e-2 | 8.3623e-2 | 1.5719e-1 |
| 32 | 3.3143e-5 | 3.4588e-5 | 4.8486e-5 | 2.4857e-3 | 2.5940e-3 | 3.6352e-3 | 9.6212e-5 | 1.1562e-4 | 2.4262e-4 | 3.8485e-2 | 4.6246e-2 | 9.7049e-2 |
| 48 | 1.7645e-5 | 1.8416e-5 | 2.5946e-5 | 1.2996e-3 | 1.3564e-3 | 1.9105e-3 | 5.2862e-5 | 6.3544e-5 | 1.3430e-4 | 2.1145e-2 | 2.5417e-2 | 5.3721e-2 |

N16/24/32/48 runtimes were `7.04/15.36/25.76/57.21 s`. N48 field-at-numerical-position velocity/density/pressure L2 errors were `1.3564e-3`, `6.3473e-5`, and `2.5389e-2`; initial and endpoint density errors are retained in the analysis JSON and sample CSV.
