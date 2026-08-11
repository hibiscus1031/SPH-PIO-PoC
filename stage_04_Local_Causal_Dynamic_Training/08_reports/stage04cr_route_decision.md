# Stage 04C-R Route Decision

| Arm | Input-v gradient | Input-rho gradient | Median full parameter gradient L2 | Acceleration JVP RMS |
|---|---|---|---|---|
| D1 | 4.257e-09 | 1.431e-08 | 2.057e-14 | 6.630e-04 |
| D2 | 2.973e-09 | 3.260e-08 | 1.108e-14 | 2.576e-04 |
| D3 | 3.135e-09 | 3.658e-08 | 5.500e-15 | 7.630e-04 |

Input gradients can reach 1e−10–1e−8 because they act directly on the accepted state and physical RHS. Parameter directions act first through hidden/coefficient/pair-force/correction acceleration, then are attenuated by dt or dt² and multiplied by the MSE residual. This reconciles the historical input-gradient diagnostics with near-zero parameter-loss projections without reopening Stage 03 claims.

No single eligible attribution reaches the frozen 80% threshold. Authorized next branch: none. Stage 04D remains false; training remains unauthorized. A future route requires a new prospective contract rather than changing the historical Stage 04C gate.
