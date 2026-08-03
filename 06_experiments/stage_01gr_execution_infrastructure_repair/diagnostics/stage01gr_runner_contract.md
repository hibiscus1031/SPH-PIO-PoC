# Stage 01G-R runner contract

| Boundary | Input schema | Output schema | Failure boundary |
|---|---|---|---|
| Run ID | Exact string from the frozen 12-row matrix | One unique matrix row | Missing, duplicate, or non-frozen ID stops before directory creation |
| Config | Frozen matrix row plus frozen Stage 01G YAML and their SHA-256 identities | Typed, non-null resolved record | Missing field, hash drift, implicit default, or type conversion failure stops dry resolution |
| Resolved parameters | `benchmark`, `N`, `H_over_dx`, `dt`, `t_final`, common times | Explicit benchmark metadata | Any null, absent common time, or inconsistent horizon stops before process launch |
| Output path | Frozen `future_output_directory` | Exact run-specific path | Path mismatch or existing evidence refuses overwrite |
| Process launch | Frozen Python executable and scalar command arguments | Independent child PID | Wrong environment or launch error produces infrastructure failure only |
| Solver entry | CPU float64 state, explicit regular-layout keywords, frozen physical parameters | Frozen `DynamicStepResult` with `state`, `start_evaluation`, `midpoint_evaluation`, `end_evaluation` | Type/schema mismatch stops smoke; solver code is never changed |
| Diagnostic registration | Current state, frozen step result, explicit `dt` | Diagnostic-only midpoint state and scalar audit | Reconstruction mismatch or missing diagnostic field stops smoke; reconstructed state never enters solver |
| Evidence writing | Scalar status plus typed smoke record | New JSON/stdout/stderr files | Existing path refuses overwrite; no formal trajectory, reference, metric, evaluator, or V2 evidence is written |

The repaired contract fixes only execution-layer adapters. It does not alter RK2, the solver state returned by RK2, benchmark equations, or evaluator behavior.
