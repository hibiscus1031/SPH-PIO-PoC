# Stage 01F3B MMS-B continuous-time trend

N32, `H/dx=5.049509756796392`, `t_final=0.02`, five RK2 time steps and 21 common times were used. Each labeled-particle trajectory reference used independent DOP853 baseline/tighter integration.

| dt | position exact L2 | velocity exact L2 | density exact L2 | pressure exact L2 | position self-difference | velocity self-difference |
|---:|---:|---:|---:|---:|---:|---:|
| 1e-3 | 3.4690e-5 | 2.599595e-3 | 1.17390e-4 | 4.69561e-2 | 1.23873e-7 | 1.32019e-5 |
| 5e-4 | 3.4642e-5 | 2.599604e-3 | 1.17259e-4 | 4.69038e-2 | 3.17506e-8 | 3.19974e-6 |
| 2.5e-4 | 3.4630e-5 | 2.599654e-3 | 1.17229e-4 | 4.68917e-2 | 8.03577e-9 | 7.86897e-7 |
| 1.25e-4 | 3.4627e-5 | 2.599671e-3 | 1.17222e-4 | 4.68887e-2 | 2.02121e-9 | 1.95065e-7 |
| 6.25e-5 | 3.4626e-5 | 2.599676e-3 | 1.17220e-4 | 4.68880e-2 | — | — |

All 5/5 hard paths passed, including reciprocal dynamic topology switching. Position and velocity self-difference finest/coarsest ratios are `0.01632` and `0.01478`; time-discretization differences contract rapidly while exact errors settle onto a spatial platform.

The strict CT2 velocity condition fails: finest velocity exact error is `0.00312%` above coarsest (`2.599595e-3→2.599676e-3`). Reference sensitivity is far below this spatial platform, but the preregistered zero-tolerance inequality is retained. MMS-B continuous-time status: **FAIL (CT2 only)**.

At the finest step, field-at-numerical-position velocity/density/pressure L2 errors are `2.597641e-3`, `1.170835e-4`, and `4.683339e-2`. The independent labeled-trajectory sensitivity bound, source/balance records and dynamic topology sequence are retained with the 21-row trajectory samples.
