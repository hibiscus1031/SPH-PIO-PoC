# Causal access policy

At an RHS evaluation, the model may access only current/provisional legal state-derived features, the previous three accepted causal entries, the realized current/past reciprocal graphs needed for legal summaries, frozen parameters, and train-only normalization. Future tokens, reference values at or after the rollout origin, targets, family/split labels, and absolute step/time embeddings are forbidden.

Loss computation may compare predicted accepted states with reference targets after the prediction is complete; those targets cannot feed back into the forward state/history. Validation/test targets are unavailable to normalization, threshold design, hyperparameter choice, checkpoint selection, or failure repair.

Causal audits must perturb future/reference fields and verify invariant predictions, inspect feature provenance, and record `teacher_forcing_after_start=false`. Any unauthorized access invalidates the entire lineage component, not just one frame.
