# Stage 02J-R Reference Qualification

For every new family/case, the primary reference is an independently evaluated Fourier spatial derivative and the secondary reference is the preregistered family-specific closed form:

\[
a_{ref}=-\frac{\nabla p}{\rho}+\nu\nabla^2u.
\]

Stage 02H thresholds were loaded directly from `reference_acceptance_rules.yaml`; no threshold was re-entered or changed.

| family | accepted cases | max normalized L2 difference | max normalized Linf difference | min pattern cosine |
|---|---:|---:|---:|---:|
| CROSSMODE_A | 5/5 | 1.6841e-12 | 1.9819e-12 | 1.000000 |
| DIAGONAL_B | 5/5 | 2.0425e-12 | 2.9924e-12 | 1.000000 |
| MIXED_C | 5/5 | 1.0255e-12 | 1.5278e-12 | 1.000000 |

Same state, same physics, deterministic repeat, low reconstruction bias, cross-reference agreement, and uncertainty qualification all pass. Both references are accepted for all 15 cases.

Closed-form derivative unit tests compare pressure gradients, velocity Laplacians, and total acceleration against spectral differentiation on a fixed 32×32 grid. Maximum total-acceleration component errors are `7.62e-13`, `9.68e-13`, and `9.89e-13`; all tests pass. Finite-difference derivatives and automatic differentiation were not used as target references.

