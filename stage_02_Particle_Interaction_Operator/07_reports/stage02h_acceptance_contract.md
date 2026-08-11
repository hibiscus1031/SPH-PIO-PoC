# Stage 02H — Reference Acceptance Contract

## Frozen rule

A candidate becomes `candidate_spatial_reference` only when all six checks pass:

1. same state;
2. same physics;
3. deterministic;
4. low reconstruction bias;
5. agreement with at least one independent reference candidate;
6. qualified reference uncertainty.

The bias/target and uncertainty/target \(L_2\) limits are 0.10. Pairwise cross-reference limits are 0.10 for normalized \(L_2\), 0.15 for normalized \(L_\infty\), and 0.99 minimum target-pattern cosine. Deterministic repetition permits zero difference. Threshold changes and manual verdict overrides after observation are prohibited.

## Applied decisions

| Candidate | State | Physics | Determinism | Low bias | Cross-reference | Uncertainty | Verdict |
|---|---|---|---|---|---|---|---|
| QWLS2 incumbent | PASS | PASS | PASS | FAIL | FAIL | FAIL | diagnostic |
| CWLS3 | PASS | PASS | PASS | FAIL | FAIL | FAIL | diagnostic |
| Fourier2 | PASS | PASS | PASS | PASS | PASS | PASS | accepted |
| analytic | PASS | PASS | PASS | PASS | PASS | PASS | accepted |

Accepted candidate IDs are `H_REF_FOURIER2` and `H_REF_ANALYTIC`. The analytic candidate is restricted to the periodic-vortex family; Fourier acceptance is restricted to the controlled periodic-state audit scope. Acceptance does not imply continuum model-form confirmation, target-dataset eligibility, model permission, or training permission.

The Stage 02G incumbent bias diagnostic remains in force and cannot be overridden by the acceptance of other candidates.

Rules and results: `04_target_attribution/acceptance/reference_acceptance_rules.yaml` and `04_target_attribution/acceptance/reference_acceptance_results.json`.
