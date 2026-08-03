# Stage 01F5B final report

## 1. Frozen basis and identities

Stage 01F5-Q commit `8ab58b8647c1dd1e5cfe71a77cf6ec71c93a1484`, status `FORMAL_SPACE_EXECUTION_BUNDLE_READY`, tag `stage-01f5q-formal-space-execution-bundle-ready`, execution bundle v3, 69-row matrix, and 69/69 dry-resolution audit were frozen. Numerical source commit `38487d66b40fa2c8dd65eb7aa6c279da4a8e5e2c` and the complete source-tree SHA-256 manifest matched before execution.

## 2. Complete run status table

| Run ID | Category | Raw status | Effective status |
|---|---|---|---|
| f5_ref_main_a_baseline | main_reference | PASS | PASS |
| f5_ref_main_a_tighter | main_reference | PASS | PASS |
| f5_ref_main_a_third | main_reference | PASS | PASS |
| f5_ref_main_b_baseline | main_reference | PASS | PASS |
| f5_ref_main_b_tighter | main_reference | PASS | PASS |
| f5_ref_main_b_third | main_reference | PASS | PASS |
| f5_main_a_dt1e3 | main_rk2 | PASS | PASS |
| f5_main_a_dt5e4 | main_rk2 | PASS | PASS |
| f5_main_a_dt2p5e4 | main_rk2 | PASS | PASS |
| f5_main_a_dt1p25e4 | main_rk2 | PASS | PASS |
| f5_main_a_dt6p25e5 | main_rk2 | PASS | PASS |
| f5_main_b_dt1e3 | main_rk2 | PASS | PASS |
| f5_main_b_dt5e4 | main_rk2 | PASS | PASS |
| f5_main_b_dt2p5e4 | main_rk2 | PASS | PASS |
| f5_main_b_dt1p25e4 | main_rk2 | PASS | PASS |
| f5_main_b_dt6p25e5 | main_rk2 | PASS | PASS |
| f5_ref_hold_a_baseline | heldout_reference | PASS | PASS |
| f5_ref_hold_a_tighter | heldout_reference | PASS | PASS |
| f5_ref_hold_a_third | heldout_reference | PASS | PASS |
| f5_ref_hold_b_baseline | heldout_reference | PASS | PASS |
| f5_ref_hold_b_tighter | heldout_reference | PASS | PASS |
| f5_ref_hold_b_third | heldout_reference | PASS | PASS |
| f5_hold_a_dt1e3 | heldout_rk2 | PASS | PASS |
| f5_hold_a_dt5e4 | heldout_rk2 | PASS | PASS |
| f5_hold_a_dt2p5e4 | heldout_rk2 | PASS | PASS |
| f5_hold_a_dt1p25e4 | heldout_rk2 | PASS | PASS |
| f5_hold_a_dt6p25e5 | heldout_rk2 | PASS | PASS |
| f5_hold_b_dt1e3 | heldout_rk2 | PASS | PASS |
| f5_hold_b_dt5e4 | heldout_rk2 | PASS | PASS |
| f5_hold_b_dt2p5e4 | heldout_rk2 | PASS | PASS |
| f5_hold_b_dt1p25e4 | heldout_rk2 | PASS | PASS |
| f5_hold_b_dt6p25e5 | heldout_rk2 | PASS | PASS |
| f5_space_iso_a_dt6p25e5 | space_dt_isolation | PASS | PASS |
| f5_space_iso_a_dt3p125e5 | space_dt_isolation | PASS | PASS |
| f5_space_iso_b_dt6p25e5 | space_dt_isolation | PASS | PASS |
| f5_space_iso_b_dt3p125e5 | space_dt_isolation | PASS | PASS |
| f5_space_a_n16 | formal_space | PASS | PASS |
| f5_space_a_n24 | formal_space | PASS | PASS |
| f5_space_a_n32 | formal_space | PASS | PASS |
| f5_space_a_n48 | formal_space | PASS | PASS |
| f5_space_b_n16 | formal_space | PASS | PASS |
| f5_space_b_n24 | formal_space | PASS | PASS |
| f5_space_b_n32 | formal_space | PASS | PASS |
| f5_space_b_n48 | formal_space | PASS | PASS |
| f5_main_a_dt6p25e5_rep2 | determinism_repeat | PASS | PASS |
| f5_main_b_dt6p25e5_rep2 | determinism_repeat | PASS | PASS |
| f5_hold_a_dt6p25e5_rep2 | determinism_repeat | PASS | PASS |
| f5_hold_b_dt6p25e5_rep2 | determinism_repeat | PASS | PASS |
| f5_space_a_n32_rep2 | determinism_repeat | PASS | PASS |
| f5_space_b_n32_rep2 | determinism_repeat | PASS | PASS |
| f5_ref_space_b_n16_baseline | space_mms_b_reference | PASS | PASS |
| f5_ref_space_b_n16_tighter | space_mms_b_reference | PASS | PASS |
| f5_ref_space_b_n16_third | space_mms_b_reference | PASS | PASS |
| f5_ref_space_b_n24_baseline | space_mms_b_reference | PASS | PASS |
| f5_ref_space_b_n24_tighter | space_mms_b_reference | PASS | PASS |
| f5_ref_space_b_n24_third | space_mms_b_reference | PASS | PASS |
| f5_ref_space_b_n32_baseline | space_mms_b_reference | PASS | PASS |
| f5_ref_space_b_n32_tighter | space_mms_b_reference | PASS | PASS |
| f5_ref_space_b_n32_third | space_mms_b_reference | PASS | PASS |
| f5_ref_space_b_n48_baseline | space_mms_b_reference | PASS | PASS |
| f5_ref_space_b_n48_tighter | space_mms_b_reference | PASS | PASS |
| f5_ref_space_b_n48_third | space_mms_b_reference | PASS | PASS |
| f5_space_a_n64 | conditional_n64 | PASS | PASS |
| f5_space_b_n64 | conditional_n64 | PASS | PASS |
| f5_n64_smoke_a | conditional_n64_smoke | FAIL | PASS |
| f5_n64_smoke_b | conditional_n64_smoke | PASS | PASS |
| f5_ref_space_b_n64_baseline | conditional_n64_reference | PASS | PASS |
| f5_ref_space_b_n64_tighter | conditional_n64_reference | PASS | PASS |
| f5_ref_space_b_n64_third | conditional_n64_reference | PASS | PASS |
| f5_n64_smoke_a_infra_retry1 | conditional_n64_smoke_infrastructure_retry | PASS | PASS |

## 3. Reference qualification

Reference qualification: `PASS`. All reference evidence is newly generated Stage 01F5B evidence using the production sparse RHS and frozen DOP853 levels.

## 4. N20 main time and plateau gates

| Gate | Result |
|---|---|
| P1 | PASS |
| P2 | PASS |
| P3 | PASS |
| T1 | PASS |
| T2 | PASS |
| T3 | PASS |
| T4 | PASS |
| T5 | PASS |

Time-integrator convergence was evaluated against qualified semidiscrete references. Total exact error was used only for plateau gates. Vector cross terms, cosines, squared-norm reconstruction, and platform approach direction were reported but not promoted to qualification gates.

## 5. N28 held-out gates

| Gate | Result |
|---|---|
| H1 | PASS |
| H2 | PASS |
| H3 | PASS |
| H4 | PASS |
| H5 | PASS |

## 6. Space-step decision and formal spatial gates

The immutable Phase F decision selected `dt_space=6.25e-05`, `320` steps, and `t_final=0.02` from the preregistered eight-field comparison.

| Gate | Result |
|---|---|
| S1 | PASS |
| S2 | PASS |
| S3 | PASS |
| S4 | PASS |

The spatial claim is limited to increasing-neighbor consistency-path convergence and is not fixed-stencil single-h convergence.

## 7. N64 branch

The immutable N64 trigger decision was `TRIGGERED` and the frozen DAG was followed. Conditional statuses are recorded in the full run table.

The original `f5_n64_smoke_a` infrastructure failure remains raw `FAIL`; it launched no solver and generated no numerical state. Its sole authorized `_infra_retry1` is recorded separately, and the evaluator validates parameter identity and all retained provenance before assigning the effective predecessor status. No scientific failure is reclassified by this mechanism.

The postexecution evaluator amendment is separately hash-sealed. Its scope is infrastructure-retry reconciliation only; it records no numerical-source, runner, configuration, scientific-gate, threshold, trigger, or execution-order change.

## 8. Safety, provenance, determinism, and GCI

| Gate | Result |
|---|---|
| H1_H5 | PASS |
| S1_S4 | PASS |
| T1_T5_P1_P3 | PASS |
| all_unconditional_hard_and_reference_runs_pass | PASS |
| determinism | PASS |
| n64_branch | PASS |
| preflight | PASS |
| provenance | PASS |
| reference_qualification | PASS |
| space_step_decision | PASS |
| unconditional_complete | PASS |

The source, conservation, topology, resource, and determinism evidence is retained per run. Six determinism pairs had overall status `PASS`. GCI was evaluated independently by variable; where prerequisites failed, the only statement is `GCI not justified`.

The final no-overwrite SHA-256 evidence inventory is `06_experiments/stage_01f5b_requalification_execution/manifests/stage01f5b_final_evidence_sha256.csv`. It covers the complete local run evidence, checkpoints, references, logs, aggregate results, reports, tests, and frozen Stage 01F5-Q/01F5-P inputs.

## 9. Failures and limitations

No failed gate is masked by a platform interpretation or GCI. Reciprocal cutoff crossings and more than one edge identity are legal diagnostics; structural topology defects are hard failures. The one-shot no-overwrite/no-rerun rule remained in force.

## 10. Unique Stage 01F5B status

`PLATEAU_AWARE_MMS_REQUALIFICATION_PASS`

The project is eligible to apply for Stage 01G design. Stage 01G was not started automatically.

Stage 01D2, Stage 01F3, Stage 01F3B, Stage 01F3C, and Stage 01F5-P historical states remain unchanged. V3, Stage 02, training, and label generation have not started.
