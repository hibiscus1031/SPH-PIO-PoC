# Stage 06B Final Report

## 1. Stage06A authorization

The unique authorization was Stage06A `ACTUAL_OPTIMIZER_UPDATE_DYNAMICS_QUALIFIED`.

## 2. Historical failures preservation

Stage05C remains `OPTIMIZER_ALIGNED_DEFECT_GRADIENT_AND_LOCAL_DESCENT_NOT_QUALIFIED`; Stage05C-R remains `DEFECT_GRADIENT_FD_FAILURE_EVIDENCE_INCOMPLETE`; Stage05C-Q remains `PROSPECTIVE_OPTIMIZER_PATH_GRADIENT_CONFIRMATION_NOT_QUALIFIED`; coordinate/block coverage remains `NOT_QUALIFIED`. Preserved failure hashes:

- `sha256:1cc6c29e128dae209787d9e95468f6a3cd675beed7c7b403b94a62da2564eb92`
- `sha256:3e83f230a85ff39ee97ea8f9964fa11ad2668f84291c8bbce244ccf2ca8526f8`
- `sha256:9fb0443d1cbac82cd765f6a2642297e9307a89a07034f0f68d4079762a228a69`
- `sha256:b0aa122c427bea6da621fd27751034f17184b92e878ee50c76afe36044b59fb7`
- `sha256:34fbf73aa8c0221cfb3a588c0669b0e28f125448eb2467533505fff4a12c7dbc`
- `sha256:62f4722bdc8bce75d9966a8aeb335101871f8ef7dda3bfe5587d60bfdd7a3cb0`
- `sha256:823f17db030aa9c007e8f096e0ca94164ef3b4b2a1fc203c15589eeb830d717f`
- `sha256:a013995b33970f2bcc8c426c1c141655acd41ff69dcff5f15a3195ecc086b798`
- `sha256:a4b939ec0f38b99571fca116758d385016f11db7116779e451bc816c0f88fc61`
- `sha256:c5b3322ea469b6282dafd5c2757a0881c5b377dde85c931d266c47f50cf679d1`

## 3. Protocol hash

`sha256:b7918bde82b104895b6d47c798801608938c661c3f8b249f4c832c98c3a83cbe` was closed before validation decode and remains unchanged.

## 4. Formal LR selection matrix

TRAIN-only candidate results: 1e-05: 63/63, 3e-05: 0/63, 1e-04: 0/63, 3e-04: 0/63, 1e-03: 0/63. The complete 63-context × 5-candidate matrix is in `stage06b_lr_selection.md` and the machine-readable manifest.

## 5. Selected LR

The common fully qualified set is `[1e-05]`; the frozen maximum is `1.0e-05`. Validation was not used.

## 6. Formal seeds

Fresh seeds: 20600611, 20600612, 20600613; qualification seeds and weights are excluded.

## 7. 384 TRAIN inventory

384/384 frozen Stage05B TRAIN targets remain hash-identical and are all assigned exactly once.

## 8. 128 VALIDATION inventory

128/128 LCDF_02/LCDF_09 × LOW/MAIN × origins 0–31 records are complete and unique.

## 9. Validation target qualification

D0 class/functional/repeat, defect/reference, finite, zero-force, provenance, and 896 symmetry/invariance audits passed. Bounded pair basis and signal-to-TRAIN-scale remain diagnostics. Frozen TRAIN scale was not recalculated or modified.

## 10. TRAIN batch schedule

Eight balanced 48-origin base batches cover all 384 records without overlap or omission. Deterministic run/epoch orders are sealed in the batch manifest.

## 11. Optimizer and scheduler

AdamW (0.9,0.999), eps 1e-12, weight decay 0, AMSGrad false, clip 1.0, LR 1e-5. Warmup is 40 updates from 0.1× to 1×; cosine decay reaches 0.1× at 1500; subqualification tail values make no new qualification claim.

## 12. Budget and early stopping

Maximum 1500, minimum 320; validation/checkpoint cadence 20. At update ≥320, patience is 300 updates with minimum Q_def improvement 1e-5; no budget extension is allowed.

## 13. Checkpoint selection

Minimum validation global-balanced Q_def, earlier-update tie break, selected update ≥320. Sealed test and diagnostics never participate.

## 14. Success gates

Selected checkpoints must satisfy frozen A–E numerical, TRAIN, validation, per-lineage, conservation, symmetry, and history gates. Each arm needs ≥2/3 seed passes; D3 must pass for the transformer route.

## 15. Nine run IDs

D1_seed20600611, D1_seed20600612, D1_seed20600613, D2_seed20600611, D2_seed20600612, D2_seed20600613, D3_seed20600611, D3_seed20600612, D3_seed20600613

## 16. Zero-step preflight

9/9 passed fresh initialization, hashes, TRAIN/VALIDATION forwards, full finite gradients, optimizer/scheduler state creation, safety, and access denial. Preflight objects were destroyed.

## 17. Checkpoint/reload

9/9 in-memory update-0 checkpoints preserved model, empty pre-step optimizer, scheduler, RNG, protocol/run identities, parameter hash, and exact next TRAIN forward. No formal checkpoint selection occurred.

## 18. Sealed-test denial

25/25 trainer, validation evaluator, checkpoint selector, report generator, and general reader probes were denied before payload read. Only opaque public seal metadata was inspected.

## 19. Decode counts

sealed_formula_decode_count=0, sealed_origin_decode_count=0, sealed_source_decode_count=0, sealed_state_decode_count=0, sealed_target_decode_count=0. Sealed evaluations=0.

## 20. Resource forecast

Sequential wall `24.24` h; peak RSS `1250743092` bytes ≤1.5 GiB; checkpoints `246837942` bytes ≤10 GiB; result allowance `268435456` bytes; graph rebuilds `2203200`. No budget reduction.

## 21. Stage06C authorization

`Stage 06C — Formal K=1 D1/D2/D3 Training is authorized.` This is limited authorization; sealed test remains closed.

## 22. Formal optimizer steps

`formal_optimizer_steps = 0` and `formal_parameter_updates = 0`.

## 23. Formal training runs

`formal_training_runs = 0`; rollouts=0; performance evaluations=0.

## 24. Historical hashes unchanged

PASS: 3700 Stage01–05 artifacts and 206 Stage06A artifacts were rehashed with zero changes; private historical payload modes/sizes were restored and unchanged. Stage06A final manifest hash is `sha256:c7e15ed4fc3a285e50a7ffc687d506807a66d25324bb1c9d90323cc849707219`.

## Final decision

`FORMAL_TRAINING_PROTOCOL_AND_VALIDATION_PREFLIGHT_READY`
