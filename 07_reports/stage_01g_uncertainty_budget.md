# Stage 01G — Prospective validation uncertainty budget

The future validation report must retain the following independent components. No component may be silently absorbed into a single error number.

| Component | Prospective treatment | Boundary |
|---|---|---|
| Analytic/linear reference | Shear closure is analytic; acoustic closure is linearized | Acoustic finite-amplitude departure is not zero-reference uncertainty |
| RK2 time step | N32 main-dt versus half-dt difference | Must be <= 10% for the frozen primary metrics |
| Increasing-neighbor spatial envelope | N24/N32/N48 with frozen H/dx | This is not fixed-stencil single-h convergence |
| N48/N32 difference | Report direct finest-two-level differences | Not promoted to an extrapolated truth |
| Float64 determinism | N48 repeat for each benchmark | CPU float64 scope only |
| Acoustic finite-amplitude model form | Compare harmonic behavior across epsilon 0.01, 0.005, 0.0025 | Report separately from numerical discretization error |
| Kernel-density/EOS background | Report mean density/pressure bias and shear density/pressure drift | Frozen operators; no retuning |
| Topology and resource | Report hard gates and diagnostics per run | A safety failure cannot be uncertainty-expanded into a pass |
| Stage 01F5B GCI limitation | State `GCI not justified` where prerequisites fail | Do not fabricate a total GCI |

The budget remains mandatory even though Stage 01F5B did not justify GCI. The future report must present component values or explicit evidence-missing states, preserve covariance/interaction caveats, and avoid a false scalar “total GCI.” Thresholds are preregistered in Stage 01G and cannot be changed after observing SPH outputs.
