# Stage 06C-R Final Report

## 1. Stage06C failure preservation
Stage06C remains **FORMAL_K1_TRAINING_COMPLETE_TRANSFORMER_NOT_QUALIFIED**. The frozen TRAIN gate remains `Q_train <= 0.50`; checkpoint selection and A–E gates were not changed. Stage06D authorization is **false**.

## 2. All nine histories and optimizer dynamics
- D1_seed20600611: terminal=1500 (MAX_UPDATES), slope200=-4.978e-06, slope400=-6.654e-06, OPTIMIZATION_PLATEAU, SATURATION_OR_STALL_CANDIDATE.
- D1_seed20600612: terminal=1500 (MAX_UPDATES), slope200=-4.028e-06, slope400=-5.360e-06, OPTIMIZATION_PLATEAU, SATURATION_OR_STALL_CANDIDATE.
- D1_seed20600613: terminal=1500 (MAX_UPDATES), slope200=-3.882e-06, slope400=-5.207e-06, OPTIMIZATION_PLATEAU, SATURATION_OR_STALL_CANDIDATE.
- D2_seed20600611: terminal=1500 (MAX_UPDATES), slope200=-6.733e-06, slope400=-8.992e-06, OPTIMIZATION_PLATEAU, SATURATION_OR_STALL_CANDIDATE.
- D2_seed20600612: terminal=1500 (MAX_UPDATES), slope200=-7.528e-06, slope400=-1.001e-05, MIXED, NORMAL_UPDATE_SCALE.
- D2_seed20600613: terminal=1500 (MAX_UPDATES), slope200=-5.116e-06, slope400=-6.877e-06, OPTIMIZATION_PLATEAU, SATURATION_OR_STALL_CANDIDATE.
- D3_seed20600611: terminal=800 (EARLY_STOPPED), slope200=-1.670e-05, slope400=-1.433e-04, VALIDATION_EARLY_STOP_ONLY, NORMAL_UPDATE_SCALE.
- D3_seed20600612: terminal=820 (EARLY_STOPPED), slope200=-8.760e-06, slope400=-1.325e-04, MIXED, NORMAL_UPDATE_SCALE.
- D3_seed20600613: terminal=1000 (EARLY_STOPPED), slope200=-8.664e-06, slope400=-5.048e-05, MIXED, NORMAL_UPDATE_SCALE.

All 11,620 update rows and every-20 global/checkpoint observations were joined without smoothing or interpolation replacing raw evidence. Exact path length, net displacement, relative displacement, encoder/GRU/attention-Q/K/V/O/FFN/pair-head splits, Adam moments, coefficients, saturation, and correction-force residuals are in Stage06C-R results.

## 3. Selected, terminal, best-train, and all-590 scan
| Run | Selected u | Qtrain sel | Terminal u | Qtrain term | Best-train u | Qtrain best | Qval sel | Qval best-train | Tension | Any B pass |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| D1_seed20600611 | 1500 | 0.962203 | 1500 | 0.962203 | 1500 | 0.962203 | 0.642161 | 0.642161 | False | False |
| D1_seed20600612 | 1500 | 0.972237 | 1500 | 0.972237 | 1500 | 0.972237 | 0.654221 | 0.654221 | False | False |
| D1_seed20600613 | 1500 | 0.968334 | 1500 | 0.968334 | 1500 | 0.968334 | 0.651194 | 0.651194 | False | False |
| D2_seed20600611 | 1500 | 0.967218 | 1500 | 0.967218 | 1500 | 0.967218 | 0.645523 | 0.645523 | False | False |
| D2_seed20600612 | 1500 | 0.967139 | 1500 | 0.967139 | 1500 | 0.967139 | 0.639946 | 0.639946 | False | False |
| D2_seed20600613 | 1500 | 0.962008 | 1500 | 0.962008 | 1500 | 0.962008 | 0.641188 | 0.641188 | False | False |
| D3_seed20600611 | 500 | 0.731251 | 800 | 0.722325 | 800 | 0.722325 | 0.123464 | 0.149319 | False | False |
| D3_seed20600612 | 520 | 0.720473 | 820 | 0.715613 | 820 | 0.715613 | 0.156662 | 0.179560 | False | False |
| D3_seed20600613 | 700 | 0.724687 | 1000 | 0.720782 | 1000 | 0.720782 | 0.078721 | 0.088693 | False | False |

`ANY_HISTORICAL_CHECKPOINT_TRAIN_B_PASS = False`. Therefore the TRAIN failure is not solely a selected-checkpoint artifact. No diagnostic identity replaced a Stage06C selection.

## 4. TRAIN lineage, origins, and VALIDATION decomposition
All selected and terminal identities were reevaluated on 384 TRAIN and 128 VALIDATION origins. The origin × arm × seed matrix, LOW/MAIN and six/two-lineage decompositions, seed mean/std/range, persistent/seed-sensitive/architecture-sensitive labels, target/source/oracle/topology/graph/time/formula correlations, and TRAIN–VALIDATION distribution contrasts are complete. No hard family was removed and no role/split changed.

## 5. Learning-rate evidence
- 1e-05: **DIRECTLY_QUALIFIED**; D1=DIRECTLY_QUALIFIED, D2=DIRECTLY_QUALIFIED, D3=DIRECTLY_QUALIFIED
- 3e-05: **PARTIALLY_SUPPORTED**; D1=PARTIALLY_SUPPORTED, D2=PARTIALLY_SUPPORTED, D3=PARTIALLY_SUPPORTED
- 1e-04: **PARTIALLY_SUPPORTED**; D1=PARTIALLY_SUPPORTED, D2=PARTIALLY_SUPPORTED, D3=PARTIALLY_SUPPORTED
- 3e-04: **PARTIALLY_SUPPORTED**; D1=PARTIALLY_SUPPORTED, D2=PARTIALLY_SUPPORTED, D3=PARTIALLY_SUPPORTED
- 1e-03: **ACTUALLY_FAILED**; D1=ACTUALLY_FAILED, D2=ACTUALLY_FAILED, D3=PARTIALLY_SUPPORTED

Higher-LR missing candidate-LR actual-update FD coverage is not written as an actual failure. No hypothetical evidence was converted into training authorization.

## 6. Plateau, update scale, capacity, and history value
- D1: head=1.0000; full=1.0000; HIGH_LOCAL_REDUCIBILITY.
- D2: head=1.0000; full=1.0000; HIGH_LOCAL_REDUCIBILITY.
- D3: head=1.0000; full=1.0000; HIGH_LOCAL_REDUCIBILITY.

- D3_seed20600611: history_order_permutation ΔQ=-0.001328, normal_history ΔQ=+0.000000, repeated_current_token ΔQ=+0.002847, zeroed_temporal_offset_encoding ΔQ=+0.006413
- D3_seed20600612: history_order_permutation ΔQ=-0.001217, normal_history ΔQ=+0.000000, repeated_current_token ΔQ=+0.002850, zeroed_temporal_offset_encoding ΔQ=+0.013794
- D3_seed20600613: history_order_permutation ΔQ=-0.001558, normal_history ΔQ=+0.000000, repeated_current_token ΔQ=+0.003271, zeroed_temporal_offset_encoding ΔQ=+0.001270

Gradient alignment, D3 layer1/layer2 attention evolution, coefficient dynamics, local pair-head/full-network tangent range, and Stage05B oracle nodal-correction comparisons are post-hoc mechanism evidence only.

## 7. Per-arm and overall attribution
| Arm | Primary attribution | Mean TRAIN Q | Mean VALIDATION Q | Tangent reducibility |
|---|---|---:|---:|---:|
| D1 | OPTIMIZATION_PLATEAU_WITH_REDUCIBLE_RESIDUAL | 0.967591 | 0.649192 | 1.0000 |
| D2 | OPTIMIZATION_PLATEAU_WITH_REDUCIBLE_RESIDUAL | 0.965455 | 0.642219 | 1.0000 |
| D3 | TRAIN_LINEAGE_HETEROGENEITY_DOMINANT | 0.725470 | 0.119616 | 1.0000 |

Overall decision: **FORMAL_TRAINING_FAILURE_ATTRIBUTED**.

## 8. Prospective branches
- Branch B: New heterogeneous TRAIN development pool.

No branch was executed. If a new TRAIN pool or architecture is pursued, it requires new validation; current validation becomes consumed development evidence where specified.

## 9. Boundary and integrity
New optimizer steps: `0`; new parameter updates: `0`; new training runs: `0`; sealed-test evaluations: `0`; rollouts: `0`. All five sealed decode counts remain `0`. Stage06D is `false`; SEALED_TEST is `CLOSED`. All 590 checkpoint hashes, nine selected hashes, Stage06C report/manifest hashes, Stage01–05, Stage06A, Stage06B, and ten historical failure hashes are unchanged: **True**.

## Final status
**FORMAL_TRAINING_FAILURE_ATTRIBUTED**
