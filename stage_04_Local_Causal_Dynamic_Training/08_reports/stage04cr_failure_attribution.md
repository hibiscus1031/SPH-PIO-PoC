# Stage 04C-R Failure Attribution

| Arm | D0 x RMS | D0 v RMS | D0 rho RMS | Random-model v RMS |
|---|---|---|---|---|
| D1 | 9.602e-09 | 4.893e-06 | 1.329e-06 | 4.890e-06 |
| D2 | 9.602e-09 | 4.893e-06 | 1.329e-06 | 4.825e-06 |
| D3 | 9.602e-09 | 4.893e-06 | 1.329e-06 | 5.072e-06 |

D0 is not “already resolved”: velocity and density residuals remain around 4.9e−6 and 1.3e−6, above the frozen 1e−8 all-component rule. Random corrections change the one-step state only weakly, as expected from dt/dt² scaling, but their output and Jacobian are nonzero.

The factor split is component-specific: all 864 `L_x` rows are residual-limited; `L_v` contains 617 projection-dilution, 92 residual-small and 155 unresolved rows; `L_rho` contains 55 projection-dilution, 360 residual-small and 449 unresolved rows. No single explanation reaches 80% and the pattern varies across components/groups. Unique overall attribution: `TASK_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED`.
