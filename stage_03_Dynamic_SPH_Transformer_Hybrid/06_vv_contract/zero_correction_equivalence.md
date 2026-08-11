# Zero-correction equivalence verification

D1 is the first implementation gate. Compare baseline D0 with both `correction_enabled=false` and zeroed final coefficient heads under identical initial state, dt, backend/dtype, EOS, graph builder/order, RK2 arithmetic, and safety policy.

Required scopes are one step, multiple steps, graph/topology sequence, and checkpoint/resume. At each start, midpoint, and accepted state, store state component hashes, graph hash, EOS consistency, and history-isolation evidence. Primary acceptance is bitwise equality. A backend-specific strict componentwise bound is permitted only if frozen before results with justification and cannot hide different topology or branch decisions.

Any effect of the temporal module on baseline state, graph, time step, or failure decision is a gate failure. Later model results are uninterpretable until D1 passes.
