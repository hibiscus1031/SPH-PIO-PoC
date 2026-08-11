# Final failure taxonomy

## F1 — SPH model-form / finite-resolution boundary

- Frozen status: `BOUNDARY_ESTABLISHED_IN_SCOPE`
- Evidence: Stage01E model-form attribution; Stage01G V2_QUALIFICATION_FAIL; Stage01H FINITE_RESOLUTION_DOMINANT
- Ruled-out alternatives: Time-step and determinism dominance were not supported; operator-form failure was not confirmed.
- Methodological response: WCSPH-compatible MMS, same-semidiscrete DOP853, plateau-aware and independent validation.
- Response succeeded: Partially: references were qualified, final V2 was not.
- Final disposition: High-resolution SPH is not truth.

## F2 — Static pair-force fitting failure

- Frozen status: `STATIC_ROUTE_CLOSED`
- Evidence: Stage02M STATIC_PAIR_FORCE_FITTING_NOT_QUALIFIED; Stage02M-Q STATIC_PAIR_FORCE_FITTING_V02_NOT_QUALIFIED
- Ruled-out alternatives: Architecture/conservation qualification passed; conditioning diagnosis did not rescue global train fit.
- Methodological response: Task-aligned dynamic accepted-state formulation.
- Response succeeded: Static route no; dynamic method advanced.
- Final disposition: Retained as falsification evidence.

## F3 — Multistep AD/FD incomplete qualification

- Frozen status: `DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED`
- Evidence: 216 stable probes; 144 failures; history gradient 0/6
- Ruled-out alternatives: Topology component qualified; implementation and one-step AD passed.
- Methodological response: Local-causal task-aligned gradient contract.
- Response succeeded: No: Stage04 task gradient not qualified.
- Final disposition: Multistep gradient claim prohibited.

## F4 — Raw state-loss signal attenuation

- Frozen status: `TASK_SIGNAL_BOUNDARY_COMPLETE`
- Evidence: Stage04C/04C-R; nonzero correction Jacobian with attenuated task signal
- Ruled-out alternatives: A zero neural Jacobian and gross structural failure were excluded in audited cases.
- Methodological response: D0-centered scaled conservative defect loss.
- Response succeeded: Yes at target/scale and optimizer-update levels.
- Final disposition: Core methodological result.

## F5 — Coordinate-level FD incomplete coverage

- Frozen status: `NOT_QUALIFIED`
- Evidence: Stage05C-R evidence incomplete; Stage05C-Q not qualified
- Ruled-out alternatives: Directional and block diagnostics did not constitute full coordinate coverage.
- Methodological response: Prospective actual AdamW update qualification.
- Response succeeded: Yes for actual update dynamics, not for universal coordinate FD.
- Final disposition: All-coordinate FD claim prohibited.

## F6 — Formal TRAIN-fit failure

- Frozen status: `FORMAL_K1_TRAINING_COMPLETE_TRANSFORMER_NOT_QUALIFIED`
- Evidence: Stage06C nine terminal runs; all arms 0/3 seed passes
- Ruled-out alternatives: Execution incompleteness, checkpoint corruption, update-path failure and structural-force failure were excluded.
- Methodological response: Failure attribution and heterogeneous development pool.
- Response succeeded: Attribution yes; training criterion no.
- Final disposition: No qualified trained solver.

## F7 — Development-pool heterogeneity hypothesis failure

- Frozen status: `FORMAL_TRAIN_V2_RETRAINING_COMPLETE_TRANSFORMER_NOT_QUALIFIED`
- Evidence: Stage07D nine retraining runs; Branch B NOT_SUPPORTED
- Ruled-out alternatives: Pool/reference/update qualifications passed; more formula heterogeneity did not restore global success.
- Methodological response: Held-out support diagnosis and systematic coverage-by-design.
- Response succeeded: Diagnosis yes; V3 qualification no.
- Final disposition: Heterogeneity alone is insufficient.

## F8 — Held-out support-gap failure

- Frozen status: `HELD_OUT_H2_SUPPORT_GAP_DOMINANT`
- Evidence: HET_S2_02 Stage07 descriptor distance 6.5115373494207205; TARGET_OUT_OF_SUPPORT
- Ruled-out alternatives: Pair-basis failure excluded; optimizer plateau and gradient conflict documented.
- Methodological response: Four-layer prospective coverage selection.
- Response succeeded: Descriptor support improved, target support did not.
- Final disposition: Support diagnosis retained.

## F9 — Systematic coverage V3 target-manifold failure

- Frozen status: `SYSTEMATIC_COVERAGE_V3_POOL_NOT_QUALIFIED`
- Evidence: 192/192 candidates; HET_S2_02 descriptor 1.8606627588827505; target residual 3.5113172977959843 > 1.5385435220163268; fresh closure 0/4
- Ruled-out alternatives: Candidate incompleteness, manual role swapping, model-prediction selection and sealed-test leakage were excluded.
- Methodological response: Final route closure and publication synthesis.
- Response succeeded: Yes for evidence closure; no for solver qualification.
- Final disposition: FULL_SOLVER_TRAINING_ROUTE_CLOSED.
