# Stage 04C-R RK2 Attenuation

| Arm | A_mid | V_accept | X_accept | V/(dt A) | X/(dt² A) | rho/(dt² A) |
|---|---|---|---|---|---|---|
| D1 | 6.630e-04 | 2.590e-07 | 5.062e-11 | 1.000 | 0.501 | 1.850 |
| D2 | 2.576e-04 | 1.006e-07 | 1.898e-11 | 1.000 | 0.483 | 1.599 |
| D3 | 7.630e-04 | 2.980e-07 | 5.847e-11 | 1.000 | 0.500 | 1.943 |

The velocity ratio is approximately 1 and position ratio approximately 0.5, exactly matching explicit-midpoint RK2 scaling. Hence dt/dt² attenuation is present and quantitatively explains the small accepted-state signal, but it is the contracted integrator scale rather than an implementation defect. The time step was not changed.
