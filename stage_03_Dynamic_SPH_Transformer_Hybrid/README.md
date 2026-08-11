# Stage 03A — Dynamic Hybrid Solver Specification and V&V Contract

Stage 03 is a new dynamic research route. Its hypothesis is that a local Transformer with short causal memory, producing an additive antisymmetric pair-force correction at every SPH step, may express dynamic closure better than an instantaneous static correction operator. This is a hypothesis, not a performance claim.

Stage 03A freezes only the governing equations, temporal architecture, RK2 semantics, dynamic reference hierarchy, trajectory/lineage rules, rollout-loss boundary, V&V ladder, and resource/roadmap constraints. It contains no model implementation, generated trajectory, optimizer, training, rollout execution, solver-in-the-loop execution, or performance result.

The canonical contract is distributed across `00_planning`–`08_resources`; `09_reports/stage03a_final_report.md` is the readable synthesis and `10_manifests` contains machine-readable provenance. Stage 01 and Stage 02 are read-only historical evidence. Stage 02 checkpoints have role `historical_static_diagnostic_only` and may not initialize a Stage 03 model.

Final status: `DYNAMIC_HYBRID_SOLVER_SPECIFICATION_COMPLETE`.

Limited next-stage authorization: Stage 03B — Dynamic Reference Trajectory Qualification. This authorization does not extend to implementation, dataset generation, training, or rollout fitting.
