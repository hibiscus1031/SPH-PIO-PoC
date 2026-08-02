# Stage 01F3B prerequisite checks

The prerequisite gate passed before any formal convergence trajectory was started.

- Full frozen-environment pytest: **236 passed**.
- Stage 01F3-R frozen manifest: 14/14 SHA-256 identities passed.
- Stage 01F3-R evaluator and annotated-tag target: passed.
- Historical Stage 01F3 status: unchanged at `MMS_CONVERGENCE_VERIFICATION_FAIL`.
- Stage 01F source status: `MMS_SPECIFICATION_PASS`.
- Stage 01F2 source-disabled identity: `PASS`.
- Dense reference NPZ and MMS-A/B qualification identities: passed.
- N16 sparse/dense RHS spot-check: 3/3 finite states; maximum total-acceleration absolute/relative differences were `3.109e-15`/`3.460e-15`.
- Fresh N16 MMS-A and MMS-B ten-step smokes: both passed the source, balance, topology, separation and resource gates.
- Each smoke used exactly two source calls per step (`start`, `midpoint`), retained cyclic GC, ran under `torch.no_grad()`, and was fully reclaimed after its child process exited.
- Parent-side summaries contained only scalar trees and relative evidence paths.

The increasing-neighbor and fixed-ratio shell geometry was preregistered before formal spatial results. All cutoff margins exceed `1e-12`; the smallest preregistered margin is `1.161e-3`.

Machine-readable evidence is in `06_experiments/stage_01f3b_mms_convergence/results/prerequisite_checks.json`, `support_path_preregistration.csv`, and the two prerequisite run summaries.
