# Stage 02J-V Final Report

## Final status

**REGULARITY_HARD_GATE_ROUTE_TERMINATED**

Stage 02J-U authorization: **false**. Stage 02K authorization: **false**. No v0.5 design is permitted.

## 1–6. Historical preservation, necessity, controls, ablation, and Bonferroni statistic

Stage 02J-T remains `REGULARITY_GATE_V03_NOT_QUALIFIED`; its evidence and absent final v0.3 contract are preserved. v0.4 tested the preregistered necessity argument that vector structure may occur in magnitude, direction, or both. The sole test was `p_any=min(1,2*min(p_mag,p_dir))<=0.01`; neither factor nor threshold changed after execution.

All 18 magnitude-only, direction-only, and joint positive-control cases passed. All six constant-vector zero-variation checks passed. RANDOM_PARTICLE_SIGN_FLIP remained a reported direction-ablation control and did not enter hard-negative false-positive counts.

## 7–10. Calibration, development targets, refinement, and invariance

All 24 hard-negative case/control combinations passed the 512-realization one-sided 95% Clopper–Pearson gate; the maximum upper bound was `0.025525872900`.

All six PV/CROSSMODE real targets passed `p_any` and their non-null gates. Component applicability behaved as preregistered: CROSSMODE N12 magnitude refinement was diagnostic because `p_mag=0.778210116732`, while direction refinement was hard and passed.

Invariance failed 9/192 transformation rows. Every failure was exact `p_mag` equality for DIRECTION_ONLY_SMOOTH under amplitude scaling: metric magnitudes stayed inside tolerance and `p_dir/p_any` stayed exact, but near-zero float64 magnitude variation changed the permutation rank. The contract required `p_mag` itself to remain invariant, so this is a hard scientific-gate failure; no posthoc zero threshold was added.

## 11–17. Contract, blind, and auxiliary evidence

- Final v0.4 contract hash: **NOT GENERATED**.
- Concrete blind formulas: not materialized.
- Blind physical bounds/references: not evaluated.
- Blind conservation: not evaluated.
- Blind regularity: 0/4 evaluated.
- DIAGONAL_B/MIXED_C: retained as historical non-blind auxiliary-only; not evaluated or counted.

## 18–23. Route termination and prohibitions

The regularity-hard-gate route is terminated. v0.1, v0.2, the v0.3 candidate, and the v0.4 candidate remain preserved. No v0.5 may be designed. Smoothness/regularity may be used only as diagnostic evidence and may not replace dataset eligibility.

- Stage 02J-U authorized: **false**.
- Stage 02K authorized: **false**.
- Dataset materialization, split, or normalization: **none**.
- Model, Transformer, attention, or neural network: **none**.
- Optimizer or training: **none**.
- Performance claim: **none**.
- Historical hashes unchanged: 325/325; mismatches: 0.
- Stage 01 modified: **no**.
