# Stage 06A status policy

`ACTUAL_OPTIMIZER_UPDATE_DYNAMICS_QUALIFIED` requires every preregistered blind,
lineage/global, actual-update FD, micro-update, structure/safety, access,
resource, and destruction gate to pass for D1, D2, and D3. It authorizes only
Stage 06B protocol preregistration, validation opening, and sealed-test
preflight.

Any complete hard-gate failure produces
`ACTUAL_OPTIMIZER_UPDATE_DYNAMICS_NOT_QUALIFIED` and stops the formal end-to-end
neural-training route. Missing or non-finite evidence produces
`ACTUAL_OPTIMIZER_UPDATE_DYNAMICS_EVIDENCE_INCOMPLETE`; Stage 06B remains
unauthorized.
