# Stage 02H — Reference Candidates

## Pre-execution freeze

The candidate matrix was written before numerical execution. Candidate IDs, methods, bases, support, resolutions, and cost classes were immutable after results became available. All four candidates and all failures remain in the evidence set.

| ID | Method and basis | Support | Resolution suite | Cost contract |
|---|---|---|---|---|
| `H_REF_QWLS2_INCUMBENT` | quadratic local basis with 5 terms | `H/dx=2.6`, cubic-spline regression weights | 12×12, 16×16, 20×20 | local 5×5 solves; low |
| `H_REF_CWLS3` | cubic local basis with 9 terms | `H/dx=4.1`, Wendland C2 regression weights | 12×12, 16×16, 20×20 | local 9×9 solves; medium |
| `H_REF_FOURIER2` | 25 complex periodic modes, \(k_x,k_y\in[-2,2]\) | global periodic state | 12×12, 16×16, 20×20 | global particles×25 solve; medium audit-only |
| `H_REF_ANALYTIC` | exact periodic-vortex trigonometric derivatives | closed form | 12×12, 16×16, 20×20 | linear in particles; audit-scope only |

The common suite also freezes regular, jitter-5%, and jitter-10% cases at 12×12 with seeds 271828, 314159, and 161803. All methods use the same state samples, EOS, pressure-plus-viscosity physics, and timestamp. No temporal derivative is used.

## Independence

The candidates span local kernel-polynomial, local Wendland-polynomial, global spectral, and closed-form manufactured-derivative classes. The accepted stability pair—Fourier and analytic—therefore does not share a local reconstruction matrix, regression support, or derivative algorithm.

## Scope restrictions

`H_REF_ANALYTIC` is eligible only for the periodic-vortex family. `H_REF_FOURIER2` is accepted only within the controlled periodic-state audit demonstrated here. Neither acceptance grants target-dataset or training authorization.

Frozen matrix: `04_target_attribution/reference_fidelity/reference_candidate_matrix.yaml`.
