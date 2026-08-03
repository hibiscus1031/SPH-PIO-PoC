# Stage 01G-R runner audit

The repaired pipeline is:

`frozen run ID → hash-verified config → typed parameters → frozen output path → independent child → solver entry → diagnostic-only midpoint reconstruction → new evidence files`

Every boundary has an explicit input schema, output schema, and fail-before-next-boundary rule in `diagnostics/stage01gr_runner_contract.md`. Existing output evidence always refuses overwrite. Parent aggregation accepts only scalar JSON; the child PID is reaped and recorded.

The diagnostic midpoint state is reconstructed only to pair the frozen midpoint evaluation with its corresponding positions and velocities for structural diagnostics. It never enters the solver, changes RK2 state, alters RHS values, or modifies final state. The frozen `DynamicStepResult` schema remains `state`, `start_evaluation`, `midpoint_evaluation`, and `end_evaluation`.

Runner contract audit: **PASS**.
