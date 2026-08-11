# Stage 06 — Optimizer Update Dynamics Training Route

Stage 06 is a new, user-authorized scientific route. Stage 06A qualifies the
actual AdamW update map on blind TRAIN batches; it is not formal training and
does not revise any Stage 05 verdict.

The only possible Stage 06A terminal statuses are:

- `ACTUAL_OPTIMIZER_UPDATE_DYNAMICS_QUALIFIED`
- `ACTUAL_OPTIMIZER_UPDATE_DYNAMICS_NOT_QUALIFIED`
- `ACTUAL_OPTIMIZER_UPDATE_DYNAMICS_EVIDENCE_INCOMPLETE`

Formal training, validation, sealed-test evaluation, checkpoint creation,
optimizer selection, learning-rate selection, rollout, and arm ranking are
outside Stage 06A.
