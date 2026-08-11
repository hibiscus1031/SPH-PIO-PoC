# Stage 03 status policy

Exactly one Stage 03A terminal status is permitted.

`DYNAMIC_HYBRID_SOLVER_SPECIFICATION_COMPLETE` requires complete and uniquely executable contracts for equations, correction scope, temporal state/tokens, D0–D3 arms, RK2 graph/history semantics, topology differentiation, zero fallback, references, lineage/leakage, rollout loss, V&V D0–D8, resources, and historical freeze. It additionally requires zero implementation, trajectory, optimizer/training, and rollout execution artifacts.

`DYNAMIC_HYBRID_SOLVER_SPECIFICATION_INCOMPLETE` applies if temporal state, midpoint/history semantics, topology boundary, reference hierarchy, leakage rules, or V&V execution order is ambiguous. Stage 03B is then forbidden.

`DYNAMIC_HYBRID_SOLVER_SPECIFICATION_EVIDENCE_INCOMPLETE` applies if any required historical status, report hash, architecture/dataset manifest, selected-checkpoint boundary, consumed-test state, or provenance link cannot be uniquely resolved. Stage 03B is then forbidden.

Historical failures are immutable facts, not superseded aliases. Completion of a later specification never upgrades Stage 01/02 results.
