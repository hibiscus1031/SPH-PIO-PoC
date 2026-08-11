"""Freeze and verify every Stage 06C input before the first formal update."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import sys
from typing import Any

import torch


HERE = Path(__file__).resolve()
STAGE06C = HERE.parents[1]
STAGE06 = HERE.parents[3]
ROOT = HERE.parents[4]
STAGE06B = STAGE06 / "02_training_protocol/stage06b"
REPORTS = STAGE06 / "08_reports"
MANIFESTS = STAGE06 / "09_manifests"
PROTOCOL = STAGE06B / "contracts/formal_k1_defect_training_protocol_v0_1.yaml"
EXPECTED_PROTOCOL = "sha256:b7918bde82b104895b6d47c798801608938c661c3f8b249f4c832c98c3a83cbe"
RUN_IDS = [f"{arm}_seed{seed}" for arm in ("D1", "D2", "D3") for seed in (20600611, 20600612, 20600613)]


def sha_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def import_path(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def verify_artifacts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    changed = []
    for row in rows:
        path = ROOT / row["path"]
        if not path.is_file():
            changed.append({"path": row["path"], "reason": "missing"})
            continue
        actual = sha_file(path)
        if actual != row["sha256"]:
            changed.append({"path": row["path"], "reason": "sha256", "expected": row["sha256"], "actual": actual})
    return changed


def main() -> None:
    for name in (
        "freeze", "execution_control", "access_control", "checkpoints", "training_histories",
        "validation_histories", "checkpoint_selection", "checkpoint_integrity", "postfit_structure",
        "determinism", "resources", "qualification", "manifests", "results",
    ):
        (STAGE06C / name).mkdir(parents=True, exist_ok=True)
    for run_id in RUN_IDS:
        (STAGE06C / "runs" / run_id).mkdir(parents=True, exist_ok=True)

    protocol_hash = sha_file(PROTOCOL)
    final06b = json.loads((MANIFESTS / "stage06b_final_manifest.json").read_text())
    freeze06a = json.loads((MANIFESTS / "stage06a_input_freeze_manifest.json").read_text())
    final06a = json.loads((MANIFESTS / "stage06a_final_manifest.json").read_text())
    schedule = json.loads((STAGE06B / "train_batch_schedule/formal_train_batch_schedule.json").read_text())
    validation = json.loads((MANIFESTS / "stage06b_validation_manifest.json").read_text())
    target = json.loads((ROOT / "stage_05_Scale_Aware_Discrete_Defect_Training/09_manifests/stage05b_target_manifest.json").read_text())
    model_seed = json.loads((MANIFESTS / "stage06b_model_seed_manifest.json").read_text())
    preflight = json.loads((MANIFESTS / "stage06b_preflight_manifest.json").read_text())

    historical_changed = verify_artifacts(freeze06a["historical_artifacts"])
    stage06a_changed = verify_artifacts(final06a["artifacts"])
    stage06b_changed = verify_artifacts(final06b["artifacts"])

    access = import_path("stage06c_freeze_access", STAGE06B / "access_control/stage06b_access.py")
    sealed_paths = [
        access.SEALED_ROOT / "lcdf_03_variant_main_n8.npz",
        access.SEALED_ROOT / "lcdf_03_variant_main_n8.json",
        access.SEALED_ROOT / "lcdf_10_variant_main_n8.npz",
        access.SEALED_ROOT / "lcdf_10_variant_main_n8.json",
    ]
    denial_rows = []
    for path in sealed_paths:
        try:
            access.read_for_actor("trainer", path)
            denied = False
        except (PermissionError, OSError):
            denied = True
        denial_rows.append({"path": str(path.relative_to(ROOT)), "denied_before_payload_read": denied})

    existing_formal_checkpoints = sorted(str(p.relative_to(ROOT)) for p in (STAGE06C / "checkpoints").glob("*.pt"))
    run_rows = model_seed["runs"]
    expected_order = [row["run_id"] for row in run_rows]
    schedule_counts = {run_id: sum(row["run_id"] == run_id for row in schedule["update_schedule"]) for run_id in RUN_IDS}
    gates = {
        "stage06b_authorization_exact": final06b["status"] == "FORMAL_TRAINING_PROTOCOL_AND_VALIDATION_PREFLIGHT_READY" and final06b["Stage06C_authorized"],
        "protocol_hash_exact": protocol_hash == EXPECTED_PROTOCOL == final06b["protocol_sha256"],
        "stage06b_complete": final06b["complete"] is True,
        "historical_stage01_05_unchanged": not historical_changed and len(freeze06a["historical_artifacts"]) == 3700,
        "stage06a_unchanged": not stage06a_changed and sha_file(MANIFESTS / "stage06a_final_manifest.json") == "sha256:c7e15ed4fc3a285e50a7ffc687d506807a66d25324bb1c9d90323cc849707219",
        "stage06b_artifacts_unchanged": not stage06b_changed,
        "train_384": target["record_count"] == 384 and len(target["records"]) == 384,
        "validation_128": validation["pass"] is True and validation["record_count"] == 128 and len(validation["records"]) == 128,
        "batch_schedule_exact": schedule["pass"] is True and schedule["record_count"] == 384 and all(v == 1500 for v in schedule_counts.values()),
        "nine_run_order_exact": expected_order == RUN_IDS and model_seed["pass"] is True,
        "formal_lr_exact": all(row["formal_learning_rate"] == 1.0e-5 for row in run_rows),
        "formal_backend_exact": all(row["backend"] == "CPU_FLOAT64_SDPBackend.MATH" for row in run_rows),
        "fresh_initialization_only": all(row["historical_weight_reads"] == 0 and row["qualification_weight_reads"] == 0 for row in run_rows),
        "preflight_9_of_9": preflight["pass"] is True and preflight["passed"] == 9,
        "preflight_weights_not_reused": not existing_formal_checkpoints,
        "sealed_denial_all": all(row["denied_before_payload_read"] for row in denial_rows),
        "sealed_decode_counts_zero": all(access.COUNTS[key] == 0 for key in access.COUNTS if key.startswith("sealed_")),
        "formal_steps_still_zero": final06b["formal_optimizer_steps"] == 0 and final06b["formal_parameter_updates"] == 0,
    }
    passed = all(gates.values())
    result = {
        "schema": "sph-pio-poc.stage06c.input-freeze.v1",
        "status": "STAGE06C_INPUTS_FROZEN" if passed else "FORMAL_K1_TRAINING_EVIDENCE_INCOMPLETE",
        "protocol_sha256": protocol_hash,
        "stage06b_authorization": final06b["status"],
        "run_ids": RUN_IDS,
        "formal_seeds": [20600611, 20600612, 20600613],
        "formal_learning_rate": 1.0e-5,
        "train_record_count": 384,
        "validation_record_count": 128,
        "historical_stage01_05_count": len(freeze06a["historical_artifacts"]),
        "stage06a_artifact_count": len(final06a["artifacts"]),
        "stage06b_artifact_count": len(final06b["artifacts"]),
        "historical_changes": historical_changed,
        "stage06a_changes": stage06a_changed,
        "stage06b_changes": stage06b_changed,
        "stage05_failure_hashes": final06b["stage05c_failure_hashes_preserved"] + final06b["stage05cq_failure_hashes_preserved"],
        "architecture_hashes": {row["arm"]: row["architecture_sha256"] for row in run_rows},
        "scale_sha256": run_rows[0]["scale_sha256"],
        "backend": "CPU_FLOAT64_SDPBackend.MATH",
        "environment": {"python": sys.version, "torch": torch.__version__, "platform": platform.platform()},
        "sealed_denial": denial_rows,
        "sealed_decode_counts": {key: value for key, value in access.COUNTS.items() if key.startswith("sealed_")},
        "sealed_test_evaluations": 0,
        "existing_formal_checkpoints_before_freeze": existing_formal_checkpoints,
        "gates": gates,
        "pass": passed,
    }
    write_json(STAGE06C / "freeze/stage06c_input_freeze_record.json", result)
    write_json(MANIFESTS / "stage06c_input_freeze_manifest.json", result)
    write_json(STAGE06C / "manifests/stage06c_input_freeze_manifest.json", result)
    inventory = {
        "schema": "sph-pio-poc.stage06c.run-inventory.v1", "protocol_sha256": protocol_hash,
        "execution": "single_process_serial", "run_count": 9, "runs": run_rows,
        "order": RUN_IDS, "updates_per_run_max": 1500, "schedule_counts": schedule_counts,
        "additional_runs_allowed": False, "pass": passed and expected_order == RUN_IDS,
    }
    write_json(MANIFESTS / "stage06c_run_inventory_manifest.json", inventory)
    write_json(STAGE06C / "manifests/stage06c_run_inventory_manifest.json", inventory)
    write_json(STAGE06C / "access_control/pre_training_sealed_denial_audit.json", {
        "rows": denial_rows, "sealed_decode_counts": result["sealed_decode_counts"],
        "sealed_test_evaluations": 0, "pass": gates["sealed_denial_all"] and gates["sealed_decode_counts_zero"],
    })
    write_json(STAGE06C / "execution_control/campaign_state.json", {
        "schema": "sph-pio-poc.stage06c.campaign-state.v1", "status": "READY" if passed else "BLOCKED",
        "protocol_sha256": protocol_hash, "next_run_index": 0, "formal_optimizer_steps": 0,
        "formal_parameter_updates": 0, "formal_training_runs": 0, "sealed_test_evaluations": 0,
    })
    write_text(REPORTS / "stage06c_freeze_and_scope.md", f"""# Stage 06C Freeze and Scope

Unique authorization: Stage06B `FORMAL_TRAINING_PROTOCOL_AND_VALIDATION_PREFLIGHT_READY`.

Protocol: `{protocol_hash}`. Formal LR: `1.0e-5`. Seeds: `20600611`, `20600612`, `20600613`. The fixed nine-run order is `{', '.join(RUN_IDS)}`. TRAIN is 384 records and VALIDATION is 128 records; SEALED_TEST remains closed. Historical Stage01–05, Stage06A, and Stage06B artifact verification is `{'PASS' if passed else 'FAIL'}`. No preflight weight was reused and no formal optimizer step was performed by this freeze operation.

Freeze status: **{result['status']}**
""")
    write_text(REPORTS / "stage06c_execution_control.md", f"""# Stage 06C Execution Control

Execution is locked to one CPU process, float64, explicit `SDPBackend.MATH`, and the frozen order `{', '.join(RUN_IDS)}`. AdamW, scheduler, clipping, zero-grad, batch order, 1500-update budget, 20-update evaluation/checkpoint cadence, selection at update >=320, and early stopping are consumed from Stage06B without reinterpretation. Scientific retry, replacement seeds, parallel runs, rollout, and SEALED_TEST access are forbidden.

Ready for formal steps: **{passed}**
""")
    print(json.dumps({"status": result["status"], "protocol": protocol_hash, "gates": gates}, sort_keys=True))
    if not passed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
