# Stage 01G-P — Independence and inverse-crime audit

## Prohibited reuse

The frozen Stage 01G flags and reports prohibit the future benchmarks from using:

- the Stage 01F MMS source or any manufactured force;
- the Stage 01F2 source-adapter path;
- Stage 01F3 references as physical-validation references;
- Stage 01F3B/F3C trajectories;
- Stage 01F5B trajectories or error points;
- any reference corrected using an SPH residual.

The reference path list is empty. Shear truth comes from a closed-form continuum field and closed-form particle trajectory. Acoustic truth comes from independent linear acoustic theory, with finite-amplitude departure classified as model-form uncertainty.

## Evaluator-only metrics

Validation metrics remain evaluator-only. The frozen contract prohibits them from entering solver RHS, modifying initialization, selecting or modifying thresholds, or modifying a reference. Numerical acoustic density remains a kernel sum; the evaluator cannot inject the linear density into the state.

No Stage 01G-P file imports or calls the solver, RK2, DOP853, a source adapter, or a benchmark worker. Independence audit: **PASS**.
