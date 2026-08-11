# Graph rebuild contract

The reciprocal periodic minimum-image graph is rebuilt independently from the state used by each RK2 RHS: once at the start and once at the provisional midpoint. Fixed whole-step topology is forbidden. The accepted-state graph used for the next step/history token is rebuilt or deterministically materialized from `S^{n+1}`; it is not silently reused from the midpoint.

Each graph must contain a canonical undirected edge list, reciprocal directed view if needed, cutoff/support configuration, deterministic minimum-image tie rule, edge ordering, and graph hash. Audits cover reciprocal consistency, no unintended self edges, repeated-build determinism, and edge birth/death across cutoff crossings.

Graph construction is controlled by the baseline solver and cannot be predicted, pruned, or modified by the network. Any caching is legal only if it provably returns the same canonical graph as a rebuild and cannot change topology or accumulation order.
