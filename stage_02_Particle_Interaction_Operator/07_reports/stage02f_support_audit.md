# Stage 02F — Support Path Audit

## Controlled path

The support path fixes the 8×8 resolution, periodic-vortex initial condition, regular particle order, physical configuration, and timestamp. It varies only `H/dx` through 2.2, 2.6, and 3.0, meeting the three-level minimum and separating support from resolution.

## Results

| H/dx | Target L2 RMS | Target Linf |
|---:|---:|---:|
| 2.2 | 3.752528e-2 | 4.613216e-2 |
| 2.6 | 1.010872e-2 | 1.255734e-2 |
| 3.0 | 1.010872e-2 | 1.255734e-2 |

The maximum-to-minimum target \(L_2\) ratio is 3.712168, below the frozen upper bound of 10. Adjacent Fourier-direction cosines are 0.998540 and 1.000000, above the frozen lower bound of 0.5. Fixed resolution, three support levels, separated controls, bounded magnitude variation, and direction consistency all pass.

The equality of the 2.6 and 3.0 results is consistent with the cubic-spline kernel's compact support: added graph edges beyond the nonzero kernel radius carry zero kernel weight. This is recorded as an operator-support observation, not a performance or continuum model-form claim.

## Verdict

The support path is `PASS` within the frozen R2S semidiscrete internal scope. It does not override the unresolved resolution smoothness check or the historical `NOT CONFIRMED` viscosity-operator conclusion.

Machine-readable evidence is in `04_target_attribution/support_path/support_path_audit.json`.
