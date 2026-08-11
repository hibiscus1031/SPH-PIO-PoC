# Stage 02I — Candidate Eligibility Audit

All seven candidates pass the six required attribution components:

1. spatial consistency;
2. resolution trend;
3. support consistency;
4. temporal contamination isolation;
5. reference sensitivity;
6. model-form compatibility within the frozen spatial-operator scope.

Accordingly, all seven are marked `candidate_discretization_target=true`; the three primary regular resolution cases are 3/3 qualified. No manual override was used.

This scientific-attribution label is not a training-eligibility verdict. Every candidate retains `training_eligibility=not_yet_evaluated` because no formal dataset, family split, leakage assignment, or normalization contract has been executed.

Pool readiness remains false because conservation compatibility is partial: five candidates are pair-force compatible, while two disorder candidates are node-residual-only. Stage 02J is therefore not authorized.

Machine evidence: `04_target_attribution/qualified_spatial_targets/attribution/six_component_attribution.json` and `results/stage02i_eligibility_results.json`.
