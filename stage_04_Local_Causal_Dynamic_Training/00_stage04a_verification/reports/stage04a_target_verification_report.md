# Stage 04A target verification report

## Verdict

`STAGE04A_TARGET_VERIFIED`

The verdict was formed from the actual Stage 04A artifacts, not from the user-supplied status string. This verification added only the dedicated `00_stage04a_verification/` record and did not alter any pre-existing Stage 04A or Stage 01–03 artifact.

## Artifact and manifest closure

- Exactly one Stage 04A final report was found at `08_reports/stage04a_final_report.md`.
- The input-freeze, contract, and final manifests exist and parse as JSON.
- The contract manifest closes 31/31 declared artifacts with zero missing paths, zero byte-count differences, and zero SHA-256 differences.
- The final manifest closes 6/6 references with zero missing paths, zero byte-count differences, and zero SHA-256 differences.
- No YAML artifact exists in the verified Stage 04A target; therefore there is no unresolved YAML parse result.
- No conflicting Stage 04A final report or final status was found. The unique terminal state is `LOCAL_CAUSAL_TRAINING_HYPOTHESIS_CONTRACT_COMPLETE`.

## Contract audit

The new Stage 04 hypothesis is explicitly distinct from Stage 03E and Stage 03D v0.2 and does not override Stage 03D or Stage 03D-R. The unique v0.1 task fixes `K=1`, accepted history `H=4`, a complete RK2 start/midpoint/accepted transition, midpoint graph rebuild, ephemeral noncommitted midpoint token, one accepted-state commit, strictly earlier reference prehistory, no post-origin reference midpoint/state injection, and target `S_ref^(n+1)`.

The accepted-state loss contains periodic minimum-image position, velocity, and density components with family/trajectory-origin/node balancing. Direct `delta_a`, direct pair-force supervision, and conservation/antisymmetry penalties are prohibited. Numerical component-weight conventions are deferred to prospective Stage 04D registration and cannot be tuned after outcomes.

The hard gradient boundary covers only optimizer parameters: D1 encoder/head; D2 encoder/GRU/head; D3 encoder/Q-K-V-O/feed-forward/head. Initial velocity, initial density, and reference-prehistory input gradients are diagnostic only and are not claimed repaired. Formal evidence is CPU float64; D3 fixes PyTorch `SDPBackend.MATH` and disables flash, memory-efficient, and automatic selection.

D1/D2/D3 require fresh initialization, no Stage 02/03 weights, identical legal information, common reciprocal antisymmetric pair head, common split/loss/budget/checkpoint rule, and no assumed D3 superiority. New Stage 04 formula lineages, complete-lineage split atoms, prohibited random sub-lineage splits, a new sealed test, and D-R3 independent-only use are explicit. The 04A→04B→04C→04D→04E→04F→04G dependency is complete and forbids skipping 04B–04D to train.

## Historical integrity

The preserved ledger is:

- Stage 03C: `DYNAMIC_RK2_HYBRID_IMPLEMENTATION_VERIFIED`;
- Stage 03D: `DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED`;
- Stage 03D-R: `DYNAMIC_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED`;
- Stage 03D-S: `STAGE03_ROUTE_PAUSED_GRADIENT_BOUNDARY_COMPLETE`;
- topology: `TOPOLOGY_EVENT_COMPONENT_QUALIFIED`;
- Stage 03E authorization: `false`.

The Stage 03D-S historical freeze verified 1976/1976 paths with zero missing and zero hash mismatch. The Stage 03D-S final inventory verified 57/57 artifacts. Eight Stage 01/02/03 status sources verified with zero missing, zero hash mismatch, and zero status conflict. No statement claims repaired Stage 03 input gradients, restored Stage 01 V2, established Transformer trainability, or verified neural rollout.

## Prohibited-execution audit

No trajectory array, new reference dataset, optimizer state, trained weight, training log, neural rollout, model-performance artifact, or sealed-test release existed in Stage 04A. Recorded counts are `optimizer_steps=0`, `training_runs=0`, `neural_rollouts=0`, and `performance_evaluations=0`.

## Authorization

The final report and final manifest uniquely authorize only **Stage 04B — New Dynamic Reference-Family Pool and Lineage Qualification**. Training and Stages 04C–04E are not authorized by Stage 04A. Because the target is verified, the conditional workflow proceeds automatically to Stage 04B.
