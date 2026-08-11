# Stage07B final report

## Decision

**`TRAIN_V2_DEFECT_SCALE_AND_ACTUAL_OPTIMIZER_UPDATE_QUALIFIED`**

Stage07C — Formal Retraining Protocol Preregistration and Fresh Validation Opening — is authorized within its stated boundary.

## Preserved authorization and history

Stage07A authorization is `HETEROGENEITY_AUGMENTED_DEVELOPMENT_POOL_AND_FRESH_VALIDATION_QUALIFIED`. Stage06C remains `FORMAL_K1_TRAINING_COMPLETE_TRANSFORMER_NOT_QUALIFIED`; Stage06C-R remains `FORMAL_TRAINING_FAILURE_ATTRIBUTED`; D3's historical main attribution remains `TRAIN_LINEAGE_HETEROGENEITY_DOMINANT`. All nine frozen historical input hashes remain unchanged.

The Stage07B contract hash is `sha256:1056cc069e27696ee0451896497f95923edd18c9568e4fcaa3b73c504cb26504`. It was frozen before any NEW_TRAIN_V2 trajectory-array decode and remained unchanged.

## TRAIN_V2 target and scale evidence

TRAIN_V2 contains exactly 14 lineages: six anchors plus eight Stage07A NEW_TRAIN_V2 lineages. The evidence contains 384/384 read-only anchor raw-target imports, 512/512 new complete-RK2 D0 constructions, and 896/896 qualified N8 target records. Conservative compatibility and frozen pair-force basis unbounded/bounded representability both pass; LCDF_08 receives no exception.

Historical `s_a_v1 = 0.3456328553384328` is retained only as history. Formal `s_a_v2 = 1.7254786448147168` with hash `sha256:4ca44e15f2024c5ed02c97d10d1342644fccd17db6a40d7e0e558c8d0214141b`; `s_a_v2/s_a_v1 = 4.9922298`. The TRAIN_V2 zero-correction identity is exactly `1.0`. Uncertainty and distinguishability pass, including 100% overall and per-lineage signal-bearing fractions.

Resolution diagnostics contain 112 N12/N16 cases and remain diagnostic-only: no convergence/GCI claim and no redefinition of `s_a_v2`.

## Actual optimizer evidence

Fresh qualification seeds are 20700701, 20700702, 20700703; historical or trained weights were not read. There are 135/135 frozen contexts. Full-gradient identity, actual AdamW one-step descent at the sole LR `1e-5`, and actual-update FD pass 135/135. The 2/4-step seed-context result is 133/135: the two retained misses are [{"arm": "D1", "context": "HET_S2_01", "seed": 20700703, "step4_relative_loss_reduction": 9.548765117644758e-05}, {"arm": "D2", "context": "HET_S2_01", "seed": 20700701, "step4_relative_loss_reduction": 9.166502605713208e-05}]. Under the preregistered aggregation rule, every arm passes 14/14 lineages at >=2/3 seeds and GLOBAL 3/3; D1, D2 and D3 therefore all pass.

Inter-lineage cosine evidence remains posthoc diagnostic-only. The coordinate/block diagnostic covers 36/36 arm×group×seed units and 144/144 probes with zero hard failures. Complete coordinate/block FD coverage explicitly remains NOT_QUALIFIED.

Structure and safety pass 126/126 arm×seed×lineage audits. The formal peak RSS delta is `1578565632` bytes against `1610612736`; no monotonic autograd retention or dense particle N×N allocation was observed. All qualification models and optimizer states were destroyed; training runs = 0 and saved training checkpoints = 0.

## Isolation and authorization boundary

At both start and end, all 89 fresh-validation private artifacts existed with mode `000` and denied read access. Fresh-validation formula/state/source/target/origin decode counts are all zero. Original sealed-test formula/state/source/target/origin decode and evaluation counts are all zero. Consumed validation was not read.

Stage07C may use this TRAIN-only evidence to freeze a formal retraining protocol, seeds, checkpoint selection and success gates, then close the protocol hash before first opening FRESH_VALIDATION_V2. Stage07B itself did not open validation, train, rank models, save weights, or run rollouts.

## Gates A–Q

| gate | criterion | result |
| --- | --- | --- |
| A | historical_freeze | PASS |
| B | train_v2_exactly_14_lineages | PASS |
| C | target_records_896_complete | PASS |
| D | conservative_compatibility | PASS |
| E | pair_basis_unbounded_bounded | PASS |
| F | scale_positive_finite_zero_baseline | PASS |
| G | uncertainty_distinguishability | PASS |
| H | D1_optimizer_update_dynamics | PASS |
| I | D2_optimizer_update_dynamics | PASS |
| J | D3_optimizer_update_dynamics | PASS |
| K | all_14_lineages_covered | PASS |
| L | global_3_of_3_each_arm | PASS |
| M | structure_safety | PASS |
| N | fresh_validation_decode_zero | PASS |
| O | original_sealed_test_decode_zero | PASS |
| P | resources_provenance | PASS |
| Q | training_runs_zero | PASS |
