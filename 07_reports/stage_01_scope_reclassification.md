# Stage 01 scope reclassification

Date: 2026-07-31  
Reclassification: **Stage 01 `CONDITIONAL PASS` qualifies V0 only**

This document narrows the interpretation of the completed Stage 01 without
editing or superseding `07_reports/stage_01_solver_validation.md`.  The
original report remains unchanged and its SHA-256 at reclassification is:

```text
a7ebc9c50149a8d252bf138ccf7e119f6d3efb4de6fa6ed0efdc0a64c256e442
```

## Qualification levels

| Level | Current state | Evidence and boundary |
|---|---|---|
| V0 engineering executability | **CONDITIONAL PASS** | The complete official diffSPH DeltaSPH chain ran; the CPU canonical path passed; MPS ran as a hybrid path with CPU-backed compact neighbor search; the tested three-step value-path derivative passed. |
| V1 code verification | **PARTIAL** | Existing tests cover initialization, periodic-domain flags and wrapping, differentiable metrics, short rollout graph retention, artifact integrity and repeat auditing. Kernel moments, manufactured differential operators, pairwise force structure and measured integrator order were not yet verified. |
| V2 solution and physical validation | **NOT COMPLETE** | Stage 01 did not hold physical viscosity, Reynolds number and sound speed fixed across resolution. Its Taylor–Green comparison is an official-demo resolution trend, not a fixed-physics time/space convergence study. |
| V3 reference qualification | **NOT STARTED** | No independent reference-solution qualification, benchmark hierarchy or reference uncertainty assessment has been performed. |

## What Stage 01 established

- The full official diffSPH solver chain executed through particle
  initialization, periodic neighborhood search, kernel operations,
  density/pressure/diffusion terms, time integration and state update.
- CPU completed the canonical 256-, 576- and 1024-particle cases twice.
- MPS completed the requested cases, but `torchCompactRadius` transfers
  compact-neighbor-search data to CPU and indices back to MPS.  It must be
  described as a hybrid MPS/CPU path, not a pure MPS solver.
- The initial-velocity-amplitude value path retained autograd through three
  complete SPH steps on CPU and MPS, with centered finite-difference agreement.
- The result supports continued verification work; it does not yet qualify
  the solver as a fixed-physics reference or training-data generator.

## What Stage 01 did not establish

- It did not verify kernel zeroth/first moments over regular and perturbed
  layouts.
- It did not verify manufactured gradient, divergence and Laplacian errors.
- It did not verify pairwise force antisymmetry, total internal force or
  torque structure.
- It did not measure the empirical order of the selected integrator.
- It did not establish a controllable physical kinematic viscosity shared by
  all resolutions.
- It did not separate temporal, spatial and model-form error.
- It did not justify Richardson extrapolation, GCI or a numerical uncertainty
  percentage.
- It did not qualify full particle-topology differentiability.

## Training gate

Neural-network training, label generation, teacher/student solver
designation, MLP/Transformer implementation and Stage 02 design are **not
authorized** at this point.  They remain blocked until Stage 01B reports an
explicit V1/V2 decision and the result is reviewed.

## Evidence retained without modification

- `07_reports/stage_01_solver_validation.md`
- `07_reports/stage_01_gradient_check.md`
- `07_reports/stage_01_numerical_metrics.csv`
- `07_reports/stage_01_runtime_metrics.csv`
- `06_experiments/stage_01_tgv/raw/`
- `06_experiments/stage_01_tgv/logs/`
- `06_experiments/stage_01_tgv/processed/`

Stage 01B begins with a source-level viscosity/sound-speed/Reynolds/CFL audit.
No fixed-Re or fixed-physics convergence experiment may run until that audit
proves that the physical parameters are controllable without an unreviewed
third-party source modification.
