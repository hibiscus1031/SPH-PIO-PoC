# Stage 02J Leakage Audit

## Family definition

All five records belong to `analytic_periodic_vortex_shared_physics_t0_v1`. Resolution and support identities remain configuration axes, not automatically independent physical families.

Every pair shares the analytic periodic-vortex initial-condition lineage, timestamp `t=0`, reference-generation family, physical coefficients, periodic unit domain, target-construction protocol, and Stage 02I anchor lineage. These relations implement the frozen Stage 02B family/leakage contract.

## Leakage graph

The graph has 5 nodes and all 10 possible undirected leakage edges. With node order `[N12/H2.6, anchor N16/H2.6, N20/H2.6, N16/H2.2, N16/H3.0]`, the adjacency matrix is

```text
0 1 1 1 1
1 0 1 1 1
1 1 0 1 1
1 1 1 0 1
1 1 1 1 0
```

There is exactly one connected component, `leakage_component_000`, with hash `sha256:d11005c75b44659c4777c4fa805d4132b0b2f7c769f704b3ca1e618e88685cee`.

No leakage edge was ignored. No particle-level, edge-level, local-patch, or within-graph split was used.

