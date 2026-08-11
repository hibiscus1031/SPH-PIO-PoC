"""Freeze Stage 06C-R inputs and diagnostic decision rules without opening checkpoints."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve()
STAGE06CR = HERE.parents[1]
STAGE06 = HERE.parents[3]
ROOT = HERE.parents[4]
STAGE06C = STAGE06 / "03_formal_training/stage06c"
REPORTS = STAGE06 / "08_reports"
MANIFESTS = STAGE06 / "09_manifests"
PROTOCOL = "sha256:b7918bde82b104895b6d47c798801608938c661c3f8b249f4c832c98c3a83cbe"
RUN_IDS = [f"{arm}_seed{seed}" for arm in ("D1", "D2", "D3") for seed in (20600611, 20600612, 20600613)]
SUBDIRS = [
    "freeze", "complete_history", "checkpoint_trajectory", "train_lineage_decomposition",
    "validation_decomposition", "origin_difficulty", "learning_rate_evidence", "optimizer_dynamics",
    "parameter_displacement", "coefficient_dynamics", "gradient_alignment", "capacity_diagnostics",
    "checkpoint_selection_tension", "attribution", "future_protocol", "resources", "manifests", "results",
]


def sha_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(value.rstrip() + "\n", encoding="utf-8")
    os.replace(tmp, path)


def main() -> None:
    for name in SUBDIRS:
        (STAGE06CR / name).mkdir(parents=True, exist_ok=True)
    final06c_path = MANIFESTS / "stage06c_final_manifest.json"
    report06c_path = REPORTS / "stage06c_final_report.md"
    final06c = json.loads(final06c_path.read_text())
    checkpoint_manifest_path = MANIFESTS / "stage06c_checkpoint_manifest.json"
    checkpoint_manifest = json.loads(checkpoint_manifest_path.read_text())
    selected_manifest_path = MANIFESTS / "stage06c_selected_checkpoint_manifest.json"
    selected_manifest = json.loads(selected_manifest_path.read_text())
    input06c = json.loads((STAGE06C / "freeze/stage06c_input_freeze_record.json").read_text())
    required_status = "FORMAL_K1_TRAINING_COMPLETE_TRANSFORMER_NOT_QUALIFIED"
    gates = {
        "stage06c_status_preserved": final06c.get("status") == required_status,
        "stage06d_false": final06c.get("Stage06D_authorized") is False,
        "protocol_exact": final06c.get("protocol_sha256") == PROTOCOL,
        "nine_run_ids_exact": final06c.get("run_ids") == RUN_IDS,
        "optimizer_steps_11620": final06c.get("formal_optimizer_steps") == 11620,
        "checkpoint_inventory_590": checkpoint_manifest.get("checkpoint_count") == 590,
        "selected_inventory_9": selected_manifest.get("selected_count") == 9,
        "selected_hashes_closed": bool(selected_manifest.get("hashes_closed")),
        "sealed_counts_zero": all(value == 0 for value in final06c.get("sealed_decode_counts", {}).values()),
        "sealed_evaluations_zero": final06c.get("sealed_test_evaluations") == 0,
        "rollouts_zero": final06c.get("rollouts") == 0,
        "historical_audit_pass": final06c.get("historical_audit", {}).get("pass") is True,
    }
    freeze = {
        "schema": "sph-pio-poc.stage06cr.input-freeze.v1",
        "status": "STAGE06CR_INPUTS_AND_RULES_FROZEN" if all(gates.values()) else "STAGE06CR_INPUT_FREEZE_FAILED",
        "pass": all(gates.values()),
        "stage06c_verdict_required": required_status,
        "stage06c_verdict_unchanged": final06c["status"],
        "Stage06D_authorized": False,
        "SEALED_TEST": "CLOSED",
        "protocol_sha256": PROTOCOL,
        "frozen_inputs": {
            "stage06c_final_manifest": {"path": str(final06c_path.relative_to(ROOT)), "sha256": sha_file(final06c_path)},
            "stage06c_final_report": {"path": str(report06c_path.relative_to(ROOT)), "sha256": sha_file(report06c_path)},
            "stage06c_checkpoint_manifest": {"path": str(checkpoint_manifest_path.relative_to(ROOT)), "sha256": sha_file(checkpoint_manifest_path)},
            "stage06c_selected_checkpoint_manifest": {"path": str(selected_manifest_path.relative_to(ROOT)), "sha256": sha_file(selected_manifest_path)},
            "stage06b_protocol": PROTOCOL,
            "run_ids": RUN_IDS,
            "optimizer_steps": 11620,
            "checkpoint_count": 590,
            "checkpoint_identities": checkpoint_manifest["checkpoints"],
            "selected_checkpoint_identities": selected_manifest["checkpoints"],
            "train_record_count": input06c["train_record_count"],
            "validation_record_count": input06c["validation_record_count"],
            "stage05_failure_hashes": input06c["stage05_failure_hashes"],
        },
        "diagnostic_rules_frozen_before_result_read": {
            "checkpoint_selection_tension": {
                "best_train_better_than_selected_by_Q_at_least": 0.02,
                "best_train_validation_worse_than_selected_by_Q_at_least": 0.01,
            },
            "update_scale": {
                "too_small_median_relative_step_below": 1e-6,
                "too_small_total_path_relative_below": 0.02,
                "stall_absolute_train_Q_slope_per_update_at_most": 1e-5,
                "stall_gradient_RMS_above": 1e-4,
                "coefficient_saturation_fraction_at_least": 0.10,
            },
            "plateau": {
                "progress_train_Q_slope_per_update_below": -1e-5,
                "flat_absolute_train_Q_slope_per_update_at_most": 1e-5,
                "flat_absolute_validation_Q_slope_per_update_at_most": 1e-5,
                "windows_updates": [200, 400],
            },
            "lineage_labels": {
                "persistent_hard_mean_Q_above": 0.75,
                "seed_sensitive_coefficient_of_variation_above": 0.15,
                "architecture_sensitive_arm_mean_range_above": 0.10,
            },
            "local_tangent": {
                "high_reducibility_fraction_at_least": 0.50,
                "low_reducibility_fraction_below": 0.20,
                "head_direction_count": 64,
                "full_network_direction_count": 64,
                "preregistered_cases_per_lineage_variant": 1,
            },
            "origin_correlation": {"material_absolute_correlation_at_least": 0.30},
        },
        "activity_counters_at_entry": {
            "new_optimizer_steps": 0,
            "new_parameter_updates": 0,
            "new_training_runs": 0,
            "sealed_test_evaluations": 0,
            "rollouts": 0,
        },
        "gates": gates,
    }
    write_json(STAGE06CR / "freeze/stage06cr_input_freeze_record.json", freeze)
    write_json(MANIFESTS / "stage06cr_input_freeze_manifest.json", freeze)
    write_json(STAGE06CR / "manifests/stage06cr_input_freeze_manifest.json", freeze)
    report = f"""# Stage 06C-R Freeze and Scope

Stage06C remains **{final06c['status']}** and Stage06D authorization remains **false**. Protocol `{PROTOCOL}`, nine run identities, 11,620 historical updates, 590 checkpoint identities, nine selected hashes, TRAIN/VALIDATION identities, and the ten historical failure hashes are frozen.

This stage is post-hoc diagnosis only. It permits checkpoint loading, forward evaluation, gradients/Jacobian-vector products without writeback, and history substitutions on disposable in-memory diagnostic models. It forbids any optimizer update, persistent parameter mutation, new training run, new checkpoint, rollout, sealed decode/evaluation, gate change, or checkpoint reselection.

The selection-tension, update-scale, plateau, lineage, tangent-reducibility, and correlation thresholds were frozen in `stage06cr_input_freeze_manifest.json` before checkpoint payloads or result curves were inspected by the Stage06C-R runner.

Freeze PASS: **{freeze['pass']}**. SEALED_TEST: **CLOSED**. New optimizer steps, parameter updates, training runs, sealed evaluations, and rollouts are all fixed at zero.
"""
    write_text(REPORTS / "stage06cr_freeze_and_scope.md", report)
    if not freeze["pass"]:
        raise SystemExit("Stage06C-R input freeze failed")
    print(json.dumps({"status": freeze["status"], "pass": freeze["pass"], "checkpoint_count": 590}, sort_keys=True))


if __name__ == "__main__":
    main()
