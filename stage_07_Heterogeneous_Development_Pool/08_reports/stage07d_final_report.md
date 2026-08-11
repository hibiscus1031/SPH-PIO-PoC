# Stage07D Final Report

## Authorization, freeze, and preserved history
Stage07C authorization: `FORMAL_RETRAINING_PROTOCOL_AND_FRESH_VALIDATION_PREFLIGHT_READY`. Protocol `sha256:21b52f0aca3791cdc0d58165f1edd980667bafe0eee5a9d52544c24a8f518dbb` and `s_a_v2=1.7254786448147168` / `sha256:4ca44e15f2024c5ed02c97d10d1342644fccd17db6a40d7e0e558c8d0214141b` remained exact. Historical hashes unchanged: **True**.

- Stage06C: `FORMAL_K1_TRAINING_COMPLETE_TRANSFORMER_NOT_QUALIFIED`.
- Stage06C-R: `FORMAL_TRAINING_FAILURE_ATTRIBUTED`.
- D3 historical attribution: `TRAIN_LINEAGE_HETEROGENEITY_DOMINANT`.
- Stage07A: `HETEROGENEITY_AUGMENTED_DEVELOPMENT_POOL_AND_FRESH_VALIDATION_QUALIFIED`.
- Stage07B: `TRAIN_V2_DEFECT_SCALE_AND_ACTUAL_OPTIMIZER_UPDATE_QUALIFIED`.
- Stage07C: `FORMAL_RETRAINING_PROTOCOL_AND_FRESH_VALIDATION_PREFLIGHT_READY`.

## Formal inventory and configuration
Nine runs completed in the frozen order. TRAIN_V2 used 896 records in 14 lineages and eight 112-record base batches; FRESH_VALIDATION_V2 used 256 records in four lineages with lineage-balanced reduction. AdamW LR `1e-5`, betas `(0.9,0.999)`, eps `1e-12`, weight decay 0, AMSGrad false, clip 1.0, frozen warmup/cosine schedule, CPU float64, and explicit `SDPBackend.MATH` were used.

## Terminal states, histories, and selected checkpoints
| Run | Terminal | Updates | Selected | TRAIN Q | FRESH Q | Seed PASS |
|---|---:|---:|---:|---:|---:|---:|
| D1_seed20700711 | MAX_UPDATES | 1500 | 1500 | 0.983554187 | 2.040410564 | False |
| D1_seed20700712 | MAX_UPDATES | 1500 | 1500 | 0.977086393 | 2.029706356 | False |
| D1_seed20700713 | MAX_UPDATES | 1500 | 1500 | 0.978709939 | 2.034934396 | False |
| D2_seed20700711 | MAX_UPDATES | 1500 | 1500 | 0.976991086 | 2.031637650 | False |
| D2_seed20700712 | MAX_UPDATES | 1500 | 1500 | 0.979956565 | 2.035608899 | False |
| D2_seed20700713 | MAX_UPDATES | 1500 | 1500 | 0.979874774 | 2.034753755 | False |
| D3_seed20700711 | EARLY_STOPPED | 1240 | 940 | 0.795695165 | 1.762141387 | False |
| D3_seed20700712 | EARLY_STOPPED | 1380 | 1080 | 0.791977830 | 1.759669733 | False |
| D3_seed20700713 | EARLY_STOPPED | 1240 | 940 | 0.794671525 | 1.764211789 | False |

Formal optimizer steps: `12860`. Training and fresh-validation histories are closed under `05_formal_retraining/stage07d`. Selection used only FRESH_VALIDATION_V2; selected hashes and checkpoint reload identities are closed.

### Selected checkpoint hashes
- D1_seed20700711: update 1500; `sha256:c0c375be619e49f38702f841bda8ca9a28ec49ec2ee23dada44ae004de0c7268`.
- D1_seed20700712: update 1500; `sha256:ec8b5b1ebb01f74599930fc867bf5dca8a27aa93fd102f86bd43a75314e842a5`.
- D1_seed20700713: update 1500; `sha256:3a830cf68c9a77f25991458e871e74085e7c02ac457983cb72f6bc992e923cd8`.
- D2_seed20700711: update 1500; `sha256:bbfbadffeb87ff98f3dec0441c61b909f9164aa077b49df5a4ac93e730f6c1ca`.
- D2_seed20700712: update 1500; `sha256:8b15e26bf68a311aa93f6a9a7083159cb0e752749b25ec96b90abe4ee9924a16`.
- D2_seed20700713: update 1500; `sha256:cfe490640d2f72062714b97a940cd770a724e8fa92f0911c6f5e6125846e6c2c`.
- D3_seed20700711: update 940; `sha256:d69f500775d7dbf95191dea75cd51e46ac6c75c2c5b3eaa918dcc5592c13081c`.
- D3_seed20700712: update 1080; `sha256:3b2608fd30aa8542da0252fc41369a50e24496518cc93a217d1232d24b08494e`.
- D3_seed20700713: update 940; `sha256:c6e4e3c85d12c15cd9ebe2a37caff1779ec3043f256487947cbf30013cdbb25e`.

## Qualification and diagnostics
Arm results: `{"D1": {"arm_pass": false, "completed": 3, "seed_passes": 0}, "D2": {"arm_pass": false, "completed": 3, "seed_passes": 0}, "D3": {"arm_pass": false, "completed": 3, "seed_passes": 0}}`. LCDF_08 and eight-new-lineage update-0/selected/terminal diagnostics are complete. Stage06C↔Stage07D comparison uses only raw acceleration RMSE and per-lineage relative reduction for the six anchors; it is `POSTHOC_MECHANISTIC_DIAGNOSTIC` and does not change the verdict. No D3 superiority, Transformer necessity, attention superiority, or model-ranking claim is made.

### Frozen A–E per seed
- D1_seed20700711: `{"A_numerical_safety": true, "B_train_fit": false, "C_validation_transfer": false, "D_HET_S1_01": true, "D_HET_S2_02": false, "D_HET_S3_03": true, "D_HET_S4_03": true, "E_structure": true}`; seed PASS=False.
- D1_seed20700712: `{"A_numerical_safety": true, "B_train_fit": false, "C_validation_transfer": false, "D_HET_S1_01": true, "D_HET_S2_02": false, "D_HET_S3_03": true, "D_HET_S4_03": true, "E_structure": true}`; seed PASS=False.
- D1_seed20700713: `{"A_numerical_safety": true, "B_train_fit": false, "C_validation_transfer": false, "D_HET_S1_01": true, "D_HET_S2_02": false, "D_HET_S3_03": true, "D_HET_S4_03": true, "E_structure": true}`; seed PASS=False.
- D2_seed20700711: `{"A_numerical_safety": true, "B_train_fit": false, "C_validation_transfer": false, "D_HET_S1_01": true, "D_HET_S2_02": false, "D_HET_S3_03": true, "D_HET_S4_03": true, "E_structure": true}`; seed PASS=False.
- D2_seed20700712: `{"A_numerical_safety": true, "B_train_fit": false, "C_validation_transfer": false, "D_HET_S1_01": true, "D_HET_S2_02": false, "D_HET_S3_03": true, "D_HET_S4_03": true, "E_structure": true}`; seed PASS=False.
- D2_seed20700713: `{"A_numerical_safety": true, "B_train_fit": false, "C_validation_transfer": false, "D_HET_S1_01": true, "D_HET_S2_02": false, "D_HET_S3_03": true, "D_HET_S4_03": true, "E_structure": true}`; seed PASS=False.
- D3_seed20700711: `{"A_numerical_safety": true, "B_train_fit": false, "C_validation_transfer": false, "D_HET_S1_01": true, "D_HET_S2_02": false, "D_HET_S3_03": true, "D_HET_S4_03": true, "E_structure": true}`; seed PASS=False.
- D3_seed20700712: `{"A_numerical_safety": true, "B_train_fit": false, "C_validation_transfer": false, "D_HET_S1_01": true, "D_HET_S2_02": false, "D_HET_S3_03": true, "D_HET_S4_03": true, "E_structure": true}`; seed PASS=False.
- D3_seed20700713: `{"A_numerical_safety": true, "B_train_fit": false, "C_validation_transfer": false, "D_HET_S1_01": true, "D_HET_S2_02": false, "D_HET_S3_03": true, "D_HET_S4_03": true, "E_structure": true}`; seed PASS=False.

### Fresh-validation zero-baseline diagnostics
Frozen `Q_val0_v2=2.0611476240379423`; these reductions are diagnostic and did not alter selection or gates.
- D1_seed20700711: ΔQ_val=-0.020737060; relative validation reduction=+0.010060929.
- D1_seed20700712: ΔQ_val=-0.031441268; relative validation reduction=+0.015254254.
- D1_seed20700713: ΔQ_val=-0.026213228; relative validation reduction=+0.012717783.
- D2_seed20700711: ΔQ_val=-0.029509974; relative validation reduction=+0.014317254.
- D2_seed20700712: ΔQ_val=-0.025538725; relative validation reduction=+0.012390537.
- D2_seed20700713: ΔQ_val=-0.026393869; relative validation reduction=+0.012805424.
- D3_seed20700711: ΔQ_val=-0.299006237; relative validation reduction=+0.145067841.
- D3_seed20700712: ΔQ_val=-0.301477891; relative validation reduction=+0.146267006.
- D3_seed20700713: ΔQ_val=-0.296935835; relative validation reduction=+0.144063352.

### LCDF_08 selected diagnostics for D3
- D3_seed20700711: Q=0.329872479; raw RMSE=0.569187918; relative reduction=+0.174082331.
- D3_seed20700712: Q=0.327675040; raw RMSE=0.565396283; relative reduction=+0.179584167.
- D3_seed20700713: Q=0.326643753; raw RMSE=0.563616820; relative reduction=+0.182166249.

### Stage06C↔Stage07D LCDF_08 scale-independent comparison
- D3 seed ordinal 1: Stage06C raw RMSE=0.589744908, R=+0.144253201; Stage07D raw RMSE=0.569187918, R=+0.174082331.
- D3 seed ordinal 2: Stage06C raw RMSE=0.575574307, R=+0.164815390; Stage07D raw RMSE=0.565396283, R=+0.179584167.
- D3 seed ordinal 3: Stage06C raw RMSE=0.584132395, R=+0.152397213; Stage07D raw RMSE=0.563616820, R=+0.182166249.

The corresponding six-anchor comparison and all eight new-TRAIN-lineage update-0/selected/terminal Q, raw-RMSE, relative-reduction, median/p90/max diagnostics are closed in `heterogeneity_diagnostics/`; they did not participate in selection or qualification.

## Structure, access, resources, and boundary
All nine selected checkpoints underwent independent deterministic, reciprocal exchange/antisymmetry, permutation, edge reorder, translation, Galilean, SO(2), reflection, periodic shift, history-commit, midpoint-noncommit, density/finite, residual, and checkpoint/reload audits. Consumed-validation private reads are 0. Original sealed-test formula/state/source/target/origin decode counts and evaluations are all 0. Peak RSS `1583497216` bytes; checkpoint storage `234745689` bytes; resource PASS `True`. Formal training runs 9; rollouts 0; sealed-test evaluations 0.

Checkpoint integrity passed 652/652 saved update-0/interval/terminal checkpoints; selected structure passed 9/9; selected hashes are closed 9/9. The campaign used strict fresh-OS-process serial execution, 12860 optimizer steps, no replacement/additional seed, no protocol/LR/optimizer/scheduler/loss/scale/architecture/feature change, and no autonomous rollout.

## Stage07E authorization
Stage07E authorization: **False**. Original SEALED_TEST remains closed.

## Final decision
**FORMAL_TRAIN_V2_RETRAINING_COMPLETE_TRANSFORMER_NOT_QUALIFIED**
