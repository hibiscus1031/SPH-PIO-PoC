# Stage 01G — Validation metrics and hard-safety protocol

## Metric construction

All norms are particle-volume weighted where a physical field norm is intended. Vector L2 combines both velocity components before normalization; Linf is the maximum particle vector magnitude. Signal-normalized errors use the discrete norm of the independent reference signal at the same preregistered common time. If that denominator is zero, the corresponding time is excluded from a relative metric and retained as an absolute diagnostic; no epsilon denominator may be introduced after viewing results.

Periodic position error uses component-wise minimum-image displacement on the side length 2. Shear amplitude is the least-squares coefficient of \(\sin(k_sy)\), and its fitted decay rate is the slope of a preregistered linear fit to log absolute amplitude over the positive-amplitude common-time samples. Acoustic fundamental coefficients are orthogonal projections onto the frozen cosine density and sine velocity basis; phase is obtained from paired temporal quadratures. Harmonic ratios use the second spatial harmonic divided by the fundamental and are reported only when the fundamental is finite and nonzero.

The N32 time-step check is the absolute difference between main-dt and half-dt primary metrics divided by the half-dt metric magnitude. Spatial ordering is a strict comparison of the separately evaluated N24, N32, and N48 values; no regression fit can replace a failed strict ordering gate.

Validation metrics are evaluator-only quantities. They may not enter solver RHS, initialization adjustment, reference correction, or adaptive threshold selection.

## Frozen hard-safety gates

Every future run must satisfy:

| Diagnostic | Requirement |
|---|---:|
| pair-force residual | <= 1e-12 |
| normalized internal-force residual | <= 1e-10 |
| force assembly defect | <= 1e-10 |
| momentum update defect | <= 1e-10 |
| viscous power positive tolerance | <= 1e-12 |
| structural topology defects | 0 |
| minimum separation/dx | >= 0.25 |
| current RSS | < 2 GB |
| peak RSS | < 4 GB |
| RSS Q4-Q1 absolute increase | <= 250 MB |
| RSS Q4/Q1 | <= 1.50 |
| step-time Q4/Q1 | <= 1.30 |

Each task must use an independent child process, default cyclic GC, `torch.no_grad()`, no in-loop `gc.collect()`, scalar-only parent aggregation, and complete child-process reclamation.

Both benchmarks have no external source. Source call count must be zero, internal total momentum must meet the frozen tolerance, and external-force balance cannot substitute for internal conservation.

## Qualification interpretation

SHEAR1–SHEAR8 and ACOUSTIC1–ACOUSTIC10 are prospective and immutable after execution begins. Failure is retained as failure; missing evidence is not imputed. Stage 01F3B/F3C/F5B MMS trajectories and error points cannot be added to either validation series.
