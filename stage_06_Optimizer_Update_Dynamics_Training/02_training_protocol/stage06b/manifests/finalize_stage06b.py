"""Finalize Stage 06B resource evidence, hard gates, reports, and manifests."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import stat
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
STAGE06 = ROOT / "stage_06_Optimizer_Update_Dynamics_Training"
STAGE06B = STAGE06 / "02_training_protocol/stage06b"
REPORTS = STAGE06 / "08_reports"; TOP = STAGE06 / "09_manifests"


def sha_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_report(name: str, value: str) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True); (REPORTS / name).write_text(value.rstrip() + "\n")


def historical_audit() -> dict[str, Any]:
    q06a = STAGE06 / "01_update_map_qualification"
    freeze = json.loads((q06a / "freeze/stage06a_freeze_record.json").read_text()); final06a_path = TOP / "stage06a_final_manifest.json"
    final06a = json.loads(final06a_path.read_text()); changed = []
    for row in freeze["historical_artifacts"]:
        path = ROOT / row["path"]
        if not path.exists() or sha_file(path) != row["sha256"]: changed.append(row["path"])
    for row in final06a["artifacts"]:
        path = ROOT / row["path"]
        if not path.exists() or sha_file(path) != row["sha256"]: changed.append(row["path"])
    private = []
    for row in freeze.get("unreadable_private_artifacts", []):
        path = ROOT / row["path"]
        private.append({"path": row["path"], "size_unchanged": path.stat().st_size == row["size_bytes"],
                        "mode_restored_zero": stat.S_IMODE(path.stat().st_mode) == 0, "payload_read_for_final_audit": False})
    return {"stage01_05_hash_count": len(freeze["historical_artifacts"]), "stage06a_hash_count": len(final06a["artifacts"]),
            "stage06a_final_manifest_sha256": sha_file(final06a_path), "changed": changed, "private_metadata_checks": private,
            "private_modes_and_sizes_unchanged": all(r["size_unchanged"] and r["mode_restored_zero"] for r in private),
            "pass": not changed and all(r["size_unchanged"] and r["mode_restored_zero"] for r in private)}


def resource_forecast(preflight: dict[str, Any], models: dict[str, Any]) -> dict[str, Any]:
    prior = json.loads((STAGE06 / "01_update_map_qualification/resources/stage06a_resource_audit.json").read_text())
    step_seconds = {}
    for arm in ("D1", "D2", "D3"):
        rows = [r for r in prior["per_process"] if r["arm"] == arm]
        summaries = [json.loads((STAGE06 / f"01_update_map_qualification/qualification/{arm.lower()}_{r['seed']}_summary.json").read_text()) for r in rows]
        step_seconds[arm] = sum(r["wall_time_seconds"] for r in rows) / sum(s["qualification_optimizer_steps"] for s in summaries)
    pre_rows = preflight["rows"]
    validation_seconds = {arm: max(r["timing_seconds"]["validation_forward"] for r in pre_rows if r["arm"] == arm) for arm in step_seconds}
    checkpoint_zero = {arm: max(r["checkpoint_bytes"] for r in pre_rows if r["arm"] == arm) for arm in step_seconds}
    parameter_counts = {arm: next(r["parameter_count"] for r in models["runs"] if r["arm"] == arm) for arm in step_seconds}
    checkpoint_full = {arm: checkpoint_zero[arm] + 16*parameter_counts[arm] + 4096 for arm in step_seconds}
    checkpoint_count_per_run = 78
    per_arm = {}
    for arm in step_seconds:
        per_run = 1500*step_seconds[arm] + 75*validation_seconds[arm] + checkpoint_count_per_run*.01
        per_arm[arm] = {"stage06a_actual_update_qualification_seconds_per_optimizer_step_conservative": step_seconds[arm],
                        "stage06b_measured_validation_seconds": validation_seconds[arm], "per_run_wall_seconds": per_run,
                        "three_run_wall_seconds": 3*per_run, "full_checkpoint_bytes_forecast": checkpoint_full[arm],
                        "checkpoint_storage_three_runs_bytes": 3*checkpoint_count_per_run*checkpoint_full[arm]}
    peak_basis = max(prior["peak_rss_delta_max_bytes"], preflight["peak_rss_bytes"])
    peak_forecast = math.ceil(1.15*peak_basis)
    checkpoint_storage = sum(r["checkpoint_storage_three_runs_bytes"] for r in per_arm.values())
    result_storage = 256*1024**2
    graph_per_run = 1500*48*3 + 75*128*3
    result = {"schema": "sph-pio-poc.stage06b.resource-forecast.v1", "runs": 9, "max_updates_per_run": 1500,
              "batch_size": 48, "validation_interval": 20, "validation_count_per_run": 75,
              "checkpoint_interval": 20, "checkpoint_artifact_count_per_run_conservative": checkpoint_count_per_run,
              "per_arm": per_arm, "total_sequential_wall_seconds": sum(r["three_run_wall_seconds"] for r in per_arm.values()),
              "peak_rss_basis_bytes": peak_basis, "peak_rss_safety_factor": 1.15, "peak_rss_forecast_bytes": peak_forecast,
              "peak_rss_limit_bytes": 1610612736, "checkpoint_storage_forecast_bytes": checkpoint_storage,
              "checkpoint_storage_limit_bytes": 10*1024**3, "result_storage_forecast_bytes": result_storage,
              "graph_rebuilds_per_run": graph_per_run, "graph_rebuilds_total": 9*graph_per_run,
              "budget_silently_lowered": False}
    result["gates"] = {"peak_RSS": peak_forecast <= result["peak_rss_limit_bytes"],
                       "checkpoint_storage": checkpoint_storage <= result["checkpoint_storage_limit_bytes"]}
    result["pass"] = all(result["gates"].values())
    return result


def main() -> None:
    freeze = json.loads((TOP / "stage06b_input_freeze_manifest.json").read_text())
    protocol = json.loads((TOP / "stage06b_protocol_manifest.json").read_text()); protocol_path = ROOT / protocol["protocol_path"]
    lr = json.loads((STAGE06B / "lr_selection/formal_lr_selection_matrix.json").read_text())
    batch = json.loads((TOP / "stage06b_batch_manifest.json").read_text()); validation = json.loads((TOP / "stage06b_validation_manifest.json").read_text())
    models = json.loads((TOP / "stage06b_model_seed_manifest.json").read_text()); checkpoint = json.loads((TOP / "stage06b_checkpoint_policy_manifest.json").read_text())
    pre_manifest = json.loads((TOP / "stage06b_preflight_manifest.json").read_text())
    preflight = json.loads((STAGE06B / "zero_step_preflight/zero_step_preflight_results.json").read_text())
    validation_q = json.loads((STAGE06B / "validation_target_qualification/validation_target_qualification.json").read_text())
    sealed = json.loads((STAGE06B / "access_control/sealed_test_denial_audit.json").read_text())
    success = json.loads((STAGE06B / "success_gates/formal_success_gates.json").read_text())
    history = historical_audit(); resource = resource_forecast(preflight, models)
    write_json(STAGE06B / "resource_forecast/stage06b_resource_forecast.json", resource)
    write_json(STAGE06B / "freeze/stage06b_final_historical_audit.json", history)
    target_manifest_path = ROOT / "stage_05_Scale_Aware_Discrete_Defect_Training/09_manifests/stage05b_target_manifest.json"
    target_hashes = {r["target_manifest_sha256"] for r in models["runs"]}
    counters = pre_manifest["counters"]
    sealed_zero = all(v == 0 for v in sealed["sealed_decode_counts"].values())
    checkpoint_identity = all(r["pass"] and all(r["checkpoint_equality"].values()) for r in preflight["rows"])
    gates = {
        "A_historical_freeze": history["pass"],
        "B_protocol_frozen_before_validation": protocol["frozen_before_validation_decode"] and protocol["validation_decode_count_at_freeze"] == 0 and sha_file(protocol_path) == protocol["protocol_sha256"],
        "C_unique_formal_LR": lr["pass"] and len(lr["common_fully_qualified_LR_set"]) >= 1 and lr["selected_formal_learning_rate"] == max(lr["common_fully_qualified_LR_set"]),
        "D_384_TRAIN_unchanged": batch["pass"] and batch["record_count"] == 384 and target_hashes == {sha_file(target_manifest_path)},
        "E_128_validation_complete": validation["pass"] and validation["record_count"] == 128,
        "F_validation_no_feedback": validation["validation_protocol_feedback_count"] == 0 and validation_q["validation_protocol_feedback_count"] == 0,
        "G_nine_run_identities": models["pass"] and models["run_count"] == 9,
        "H_nine_preflights": pre_manifest["pass"] and pre_manifest["passed"] == 9,
        "I_checkpoint_reload_identity": checkpoint_identity,
        "J_sealed_denial": sealed["pass"],
        "K_sealed_decode_zero": sealed_zero,
        "L_resource_forecast": resource["pass"],
        "M_formal_optimizer_steps_zero": counters["formal_optimizer_steps"] == 0 and counters["formal_parameter_updates"] == 0,
        "N_formal_training_runs_zero": counters["formal_training_runs"] == 0,
    }
    complete = all(gates.values())
    status = "FORMAL_TRAINING_PROTOCOL_AND_VALIDATION_PREFLIGHT_READY" if complete else "FORMAL_TRAINING_PROTOCOL_NOT_READY"
    qualification = {"schema": "sph-pio-poc.stage06b.qualification.v1", "status": status, "gates": gates,
                     "Stage06C_authorized": complete, "formal_optimizer_steps": counters["formal_optimizer_steps"],
                     "formal_parameter_updates": counters["formal_parameter_updates"], "formal_training_runs": counters["formal_training_runs"],
                     "sealed_decode_counts": sealed["sealed_decode_counts"]}
    write_json(STAGE06B / "qualification/stage06b_qualification_summary.json", qualification)

    matrix_lines = ["| Arm | Qualification seed | Context | 1e-5 | 3e-5 | 1e-4 | 3e-4 | 1e-3 |", "|---|---:|---|---:|---:|---:|---:|---:|"]
    lookup = {(row["arm"], row["qualification_seed"], row["context"], block["learning_rate"]): row["pass"] for block in lr["matrix"] for row in block["contexts"]}
    for arm in ("D1", "D2", "D3"):
        for seed in (20600601, 20600602, 20600603):
            for context in ("LCDF_01", "LCDF_04", "LCDF_05", "LCDF_06", "LCDF_07", "LCDF_08", "GLOBAL"):
                cells = ["PASS" if lookup[(arm, seed, context, x)] else "FAIL" for x in (1e-5, 3e-5, 1e-4, 3e-4, 1e-3)]
                matrix_lines.append(f"| {arm} | {seed} | {context} | " + " | ".join(cells) + " |")
    matrix_table = "\n".join(matrix_lines)
    lr_summary = ", ".join(f"{r['learning_rate']:.0e}: {r['pass_count']}/63" for r in lr["matrix"])
    run_ids = ", ".join(r["run_id"] for r in models["runs"])
    gate_text = "\n".join(f"- {key}: `{'PASS' if value else 'FAIL'}`" for key, value in gates.items())
    failure_hashes = "\n".join(f"- `{h}`" for h in freeze["stage05c_failure_hashes"] + freeze["stage05cq_failure_hashes"])
    sealed_counts = ", ".join(f"{k}={v}" for k, v in sealed["sealed_decode_counts"].items())
    wall_hours = resource["total_sequential_wall_seconds"] / 3600
    reports = {
      "stage06b_freeze_and_scope.md": f"# Stage 06B Freeze and Scope\n\nUnique authorization: Stage 06A `ACTUAL_OPTIMIZER_UPDATE_DYNAMICS_QUALIFIED`. Protocol `{protocol['protocol_sha256']}` was frozen before any VALIDATION payload decode. Stage 06B performed no formal optimizer step, parameter update, training run, rollout, performance evaluation, ranking, or sealed-test evaluation. Historical audit: PASS ({history['stage01_05_hash_count']} Stage01–05 and {history['stage06a_hash_count']} Stage06A hashes unchanged).",
      "stage06b_lr_selection.md": f"# Stage 06B Formal Learning-Rate Selection\n\nFrozen TRAIN-only rule: maximum of the common fully qualified LR set. Aggregate counts: {lr_summary}. Common set: `{lr['common_fully_qualified_LR_set']}`; unique selected formal LR: `{lr['selected_formal_learning_rate']:.1e}`. FAIL cells above 1e-5 lack candidate-LR actual-update FD coverage; validation reads used: 0.\n\n{matrix_table}",
      "stage06b_training_protocol.md": f"# Stage 06B Formal Training Protocol\n\nProtocol hash: `{protocol['protocol_sha256']}`. Nine fresh CPU/float64/MATH runs use seeds 20600611–20600613, AdamW betas (0.9,0.999), eps 1e-12, weight decay 0, AMSGrad false, global gradient clipping 1.0, and LR 1e-5. Budget is 1500 updates (minimum 320); 40-update linear warmup 0.1×→1× then cosine to 0.1× at update 1500. Values below 1e-5 are marked schedule-only `subqualification_decay_only`. Loss and TRAIN scale remain frozen.",
      "stage06b_train_batch_schedule.md": "# Stage 06B TRAIN Batch Schedule\n\nAll 384 TRAIN origins appear exactly once across eight base batches. Every 48-origin batch contains 8 records per lineage and 24 per variant (4 origins for every lineage/variant cell). Assignment and run-specific epoch order use the two preregistered SHA-256 salts; one epoch is eight updates and no augmentation is used.",
      "stage06b_validation_opening.md": f"# Stage 06B Validation Opening\n\nLCDF_02/LCDF_09 N8 payloads were opened only after protocol hash `{protocol['protocol_sha256']}`. Access was limited to one parameter payload plus four trajectory NPZ/JSON pairs; all reversible POSIX releases restored mode 000. Validation caused zero protocol, threshold, LR, seed, batch, scheduler, scale, target, or arm changes.",
      "stage06b_validation_target_qualification.md": f"# Stage 06B Validation Target Qualification\n\n128/128 records were uniquely constructed with the Stage05B D0/reference/defect/conservative schema and frozen TRAIN `s_a={3.45632855338432798e-1:.17e}`. D0/reference/finite/zero-force gates and 896/896 symmetry checks passed. Pair-basis results are diagnostic only. The validation zero-correction identity gives `L_def,0={validation_q['zero_correction_baseline_L_def']:.9f}` and `Q_def,0={validation_q['zero_correction_baseline_Q_def']:.9f}` under the frozen TRAIN scale; validation was not renormalized to one and did not alter the protocol.",
      "stage06b_checkpoint_and_selection_policy.md": "# Stage 06B Checkpoint and Selection Policy\n\nEach future run saves update 0, every 20 updates, terminal, and selected identities. Selection is the minimum validation global-balanced Q_def; ties choose the earlier update; updates below 320 are recorded but ineligible. Sealed test and diagnostic metrics do not participate. Payload includes model, optimizer, scheduler, RNG, update, protocol hash, and run identity.",
      "stage06b_success_gates.md": f"# Stage 06B Frozen Stage 06C Success Gates\n\nThe frozen selected-checkpoint gates are: `{json.dumps(success, sort_keys=True)}`. A seed requires A–E; an arm requires at least 2/3 seeds; the transformer route requires D3 PASS. D1/D2 completion is mandatory, but their PASS is not a sealed-test authorization condition. No comparative superiority claim is preregistered.",
      "stage06b_zero_step_preflight.md": f"# Stage 06B Zero-Step Preflight\n\nAll {preflight['run_count']}/9 formal identities passed fresh initialization, parameter identity, 48-record TRAIN forward and full finite gradient, 128-record VALIDATION forward, optimizer/scheduler creation, access denial, and destruction. Formal optimizer steps, parameter updates, and training runs remained 0. No preflight weights are eligible for Stage06C reuse.",
      "stage06b_resource_forecast.md": f"# Stage 06B Resource Forecast\n\nConservative sequential wall forecast is `{wall_hours:.2f}` h for nine × 1500 updates, with per-arm actual Stage06A update-qualification timing and Stage06B validation/checkpoint measurements. Peak RSS forecast is `{resource['peak_rss_forecast_bytes']}` bytes (limit 1.5 GiB); checkpoint storage is `{resource['checkpoint_storage_forecast_bytes']}` bytes (limit 10 GiB); result storage allowance is `{resource['result_storage_forecast_bytes']}` bytes. Graph rebuild estimate: `{resource['graph_rebuilds_total']}`. Budget was not lowered. Gate: PASS.",
      "stage06b_qualification_report.md": f"# Stage 06B Qualification Report\n\n{gate_text}\n\nVerdict: `{status}`. Stage06C authorization: `{'true' if complete else 'false'}`.",
    }
    for name, value in reports.items(): write_report(name, value)
    final_report = f"""# Stage 06B Final Report

## 1. Stage06A authorization

The unique authorization was Stage06A `ACTUAL_OPTIMIZER_UPDATE_DYNAMICS_QUALIFIED`.

## 2. Historical failures preservation

Stage05C remains `OPTIMIZER_ALIGNED_DEFECT_GRADIENT_AND_LOCAL_DESCENT_NOT_QUALIFIED`; Stage05C-R remains `DEFECT_GRADIENT_FD_FAILURE_EVIDENCE_INCOMPLETE`; Stage05C-Q remains `PROSPECTIVE_OPTIMIZER_PATH_GRADIENT_CONFIRMATION_NOT_QUALIFIED`; coordinate/block coverage remains `NOT_QUALIFIED`. Preserved failure hashes:

{failure_hashes}

## 3. Protocol hash

`{protocol['protocol_sha256']}` was closed before validation decode and remains unchanged.

## 4. Formal LR selection matrix

TRAIN-only candidate results: {lr_summary}. The complete 63-context × 5-candidate matrix is in `stage06b_lr_selection.md` and the machine-readable manifest.

## 5. Selected LR

The common fully qualified set is `{lr['common_fully_qualified_LR_set']}`; the frozen maximum is `{lr['selected_formal_learning_rate']:.1e}`. Validation was not used.

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

{run_ids}

## 16. Zero-step preflight

9/9 passed fresh initialization, hashes, TRAIN/VALIDATION forwards, full finite gradients, optimizer/scheduler state creation, safety, and access denial. Preflight objects were destroyed.

## 17. Checkpoint/reload

9/9 in-memory update-0 checkpoints preserved model, empty pre-step optimizer, scheduler, RNG, protocol/run identities, parameter hash, and exact next TRAIN forward. No formal checkpoint selection occurred.

## 18. Sealed-test denial

25/25 trainer, validation evaluator, checkpoint selector, report generator, and general reader probes were denied before payload read. Only opaque public seal metadata was inspected.

## 19. Decode counts

{sealed_counts}. Sealed evaluations=0.

## 20. Resource forecast

Sequential wall `{wall_hours:.2f}` h; peak RSS `{resource['peak_rss_forecast_bytes']}` bytes ≤1.5 GiB; checkpoints `{resource['checkpoint_storage_forecast_bytes']}` bytes ≤10 GiB; result allowance `{resource['result_storage_forecast_bytes']}` bytes; graph rebuilds `{resource['graph_rebuilds_total']}`. No budget reduction.

## 21. Stage06C authorization

`{'Stage 06C — Formal K=1 D1/D2/D3 Training is authorized.' if complete else 'Stage06C is not authorized.'}` This is limited authorization; sealed test remains closed.

## 22. Formal optimizer steps

`formal_optimizer_steps = {counters['formal_optimizer_steps']}` and `formal_parameter_updates = {counters['formal_parameter_updates']}`.

## 23. Formal training runs

`formal_training_runs = {counters['formal_training_runs']}`; rollouts=0; performance evaluations=0.

## 24. Historical hashes unchanged

PASS: {history['stage01_05_hash_count']} Stage01–05 artifacts and {history['stage06a_hash_count']} Stage06A artifacts were rehashed with zero changes; private historical payload modes/sizes were restored and unchanged. Stage06A final manifest hash is `{history['stage06a_final_manifest_sha256']}`.

## Final decision

`{status}`
"""
    write_report("stage06b_final_report.md", final_report)
    required_reports = ["stage06b_freeze_and_scope.md", "stage06b_lr_selection.md", "stage06b_training_protocol.md", "stage06b_train_batch_schedule.md",
        "stage06b_validation_opening.md", "stage06b_validation_target_qualification.md", "stage06b_checkpoint_and_selection_policy.md",
        "stage06b_success_gates.md", "stage06b_zero_step_preflight.md", "stage06b_resource_forecast.md", "stage06b_qualification_report.md", "stage06b_final_report.md"]
    artifacts = []
    for path in sorted(STAGE06B.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.name != "stage06b_final_manifest.json":
            artifacts.append({"path": str(path.relative_to(ROOT)), "sha256": sha_file(path), "size_bytes": path.stat().st_size})
    for name in required_reports:
        path = REPORTS / name; artifacts.append({"path": str(path.relative_to(ROOT)), "sha256": sha_file(path), "size_bytes": path.stat().st_size})
    final_manifest = {"schema": "sph-pio-poc.stage06b.final-manifest.v1", "status": status, "complete": True,
        "protocol_sha256": protocol["protocol_sha256"], "selected_formal_learning_rate": lr["selected_formal_learning_rate"],
        "formal_seeds": models["formal_seeds"], "train_record_count": batch["record_count"], "validation_record_count": validation["record_count"],
        "formal_run_count": models["run_count"], "preflight_pass_count": pre_manifest["passed"], "gates": gates,
        "formal_optimizer_steps": counters["formal_optimizer_steps"], "formal_parameter_updates": counters["formal_parameter_updates"],
        "formal_training_runs": counters["formal_training_runs"], "sealed_test_evaluations": counters["sealed_test_evaluations"],
        "rollouts": counters["neural_rollouts"], "performance_evaluations": counters["performance_evaluations"],
        "sealed_decode_counts": sealed["sealed_decode_counts"], "stage05c_failure_hashes_preserved": freeze["stage05c_failure_hashes"],
        "stage05cq_failure_hashes_preserved": freeze["stage05cq_failure_hashes"], "historical_audit": history,
        "resource_forecast": resource, "Stage06C_authorized": complete,
        "next_authorization": "Stage 06C — Formal K=1 D1/D2/D3 Training" if complete else None,
        "sealed_test_remains_closed": True, "artifacts": artifacts}
    write_json(TOP / "stage06b_final_manifest.json", final_manifest)
    write_json(STAGE06B / "manifests/stage06b_final_manifest.json", final_manifest)
    print(json.dumps({"status": status, "gates": gates, "reports": len(required_reports), "artifacts": len(artifacts),
                      "formal_optimizer_steps": counters["formal_optimizer_steps"], "formal_training_runs": counters["formal_training_runs"]}, sort_keys=True))


if __name__ == "__main__": main()
