"""Freeze and verify Stage07D before the first formal optimizer step."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve(); D = HERE.parents[1]; S7 = HERE.parents[3]; ROOT = HERE.parents[4]
C = S7 / "04_training_protocol/stage07c"; REPORTS = S7 / "08_reports"; MANIFESTS = S7 / "09_manifests"
PROTOCOL = "sha256:21b52f0aca3791cdc0d58165f1edd980667bafe0eee5a9d52544c24a8f518dbb"
SCALE = 1.7254786448147168
SCALE_HASH = "sha256:4ca44e15f2024c5ed02c97d10d1342644fccd17db6a40d7e0e558c8d0214141b"
TARGET_HASH = "sha256:9672352d3a9ee0798d86a52a92151167c3bb83ddb38e5eef1e31e491fa1d4198"
RUN_IDS = [f"{arm}_seed{seed}" for arm in ("D1", "D2", "D3") for seed in (20700711, 20700712, 20700713)]
DIRS = ["freeze", "execution_control", "access_control", "checkpoints", "training_histories", "validation_histories",
        "heterogeneity_diagnostics", "checkpoint_selection", "checkpoint_integrity", "postfit_structure", "resources",
        "qualification", "manifests", "results", "determinism"]

def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""): h.update(chunk)
    return "sha256:" + h.hexdigest()

def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

def artifact_ok(row: dict[str, Any]) -> bool:
    path = ROOT / row["path"]
    return path.is_file() and sha(path) == row["sha256"]

def main() -> None:
    for name in DIRS: (D / name).mkdir(parents=True, exist_ok=True)
    for run_id in RUN_IDS: (D / "runs" / run_id).mkdir(parents=True, exist_ok=True)
    final = json.loads((MANIFESTS / "stage07c_final_manifest.json").read_text())
    protocol_manifest = json.loads((C / "manifests/stage07c_protocol_manifest.json").read_text())
    scale = json.loads((MANIFESTS / "stage07b_scale_manifest.json").read_text())
    target = C.parent.parent / "02_defect_scale_requalification/stage07b/manifests/target_record_manifest.json"
    schedule_path = C / "train_v2_batch_schedule/formal_train_v2_batch_schedule.json"
    schedule = json.loads(schedule_path.read_text())
    train_cache = json.loads((C / "train_v2_batch_schedule/train_case_cache_manifest.json").read_text())
    val_cache = json.loads((C / "validation_target_construction/validation_case_cache_manifest.json").read_text())
    models = json.loads((C / "model_seed_schedule/formal_model_seed_schedule.json").read_text())
    policy = json.loads((C / "checkpoint_policy/frozen_checkpoint_selection_policy.json").read_text())
    gates = json.loads((C / "success_gates/frozen_success_gates.json").read_text())
    denial = json.loads((C / "sealed_test_preflight/original_sealed_test_denial.json").read_text())
    historical = json.loads((C / "freeze/historical_checkpoint_audit.json").read_text())
    scheduler = json.loads((C / "optimizer_schedule/formal_scheduler_values.json").read_text())
    historical_rows = final["historical_inputs"] + final["artifacts"] + historical["checkpoints"] + historical["selected_checkpoints"]
    historical_changed = [row["path"] for row in historical_rows if not artifact_ok(row)]
    train_case_changed = [row["record_id"] for row in train_cache["cases"] if not artifact_ok(row)]
    val_case_changed = [row["record_id"] for row in val_cache["cases"] if not artifact_ok(row)]
    assigned = [row["record_id"] for row in schedule["assignments"]]
    batch_records = [item["record_id"] for batch in schedule["base_batches"] for item in batch["records"]]
    optimizer_ok = len(scheduler["rows"]) == 1501 and abs(scheduler["rows"][0]["learning_rate"] - 1e-6) < 1e-20 \
        and abs(scheduler["rows"][40]["learning_rate"] - 1e-5) < 1e-20 and abs(scheduler["rows"][1500]["learning_rate"] - 1e-6) < 1e-20
    checks = {
        "stage07c_authorization": final["status"] == "FORMAL_RETRAINING_PROTOCOL_AND_FRESH_VALIDATION_PREFLIGHT_READY" and final["stage07d_authorized"],
        "protocol_hash_exact": final["protocol_sha256"] == PROTOCOL and protocol_manifest["protocol_sha256"] == PROTOCOL and sha(ROOT / protocol_manifest["protocol_path"]) == PROTOCOL,
        "scale_exact": scale["s_a_v2"] == SCALE and scale["scale_v2_hash"] == SCALE_HASH,
        "target_manifest_exact": sha(target) == TARGET_HASH,
        "historical_hashes_unchanged": not historical_changed,
        "stage06c_590_checkpoints_unchanged": historical["stage06c_checkpoint_count"] == 590 and not [x for x in historical["checkpoints"] if not artifact_ok(x)],
        "stage06c_9_selected_unchanged": historical["stage06c_selected_count"] == 9 and not [x for x in historical["selected_checkpoints"] if not artifact_ok(x)],
        "TRAIN_V2_896": train_cache["case_count"] == 896 and len(assigned) == len(set(assigned)) == 896 and not train_case_changed,
        "eight_112_batches_exact_once": len(schedule["base_batches"]) == 8 and all(x["record_count"] == 112 for x in schedule["base_batches"]) and sorted(batch_records) == sorted(assigned),
        "FRESH_VALIDATION_V2_256": val_cache["case_count"] == 256 and len({x["record_id"] for x in val_cache["cases"]}) == 256 and not val_case_changed,
        "nine_run_identities": [x["run_id"] for x in models["runs"]] == RUN_IDS and all(x["protocol_sha256"] == PROTOCOL and x["scale_hash"] == SCALE_HASH and x["target_manifest_sha256"] == TARGET_HASH for x in models["runs"]),
        "optimizer_scheduler_identity": optimizer_ok,
        "checkpoint_selection_identity": policy["selection_metric"] == "FRESH_VALIDATION_V2.global_balanced_Q_def_v2" and policy["minimum_selectable_update"] == 320 and policy["tie_break"] == "earlier_update",
        "success_gates_frozen": gates["B_TRAIN_V2_global_Q_def_v2_max"] == .5 and gates["C_FRESH_VALIDATION_V2_global_Q_def_v2_max"] == .9
            and all(value == 1.0 for value in gates["D_per_fresh_lineage_Q_def_v2_max"].values()) and gates["arm_pass"] == ">=2/3 seeds",
        "consumed_validation_unread": denial["consumed_validation_private_reads"] == 0,
        "original_sealed_test_denied": denial["pass"] and all(value == 0 for value in denial["decode_counts"].values()),
        "formal_counts_zero_before_start": final["formal_optimizer_steps"] == final["formal_parameter_updates"] == final["formal_training_runs"] == 0,
    }
    record = {"schema": "sph-pio-poc.stage07d.input-freeze.v1", "authorization": final["status"],
        "protocol_sha256": PROTOCOL, "scale_v2": SCALE, "scale_hash": SCALE_HASH, "target_manifest_sha256": TARGET_HASH,
        "run_ids": RUN_IDS, "checks": checks, "historical_changed": historical_changed,
        "train_case_changed": train_case_changed, "validation_case_changed": val_case_changed,
        "sealed_decode_counts": denial["decode_counts"], "formal_optimizer_steps_before_freeze": 0,
        "formal_training_runs_before_freeze": 0, "pass": all(checks.values())}
    write(D / "freeze/stage07d_input_freeze_record.json", record)
    write(MANIFESTS / "stage07d_input_freeze_manifest.json", record)
    inventory = {"schema": "sph-pio-poc.stage07d.run-inventory.v1", "protocol_sha256": PROTOCOL,
        "execution": "strict_serial_fresh_OS_process_per_run", "run_order": RUN_IDS, "runs": models["runs"],
        "replacement_seeds": False, "additional_runs": False, "pass": checks["nine_run_identities"]}
    write(MANIFESTS / "stage07d_run_inventory_manifest.json", inventory); write(D / "manifests/stage07d_run_inventory_manifest.json", inventory)
    (REPORTS / "stage07d_freeze_and_scope.md").write_text(
        "# Stage07D Freeze and Scope\n\nUnique authorization: `FORMAL_RETRAINING_PROTOCOL_AND_FRESH_VALIDATION_PREFLIGHT_READY`. "
        f"Protocol `{PROTOCOL}` and scale `{SCALE}` / `{SCALE_HASH}` are exact. TRAIN_V2 is 896/896; "
        "FRESH_VALIDATION_V2 is 256/256; the frozen schedule is 8×112. Stage06C 590 checkpoints and nine selected hashes remain unchanged. "
        "Consumed validation private reads and original sealed-test decode/evaluation counts are zero. Pre-step freeze PASS: " + str(record["pass"]) + ".\n", encoding="utf-8")
    (REPORTS / "stage07d_execution_control.md").write_text(
        "# Stage07D Execution Control\n\nRuns execute in the frozen order, one fresh OS process at a time. No replacement seed, restart, parallel training, budget extension, rollout, old validation read, or sealed-test evaluation is permitted.\n", encoding="utf-8")
    print(json.dumps({"event": "stage07d_freeze", "pass": record["pass"], "checks": checks}, sort_keys=True))
    if not record["pass"]: raise SystemExit("FORMAL_TRAIN_V2_RETRAINING_EVIDENCE_INCOMPLETE")

if __name__ == "__main__": main()
