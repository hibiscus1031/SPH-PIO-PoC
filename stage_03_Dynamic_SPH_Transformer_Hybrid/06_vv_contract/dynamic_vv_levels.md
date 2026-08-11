# Dynamic V&V levels

Levels are sequential and cannot be skipped.

| Level | Required evidence |
|---|---|
| D0 Specification | Frozen equations, correction scope, architecture/arms, integrator, references, lineage, loss, resources |
| D1 Zero-correction equivalence | One/multistep state, graph sequence, topology, checkpoint/resume; bitwise or preregistered bounded equality |
| D2 Dynamic component verification | RK2 stages, graph rebuild, history commit/rollback, topology events, per-stage conservation, deterministic repeat |
| D3 Multistep differentiability | 1/2/4/8-step AD/FD for parameter, initial state, and hidden state; event samples separated |
| D4 Short rollout fitting | K=1/2/4/8 sequential gates on training, isolated validation, then sealed test |
| D5 Autonomous rollout validation | No forcing; state errors, conservation, density positivity, disorder, stability horizon |
| D6 Solution verification | dt, resolution, and support paths; model/reference uncertainty; no fabricated GCI |
| D7 Independent physical validation | Source-free analytic, independent solver, or experiment |
| D8 Cost/utility | Equal-error wall time/memory with uncertainty; no unmatched speedup claim |

Failure or incomplete evidence at a level blocks scientific claims at that and higher levels. Passing structural levels does not imply fitting or validation.
