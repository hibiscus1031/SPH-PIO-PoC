# Stage07D-R Final Report

## Preservation and validation transition
Stage07D remains **FORMAL_TRAIN_V2_RETRAINING_COMPLETE_TRANSFORMER_NOT_QUALIFIED**; Stage07E authorization remains **false**. HET_S1_01, HET_S2_02, HET_S3_03 and HET_S4_03 are permanently **CONSUMED_VALIDATION_V2_DIAGNOSTIC_ONLY**. They cannot again be fresh validation, selection, confirmation, or independent post-choice evidence.

## All 652 checkpoints and selection tension
| Run | selected | terminal | min TRAIN | min fresh | min HET_S2_02 | tension | B/C/D/all ever |
|---|---:|---:|---:|---:|---:|---|---|
| D1_seed20700711 | 1500 | 1500 | 1500 | 1500 | 1500 | False | False/False/False/False |
| D1_seed20700712 | 1500 | 1500 | 1500 | 1500 | 1500 | False | False/False/False/False |
| D1_seed20700713 | 1500 | 1500 | 1500 | 1500 | 1500 | False | False/False/False/False |
| D2_seed20700711 | 1500 | 1500 | 1500 | 1500 | 1500 | False | False/False/False/False |
| D2_seed20700712 | 1500 | 1500 | 1500 | 1500 | 1500 | False | False/False/False/False |
| D2_seed20700713 | 1500 | 1500 | 1500 | 1500 | 1500 | False | False/False/False/False |
| D3_seed20700711 | 940 | 1240 | 1240 | 940 | 940 | False | False/False/False/False |
| D3_seed20700712 | 1080 | 1380 | 1380 | 1080 | 1080 | False | False/False/False/False |
| D3_seed20700713 | 940 | 1240 | 1240 | 940 | 940 | False | False/False/False/False |

Global: `{"ANY_CHECKPOINT_ALL_BCD_PASS": false, "ANY_CHECKPOINT_GLOBAL_VALIDATION_C_PASS": false, "ANY_CHECKPOINT_HET_S2_02_D_PASS": false, "ANY_CHECKPOINT_TRAIN_B_PASS": false}`. No historical checkpoint ever closes all B/C/D gates, so failure is not unique to the nine selected checkpoints. Selected identities and Stage07D gates/verdict remain unchanged.

## TRAIN and consumed-validation decomposition
All update0/selected/terminal identities were evaluated on 14 TRAIN and four consumed-validation lineages, both variants and all 32 origins. Persistent hard lineages: `['HET_S2_01']`; architecture-sensitive: `['HET_S2_01', 'HET_S3_01', 'HET_S4_02', 'LCDF_05']`; seed-sensitive: `['LCDF_04', 'LCDF_05', 'LCDF_06']`. HET_S2_02 alone fails systematically across all origins/seeds while the other consumed lineages transfer.

## HET_S2_02 mechanism evidence
Descriptor geometry: **OUTSIDE_TRAIN_SUPPORT**; target manifold: **TARGET_OUT_OF_SUPPORT**. HET_S2_02 exceeds the TRAIN feature envelope in `['source_rms', 'target_defect_rms_diagnostic', 'oracle_bounded_coefficient_rms']`. Frozen wavevectors, mode count, |k|/angles, phases, amplitudes, L/T mixing, anisotropy, source/target/oracle RMS, graph degree and topology margins are recorded. Raw a_cons under a TRAIN-only PCA basis was used.

Stage07C validation-side bounded/unbounded maximums are `2.759e-15` / `2.759e-15` and zero-force maximum is `6.938e-17`; **PAIR_BASIS_REPRESENTATION_FAILURE is excluded**.

Tangent: D3_seed20700711: H2_02 full=1.0000; D3_seed20700712: H2_02 full=1.0000; D3_seed20700713: H2_02 full=0.9999. Gradient: D3_seed20700711: mean=-0.5763, min=-1.0000, neg=0.786, SYSTEMATIC_GRADIENT_CONFLICT; D3_seed20700712: mean=-0.7104, min=-1.0000, neg=0.857, SYSTEMATIC_GRADIENT_CONFLICT; D3_seed20700713: mean=-0.5980, min=-0.9999, neg=0.786, SYSTEMATIC_GRADIENT_CONFLICT. Origin pattern: **ALL_ORIGINS_CONSISTENT**. History perturbations remain post-hoc only.

## Optimization dynamics
- D3_seed20700711: slopes TRAIN200=-2.277e-06, TRAIN400=-3.203e-06, fresh=-5.122e-06, H2_02=-1.147e-05; OPTIMIZATION_PLATEAU.
- D3_seed20700712: slopes TRAIN200=-1.513e-06, TRAIN400=-2.154e-06, fresh=-3.362e-06, H2_02=-7.775e-06; OPTIMIZATION_PLATEAU.
- D3_seed20700713: slopes TRAIN200=-3.385e-06, TRAIN400=-4.712e-06, fresh=-1.675e-05, H2_02=-4.125e-05; OPTIMIZATION_PLATEAU.

## Stage06C → Stage07D / Branch B
Six common anchors use scale-independent raw RMSE and relative reduction. LCDF_08 raw improvement `-0.000424646`, reduction gain `-0.000616181`. **BRANCH_B_OUTCOME = NOT_SUPPORTED**. Stage06C-R historical attribution is unchanged.

## Attribution and unique route
- D1: **HELD_OUT_H2_SUPPORT_GAP_DOMINANT**.
- D2: **HELD_OUT_H2_SUPPORT_GAP_DOMINANT**.
- D3: **HELD_OUT_H2_SUPPORT_GAP_DOMINANT**.
- **NEXT_ROUTE = SYSTEMATIC_COVERAGE_V3** (unique; no simultaneous branch authorization).

## Boundary closure
Original SEALED_TEST LCDF_03/10 formula/state/source/target/origin decode and evaluation are all `0`. New optimizer steps, parameter updates, training runs, checkpoints, rollouts are all `0`. All 652 checkpoint hashes, nine selected hashes and frozen historical artifacts are unchanged: **True**.

## Final status
**TRAIN_V2_RETRAINING_FAILURE_ATTRIBUTED**  
**BRANCH_B_OUTCOME = NOT_SUPPORTED**  
**NEXT_ROUTE = SYSTEMATIC_COVERAGE_V3**
