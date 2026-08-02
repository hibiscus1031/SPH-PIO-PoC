# Stage 01F3B MMS-A continuous-time trend

N32, `H/dx=5.049509756796392`, `t_final=0.02`, five RK2 time steps and 21 common times were used. MMS-A labeled positions use the closed translating trajectory.

| dt | position exact L2 | velocity exact L2 | density exact L2 | pressure exact L2 | position self-difference | velocity self-difference |
|---:|---:|---:|---:|---:|---:|---:|
| 1e-3 | 3.4650e-5 | 2.593688e-3 | 1.15801e-4 | 4.63202e-2 | 2.45993e-8 | 9.66560e-7 |
| 5e-4 | 3.4603e-5 | 2.593882e-3 | 1.15661e-4 | 4.62644e-2 | 6.21061e-9 | 2.30167e-7 |
| 2.5e-4 | 3.4592e-5 | 2.593965e-3 | 1.15626e-4 | 4.62505e-2 | 1.55967e-9 | 5.61655e-8 |
| 1.25e-4 | 3.4589e-5 | 2.593990e-3 | 1.15618e-4 | 4.62471e-2 | 3.90758e-10 | 1.38736e-8 |
| 6.25e-5 | 3.4588e-5 | 2.593997e-3 | 1.15615e-4 | 4.62462e-2 | — | — |

All 5/5 hard paths passed. Position and velocity self-difference finest/coarsest ratios are `0.01588` and `0.01435`, respectively, comfortably below 0.30. Exact position, density and pressure approach a clear spatial platform.

The strict CT2 velocity condition fails: finest velocity exact error is `0.01195%` above coarsest (`2.593688e-3→2.593997e-3`). The absolute behavior is a small approach to a space-error platform rather than a time-instability, but the preregistered “not higher” condition has no tolerance and is not relaxed. MMS-A continuous-time status: **FAIL (CT2 only)**.

At the finest step, field-at-numerical-position velocity/density/pressure L2 errors are `2.593997e-3`, `1.154807e-4`, and `4.619229e-2`. Source, conservation, resource and topology evidence is retained in the corresponding 21-row trajectory sample CSV.
