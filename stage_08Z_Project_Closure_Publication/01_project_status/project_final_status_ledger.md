# Project final status ledger

## Stage00 — `CONDITIONAL`

- Hypothesis: Apple Silicon CPU/MPS can support a bounded 2D proof of concept.
- Passed: Environment/component readiness and bounded CPU/MPS execution checks.
- Failed: A complete diffSPH solver was not executed as Stage00 truth.
- Consequence: Environment readiness is not solver verification.
- Next authorization: Stage01 minimum verification path
- Training occurred: `False`
- Validation consumed: `False`
- Sealed test accessed: `False`
- Sources: `project_wide_synthesis/02_stage_timeline/complete_stage_timeline.json`

## Stage01 — `V2_QUALIFICATION_FAIL; FINITE_RESOLUTION_DOMINANT`

- Hypothesis: A fixed-physics SPH chain can be verified across implementation, conservation, reference, resolution, and independent-validation layers.
- Passed: Structural operator repair, bounded resource policy, dense-equivalent semidiscrete reference, plateau-aware MMS requalification, evaluator and execution infrastructure.
- Failed: The final independent V2 spatial/shear qualification; high-resolution SPH was not established as truth.
- Consequence: Model-form, temporal, quadrature, topology, and finite-resolution effects must be separated.
- Next authorization: Stage02 qualification-first target route
- Training occurred: `False`
- Validation consumed: `True`
- Sealed test accessed: `False`
- Sources: `project_wide_synthesis/02_stage_timeline/complete_stage_timeline.json`, `06_experiments/stage_01h_viscous_decay_diagnosis/results/stage01h_status.txt`

## Stage02 — `STAGE02_ROUTE_CLOSED_PUBLICATION_BOUNDARY_COMPLETE`

- Hypothesis: A reciprocal conservative pair-force PIO can be structurally qualified and statically fitted.
- Passed: Theory, target/reference hierarchy, blind dataset, and PAIR_FORCE_PIO_ARCHITECTURE_QUALIFIED.
- Failed: Static pair-force fitting v0.1 and v0.2 global train-fit gates; regularity as a hard dataset gate.
- Consequence: Structural correctness and representability did not imply successful static learning; the route moved to dynamic accepted-state tasks.
- Next authorization: Stage03 dynamic hybrid specification
- Training occurred: `True`
- Validation consumed: `True`
- Sealed test accessed: `False`
- Sources: `stage_02_Particle_Interaction_Operator/07_reports/stage02ms_final_report.md`, `stage_02_Particle_Interaction_Operator/06_model/pair_force_pio_architecture_v0_1/results/stage02k_qualification_summary.json`

## Stage03 — `STAGE03_ROUTE_PAUSED_GRADIENT_BOUNDARY_COMPLETE`

- Hypothesis: A conservative RK2 neural hybrid with short history can be implemented and multistep-gradient qualified.
- Passed: Dynamic reference trajectories, RK2 hybrid implementation, zero-correction equivalence, checkpoint identity, one-step AD, and topology component.
- Failed: Complete multistep AD/FD qualification: 216 stable probes and 144 failures; history gradient 0/6.
- Consequence: Correct implementation did not establish multistep trainability; task-aligned gradient diagnosis was required.
- Next authorization: Stage04 task-signal boundary
- Training occurred: `False`
- Validation consumed: `False`
- Sealed test accessed: `False`
- Sources: `stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03ds_final_manifest.json`, `stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03d_final_manifest.json`

## Stage04 — `STAGE04_ROUTE_PAUSED_TASK_SIGNAL_BOUNDARY_COMPLETE`

- Hypothesis: A local-causal raw next-state task can avoid history-gradient attenuation while preserving structure.
- Passed: Local-causal reference-family pool, analytic/topology/DOP853 qualification, sealed role governance, nonzero correction Jacobian and structural safety.
- Failed: TASK_ALIGNED_PARAMETER_GRADIENT_NOT_QUALIFIED; raw state-loss signal was attenuated; complete parameter-coordinate FD coverage was not established.
- Consequence: The target and scale, not only architecture Jacobians, determine detectable optimizer signals.
- Next authorization: Stage05 scale-aware D0 defect route
- Training occurred: `False`
- Validation consumed: `False`
- Sealed test accessed: `False`
- Sources: `stage_04_Local_Causal_Dynamic_Training/09_manifests/stage04cs_final_manifest.json`, `stage_04_Local_Causal_Dynamic_Training/09_manifests/stage04cr_final_manifest.json`

## Stage05 — `PROSPECTIVE_OPTIMIZER_PATH_GRADIENT_CONFIRMATION_NOT_QUALIFIED; target/scale qualified`

- Hypothesis: A D0-centered scale-aware conservative discrete-defect target restores identifiable optimization signals.
- Passed: CONSERVATIVE_DISCRETE_DEFECT_TARGET_AND_SCALE_QUALIFIED with 384 origins; representability, scale, uncertainty, conservation and symmetry gates.
- Failed: Complete coordinate-level FD qualification and local-descent route remained incomplete/not qualified.
- Consequence: The defect formulation was retained, while optimizer-path evidence was moved to actual update dynamics.
- Next authorization: Stage06 actual-optimizer qualification
- Training occurred: `False`
- Validation consumed: `False`
- Sealed test accessed: `False`
- Sources: `stage_05_Scale_Aware_Discrete_Defect_Training/01_defect_target_qualification/stage05b/qualification/stage05b_qualification_summary.json`, `stage_05_Scale_Aware_Discrete_Defect_Training/09_manifests/stage05cq_final_manifest.json`

## Stage06 — `FORMAL_TRAINING_FAILURE_ATTRIBUTED`

- Hypothesis: Qualified actual AdamW update dynamics can support the frozen formal K=1 campaign.
- Passed: ACTUAL_OPTIMIZER_UPDATE_DYNAMICS_QUALIFIED; nine formal runs completed with checkpoint integrity and structure gates.
- Failed: All D1/D2/D3 arms had 0/3 seed passes; transformer route not qualified.
- Consequence: Local descent and update-level trainability did not guarantee the frozen global criterion; failure was attributed to TRAIN lineage heterogeneity.
- Next authorization: Stage07 heterogeneous development pool
- Training occurred: `True`
- Validation consumed: `True`
- Sealed test accessed: `False`
- Sources: `stage_06_Optimizer_Update_Dynamics_Training/01_update_map_qualification/qualification/stage06a_qualification_summary.json`, `stage_06_Optimizer_Update_Dynamics_Training/03_formal_training/stage06cr/manifests/stage06cr_final_manifest.json`

## Stage07 — `TRAIN_V2_RETRAINING_FAILURE_ATTRIBUTED`

- Hypothesis: Prospective formula heterogeneity augmentation can restore shared-map training and fresh-validation transfer.
- Passed: 12-lineage pool qualification, TRAIN_V2 target/scale/update qualification, nine retraining runs, and support-gap attribution.
- Failed: All arms 0/3 seed passes; Branch B NOT_SUPPORTED; HET_S2_02 was descriptor and target out of support.
- Consequence: Formula heterogeneity alone did not guarantee target-manifold support; hash-based role assignment exposed a held-out H2 gap.
- Next authorization: Stage08 systematic coverage V3
- Training occurred: `True`
- Validation consumed: `True`
- Sealed test accessed: `False`
- Sources: `stage_07_Heterogeneous_Development_Pool/05_formal_retraining/stage07dr/results/stage07dr_results.json`, `stage_07_Heterogeneous_Development_Pool/08_reports/stage07dr_final_report.md`

## Stage08 — `SYSTEMATIC_COVERAGE_V3_POOL_NOT_QUALIFIED`

- Hypothesis: Prospective four-layer coverage selection can close consumed support and produce four fresh in-support validation lineages.
- Passed: 128+64 deterministic candidates; 192/192 candidate qualification; eight algorithmic TRAIN selections; TRAIN_V3=14; HET_S2_02 descriptor distance reduced to 1.8606627588827505.
- Failed: 20-lineage descriptor/target support, HET_S2_02 target PCA, key envelopes, and formal fresh-validation closure (0/4).
- Consequence: Descriptor-space support did not imply raw correction-target manifold coverage; final development cycle exhausted.
- Next authorization: None; FULL_SOLVER_TRAINING_ROUTE_CLOSED
- Training occurred: `False`
- Validation consumed: `False`
- Sealed test accessed: `False`
- Sources: `stage_08_Systematic_Coverage_V3/01_systematic_coverage_design/qualification/stage08a_qualification_summary.json`, `stage_08_Systematic_Coverage_V3/08_reports/stage08a_final_report.md`

## Frozen project flags

- `FULL_SOLVER_TRAINING_ROUTE_CLOSED = true`
- `FORMAL_TRAINED_SOLVER_QUALIFIED = false`
- `TRANSFORMER_SUPERIORITY_ESTABLISHED = false`
- `AUTONOMOUS_ROLLOUT_QUALIFIED = false`
- `SEALED_TEST_EVALUATED = false`
- `V2_BASELINE_RESTORED = false`
- `CONSERVATIVE_DYNAMIC_ARCHITECTURE_VERIFIED = true`
- `ZERO_CORRECTION_EQUIVALENCE_VERIFIED = true`
- `DISCRETE_DEFECT_TARGET_QUALIFIED = true`
- `ACTUAL_OPTIMIZER_UPDATE_DYNAMICS_QUALIFIED = true`
- `FORMAL_DYNAMIC_TRAINING_EXECUTED = true`
- `STAGE08_FINAL_DEVELOPMENT_CYCLE = true`
