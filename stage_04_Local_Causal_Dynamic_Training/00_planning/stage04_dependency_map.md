# Stage 04 dependency map

## Hard stage order

`04A contract` → `04B new family pool` → `04C task-aligned parameter gradients` → `04D training preregistration and sealed-test preflight` → `04E formal K=1 training` → `04F conditional K=2 and autonomous rollout` → `04G independent validation, refinement, and utility`.

Stages 04B, 04C, and 04D are mandatory and may not be skipped to begin training. Failure of any stage halts downstream authorization unless a separately named future contract is created; historical verdicts remain unchanged.

## Evidence dependencies

| Consumer | Required upstream evidence | Explicitly insufficient input |
|---|---|---|
| 04B | 04A lineage, role, split, and seal contracts | Re-splitting the Stage 03B 18 trajectories |
| 04C | 04B-qualified train-role samples plus 04A loss/backend contracts | Stage 03D random final-state probes or D-R3 thresholds |
| 04D | 04B qualified pool and 04C qualified parameter gradients | Result-dependent tuning |
| 04E | Complete 04D protocol and intact test seal | Any informal smoke run or MPS result |
| 04F | K=1 qualification, training, and sealed evaluation | K=1 fit alone |
| 04G | Autonomous rollout evidence and untouched D-R3 role | Training/validation metrics alone |

## Fixed cross-stage invariants

All D1/D2/D3 arms use fresh initialization; identical legal token content; the same reciprocal antisymmetric pair-force head; the same complete-lineage split; the same state loss, optimizer budget, and checkpoint rule; and no assumed arm ranking. Formal D3 qualification uses CPU float64 with PyTorch `SDPBackend.MATH`, and backend identity enters all later checkpoints, run manifests, and result hashes.

## Test-seal dependency

The sealed-test families are assigned at the complete formula-lineage-component level. Before release, target/state decode count must remain exactly zero. D-R3 oblique shear remains `independent_validation_only` and is isolated from training, normalization, validation selection, and threshold selection.
