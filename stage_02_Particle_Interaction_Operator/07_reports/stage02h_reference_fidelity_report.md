# Stage 02H — Reference Fidelity Report

## Scope

Stage 02H evaluates reference fidelity at the frozen analytic periodic-vortex state and timestamp. It compares spatial acceleration operators only. No target dataset, trajectory, split, normalization, model, training, or performance evaluation is produced.

The requested incumbent name `r2_quadratic_kernel_weighted_wls_v1` resolves to the existing project identity `r2s_quadratic_kernel_weighted_wls_v1`. The alias resolution is recorded without changing the frozen Stage 02F/02G artifact.

## Candidate outcome

Four candidates and six preselected state cases were evaluated twice:

| Candidate | Method | Acceptance |
|---|---|---|
| `H_REF_QWLS2_INCUMBENT` | local quadratic cubic-spline-kernel WLS | diagnostic |
| `H_REF_CWLS3` | local cubic Wendland-weighted WLS | diagnostic |
| `H_REF_FOURIER2` | global periodic Fourier least squares | accepted |
| `H_REF_ANALYTIC` | closed-form spatial differentiation | accepted, periodic-vortex scope only |

Every candidate passed same-state, same-physics, and deterministic checks. Fourier and analytic references also passed low-bias, uncertainty, and independent cross-reference agreement checks. Their six-case acceleration differences are \(1.22\times10^{-14}\)–\(3.31\times10^{-14}\) in particle-RMS \(L_2\), with reference-target pattern cosine numerically equal to 1.

## Fidelity conclusion

Reference stability is demonstrated for the controlled periodic-vortex audit scope by two independent mechanisms: global spectral reconstruction and closed-form spatial differentiation. This does not establish a general-purpose reference for arbitrary states and does not confirm continuum model form or the historical viscosity operator form.

The incumbent Stage 02G bias failure remains diagnostic. Its maximum bias/reference-target ratio is 68.4086. No failed candidate was removed.

Machine evidence is in `04_target_attribution/reference_fidelity/reference_candidate_results.json` and `04_target_attribution/acceptance/reference_acceptance_results.json`.
