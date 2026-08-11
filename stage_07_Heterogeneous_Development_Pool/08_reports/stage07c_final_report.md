# Stage07C final report

## Decision

**`FORMAL_RETRAINING_PROTOCOL_AND_FRESH_VALIDATION_PREFLIGHT_READY`**

Stage07D — Formal K=1 TRAIN_V2 D1/D2/D3 Retraining — is authorized.

## Frozen protocol and preserved history

Stage07B authorization is `TRAIN_V2_DEFECT_SCALE_AND_ACTUAL_OPTIMIZER_UPDATE_QUALIFIED`. Stage06C remains `FORMAL_K1_TRAINING_COMPLETE_TRANSFORMER_NOT_QUALIFIED`; Stage06C-R remains `FORMAL_TRAINING_FAILURE_ATTRIBUTED`; D3 attribution remains `TRAIN_LINEAGE_HETEROGENEITY_DOMINANT`. Stage07A/B are unchanged. Protocol hash: `sha256:21b52f0aca3791cdc0d58165f1edd980667bafe0eee5a9d52544c24a8f518dbb`. All 23 named historical inputs, 590 Stage06C checkpoints and 9 selected checkpoints remain hash-identical.

Formal seeds are `[20700711, 20700712, 20700713]` across D1/D2/D3. AdamW and sole LR `1e-5` are unchanged. TRAIN_V2 uses 896/896 Stage07B `y_def_v2` records and `s_a_v2=1.7254786448147168` (`sha256:4ca44e15f2024c5ed02c97d10d1342644fccd17db6a40d7e0e558c8d0214141b`); `s_a_v1` is forbidden.

Eight frozen 112-record batches cover all records exactly once and are lineage/variant balanced. Per-run/epoch order is SHA-256 fixed. Budget is 320--1500 updates with 40-update warmup, cosine decay to `1e-6`, validation/checkpoints every 20, and early-stopping patience 300. Success gates and the fresh-validation-only minimum-Q checkpoint selection policy were frozen before opening. LCDF_08/heterogeneity metrics, raw acceleration RMSE and relative-to-zero-baseline reductions remain diagnostic-only and cannot select checkpoints.

## Fresh validation and isolation

FRESH_VALIDATION_V2 first opened at `2026-08-07T09:07:19.694770+00:00` under the closed protocol hash. 256/256 targets and 1792/1792 seven-transform checks pass using TRAIN-only `s_a_v2`; no validation scale was fitted. Diagnostic zero baseline is `Q_val0_v2=2.0611476240379423`. Validation caused zero protocol changes. All 89 private artifacts were restored mode 000. LCDF_02/09 remained unread and diagnostic-only. The original LCDF_03/10 sealed test passes 45/45 actor denials with every decode/evaluation count zero.

## Zero-step and resource preflight

All 9 formal identities ran in fresh OS processes. 112-record forward/backward memory, frozen 4×64 validation memory, finite full gradient, optimizer/scheduler construction, structure smoke, checkpoint serialize/reload, RNG reload and exact-next-forward checks pass 9/9. Maximum RSS is `1170653184` bytes (delta `960905216`), below `1610612736`. Forecast sequential wall is `37529.2` s, checkpoint storage `305646120` bytes, result storage `76455936` bytes and graph rebuilds `5054400`; all resource gates pass.

Formal optimizer steps = 0; formal parameter updates = 0; formal training runs = 0; saved training checkpoints = 0; sealed-test evaluations = 0; rollouts = 0. Preflight weights and temporary checkpoint payloads were destroyed and cannot be used by Stage07D.

## Gates A--S

| gate | criterion | result |
| --- | --- | --- |
| A | historical_freeze | PASS |
| B | protocol_frozen_before_fresh_validation_decode | PASS |
| C | formal_seeds_fixed | PASS |
| D | optimizer_LR_unchanged | PASS |
| E | TRAIN_V2_896_exact | PASS |
| F | eight_112_batches_cover_896 | PASS |
| G | fresh_validation_256_complete | PASS |
| H | validation_did_not_alter_protocol | PASS |
| I | success_gates_frozen_before_validation | PASS |
| J | nine_run_identities_complete | PASS |
| K | 112_memory_preflight_9_of_9 | PASS |
| L | validation_memory_preflight_9_of_9 | PASS |
| M | zero_step_preflight_9_of_9 | PASS |
| N | checkpoint_reload_9_of_9 | PASS |
| O | original_sealed_test_denial | PASS |
| P | sealed_decode_counts_zero | PASS |
| Q | resource_forecast | PASS |
| R | formal_optimizer_steps_zero | PASS |
| S | formal_training_runs_zero | PASS |
