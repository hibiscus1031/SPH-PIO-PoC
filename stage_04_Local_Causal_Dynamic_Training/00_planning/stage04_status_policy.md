# Stage 04 status policy

## Immutable incoming ledger

| Evidence route | Frozen status |
|---|---|
| Stage 03C | `DYNAMIC_RK2_HYBRID_IMPLEMENTATION_VERIFIED` |
| Stage 03D | `DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED` |
| Stage 03D-R | `DYNAMIC_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED` |
| Stage 03D-S | `STAGE03_ROUTE_PAUSED_GRADIENT_BOUNDARY_COMPLETE` |
| Topology component | `TOPOLOGY_EVENT_COMPONENT_QUALIFIED` |
| Stage 03E authorization | `false` |

No Stage 04 result may overwrite, relabel, supersede, backfill, or reinterpret any ledger entry. A fixed math backend in Stage 04 is a prospective evidence environment, not a backend-based reinterpretation of Stage 03.

## Stage 04A terminal states

`LOCAL_CAUSAL_TRAINING_HYPOTHESIS_CONTRACT_COMPLETE` is permitted only if the new hypothesis, historical boundaries, unique K=1 transition, task-aligned gradient gate, formal backend, prospective data/lineage rules, fair model-arm invariants, and 04B–04G roadmap are all explicit, while computation and training counts remain zero.

If any required element is absent or contradictory, the state is `LOCAL_CAUSAL_TRAINING_HYPOTHESIS_CONTRACT_INCOMPLETE`; this state authorizes no subsequent stage.

## Authorization semantics

A complete Stage 04A authorizes only `Stage 04B — New Dynamic Reference-Family Pool and Lineage Qualification`. It does not authorize 04C, 04D, trajectory use before qualification, test release, optimizer use, training, rollout, or performance claims. Each later stage must close its own contract and issue an explicit downstream authorization.

## Non-claim rules

Contract completeness is not scientific confirmation. Gradient qualification is not training success. Training success is not complete solver success. A short-window result cannot be promoted to long-rollout stability. Full-solver claims require autonomous rollout, independent D-R3 validation, and refinement evidence under the later preregistered gates.
