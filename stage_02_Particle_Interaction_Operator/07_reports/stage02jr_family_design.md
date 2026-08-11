# Stage 02J-R Family Design

## Common physical contract

All new families use a 2D periodic unit square, CPU float64, `t=0`, frozen `rho0`, isothermal EOS, `cs`, `nu`, baseline SPH pressure/viscosity operators, regular equal-mass layouts, no source, no trajectory, and no temporal derivative. Here `k=2*pi` and `U0=0.02*cs`.

Each new family has exactly five preregistered graph candidates: N12/H2.6, N16/H2.6, N20/H2.6, N16/H2.2, and N16/H3.0. The N16/H2.6 anchor is counted once.

## FAMILY_CROSSMODE_A

Role: `future_train`.

```text
rho = rho0[1 + 0.003 cos(kx) + 0.002 cos(2ky)]
ux  = U0[sin(kx)cos(2ky) + 0.20 sin(2kx)cos(ky)]
uy  = U0[-0.70 cos(kx)sin(2ky) + 0.15 cos(2kx)sin(ky)]
```

Closed derivatives use `grad(p)=cs^2 grad(rho)` and `laplacian(u)=-5 k^2 u`.

## FAMILY_DIAGONAL_B

Role: `future_validation`.

```text
rho = rho0[1 + 0.0025 cos(k(x+y)) + 0.0015 cos(k(2x-y))]
ux  = U0[0.80 sin(k(2x+y)) + 0.25 sin(k(x-2y))]
uy  = U0[-0.60 cos(k(2x+y)) + 0.20 cos(k(x-2y))]
```

Its velocity modes also have Laplacian factor `-5 k^2`.

## FAMILY_MIXED_C

Role: `future_test`.

```text
rho = rho0[1 + 0.0020 cos(2kx)cos(2ky) + 0.0015 sin(kx)sin(2ky)]
ux  = U0[sin(2kx)cos(ky) + 0.30 sin(kx)cos(2ky)]
uy  = U0[-0.75 cos(2kx)sin(ky) + 0.25 cos(kx)sin(2ky)]
```

Complete gradient expressions, mode support, lineage IDs, formula hashes, and executable closed forms are retained in `family_preregistration.yaml` and `analytic_family_definitions.py`.

## Positivity and Mach audit

| family | proved relative rho bounds | sampled rho range | sampled Mach range |
|---|---|---|---|
| CROSSMODE_A | [0.995, 1.005] | [0.995135, 1.004865] | [0.000891, 0.020268] |
| DIAGONAL_B | [0.996, 1.004] | [0.996018, 1.003982] | [0.008134, 0.020832] |
| MIXED_C | [0.9965, 1.0035] | [0.997683, 1.002317] | [0.001420, 0.023814] |

All density fields are strictly positive. Stage 01 R3 shear/acoustic formulas, records, and parameter lineages were not reused.

