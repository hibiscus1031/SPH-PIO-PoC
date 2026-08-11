# Stage 02F — R2S Reference Design

## Scope

This report freezes the spatial reference class used by Stage 02F. It is a same-state semidiscrete evaluation, not a trajectory, dataset, model, training, or performance-evaluation artifact.

## Historical boundaries retained

- Stage 01: `V2_QUALIFICATION_FAIL`.
- Stage 01H: `FINITE_RESOLUTION_DOMINANT`.
- Viscosity operator form: `NOT CONFIRMED`.
- Stage 02E: `candidate_discretization_target_count=0`.

No Stage 01 conclusion was modified.

## Reference class

`R2S_semidiscrete_spatial_qualified` is instantiated as `r2s_quadratic_kernel_weighted_wls_v1`. For every particle, it uses the exact state, timestamp, EOS, cubic-spline kernel family, physical pressure-plus-viscosity model, and neighbor graph supplied to the baseline SPH operator. Its higher-fidelity spatial evaluation reconstructs the pressure gradient and velocity Laplacian with a local quadratic kernel-weighted least-squares basis in normalized coordinates.

The acceleration is

\[
a_{R2S}=-\frac{\nabla p_{WLS}}{\rho}+\nu\nabla^2v_{WLS}.
\]

No temporal derivative, velocity finite difference, trajectory sample, or future-time state enters this definition.

## Qualification contract

Each candidate must satisfy all five reference checks: same state, same physical configuration, same graph, uncertainty, and determinism. The numerical uncertainty check requires matrix rank at least 5, condition number no greater than \(10^8\), quadratic-reproduction \(L_\infty\) error no greater than \(10^{-10}\), and primary-versus-pseudoinverse relative \(L_2\) sensitivity no greater than \(10^{-10}\). Deterministic repetition requires zero acceleration difference.

All five evaluated candidates passed. Observed matrix conditions were 4.614–6.128, maximum reproduction errors were \(4.47\times10^{-15}\)–\(2.15\times10^{-14}\), solver sensitivities were \(3.48\times10^{-16}\)–\(6.40\times10^{-16}\), and the two complete in-memory evaluations were bitwise identical.

## Interpretation boundary

“Model-form compatible” in Stage 02F means compatible within the frozen R2S internal semidiscrete scope: same physical model, EOS, and kernel family. It does not confirm continuum WCSPH alignment, pairwise conservation, angular-momentum behavior, or the historical viscosity operator form.

Machine-readable contracts and evidence are in `04_target_attribution/semidiscrete_reference/r2s_reference_design.yaml` and `04_target_attribution/semidiscrete_reference/reference_qualification_audit.json`.
