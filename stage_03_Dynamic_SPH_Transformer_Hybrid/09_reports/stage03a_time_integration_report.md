# Stage 03A time-integration report

The frozen integrator is explicit midpoint/RK2. Start evaluation uses accepted `S^n`, rebuilds `G^n`, constructs the causal token, and forms `k1`. The provisional midpoint is constructed from `k1`, recomputes EOS, independently rebuilds its graph, uses accepted history plus an ephemeral midpoint token, and forms `k2`. The accepted state uses `k2`, recomputes EOS, passes safety checks, and only then commits one accepted token.

Midpoint tokens never enter committed history and never count as physical steps. Failed/rejected steps commit nothing. Each RHS stage has a fresh reciprocal minimum-image graph; whole-step fixed topology is forbidden. Accepted graph/state/history hashes make checkpoint/resume and deterministic repetition auditable.

Neighbor indices, sort order, and edge existence are discrete. Differentiation occurs inside the realized fixed topology through continuous geometry/state/parameters. Edge birth/death and cutoff crossings are piecewise-smooth events reported separately; the project does not claim differentiable neighbor search.

Zero correction must reproduce baseline graph/stage/EOS/state sequences bitwise, or under a strict backend-specific bound frozen before results. This D1 gate precedes all hybrid interpretation. No integrator or solver was implemented or run in Stage 03A.
