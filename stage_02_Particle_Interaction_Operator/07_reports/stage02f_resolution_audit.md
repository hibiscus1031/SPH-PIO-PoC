# Stage 02F — Resolution Path Audit

## Controlled path

The resolution path fixes `H/dx=2.6`, the periodic-vortex initial-condition family, regular particle order, physical configuration, and timestamp. It varies only the resolution through 6×6, 8×8, and 10×10 particle lattices. This meets the three-level minimum and does not bind support to resolution.

## Results

| Resolution | Target L2 RMS | Target Linf | Smoothness ratio to cyclic null |
|---:|---:|---:|---:|
| 6×6 | 1.615859e-2 | 1.982105e-2 | 1.003992 |
| 8×8 | 1.010872e-2 | 1.255734e-2 | 0.991866 |
| 10×10 | 5.847118e-3 | 8.094674e-3 | 0.985518 |

The high-to-low endpoint \(L_2\) ratio is 0.361858. Adjacent Fourier-direction cosines are 0.999895 and 0.999599. Thus the magnitude trend and direction-consistency checks pass.

The predeclared spatial-smoothness rule requires each graph-total-variation ratio to its frozen cyclic-null field to be no greater than 0.9. Observed values are 0.985518–1.003992, so this component fails. This failed check is retained; its threshold was not changed after observing the data.

## Verdict

The resolution path is `DIAGNOSTIC`: three levels, fixed support, magnitude trend, and direction consistency pass, while spatial smoothness is unresolved. This evidence is not used to claim a convergence order or numerical performance.

Machine-readable evidence is in `04_target_attribution/resolution_path/resolution_path_audit.json`.
