# Stage 03D-S — Topology component boundary

`TOPOLOGY_EVENT_COMPONENT_QUALIFIED` is preserved independently from the Stage 03D overall verdict.

- TE1: one edge birth and one edge death.
- Replay: 6/6 PASS.
- Fixed-side event gradients: 12/12 PASS.
- Force jumps: finite and bounded under the frozen audit.
- Empty graph: deterministic semantics qualified.
- Differentiability: piecewise smooth on each fixed-topology side; cutoff edge membership itself is discrete and is **not** claimed differentiable.

This component result does not turn Stage 03D into an overall PASS and does not generalize automatically to arbitrary topology-event families.
