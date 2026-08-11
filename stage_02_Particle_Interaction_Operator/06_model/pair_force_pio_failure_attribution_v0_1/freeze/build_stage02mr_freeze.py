#!/usr/bin/env python3
"""Freeze Stage 02M-R historical inputs before any new numerical diagnostic."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
STAGE = REPO / "stage_02_Particle_Interaction_Operator"
ROOT = STAGE / "06_model/pair_force_pio_failure_attribution_v0_1"
MROOT = STAGE / "06_model/pair_force_pio_static_fitting_v0_1"
LROOT = STAGE / "06_model/pair_force_pio_training_protocol_v0_1"
KROOT = STAGE / "06_model/pair_force_pio_architecture_v0_1"
JROOT = STAGE / "05_dataset/blind_multifamily_pair_scope_v1_0"


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return str(path.relative_to(REPO))


def add_tree(files: set[Path], root: Path) -> None:
    files.update(path for path in root.rglob("*") if path.is_file() and "__pycache__" not in path.parts)


files: set[Path] = {
    STAGE / "07_reports/stage02m_final_report.md",
    MROOT / "results/stage02m_qualification_summary.json",
    MROOT / "results/frozen_success_gate_evaluation.json",
    MROOT / "test_evaluation/sealed_test_evaluation_manifest.json",
    MROOT / "test_seal/test_release_manifest.json",
    MROOT / "manifests/training_validation_summary_manifest.json",
    MROOT / "manifests/stage02m_run_manifest.json",
    MROOT / "freeze/stage02m_execution_freeze_manifest.json",
    LROOT / "freeze/training_protocol_v0_1.yaml",
    LROOT / "manifests/stage02l_run_manifest.json",
    KROOT / "contracts/architecture_contract_v0_1.json",
    KROOT / "contracts/feature_contract_v0_1.json",
    KROOT / "results/stage02k_qualification_summary.json",
    JROOT / "manifests/stage02jw_dataset_manifest.json",
    JROOT / "splits/prefrozen_split_manifest.json",
    JROOT / "normalization/train_only_graph_balanced_statistics.json",
    JROOT / "canonical_records/canonical_inventory.json",
    STAGE / "05_dataset/controlled_regular_pair_scope_v0_1/schema/feature_permission_table.yaml",
    ROOT / "freeze/diagnostic_contract_v0_1.json",
}
add_tree(files, MROOT / "runs")
add_tree(files, MROOT / "checkpoints")
add_tree(files, JROOT / "canonical_records")

missing = sorted(rel(path) for path in files if not path.is_file())
if missing:
    raise FileNotFoundError(missing)

rows = [{"path": rel(path), "sha256": sha(path), "bytes": path.stat().st_size} for path in sorted(files)]
checkpoint_rows = [row for row in rows if "/checkpoints/" in row["path"] and row["path"].endswith(".pt")]
record_rows = [row for row in rows if "/canonical_records/" in row["path"] and row["path"].endswith(".bin")]

terminals = []
selected = []
for architecture in ("K0", "K1", "K2"):
    for seed in (20261201, 20261202, 20261203):
        terminal_path = MROOT / f"runs/{architecture}/seed_{seed}/run_terminal.json"
        terminal = json.loads(terminal_path.read_text())
        terminals.append({
            "run_id": terminal["run_id"],
            "architecture": architecture,
            "seed": seed,
            "optimizer_updates": terminal["total_optimizer_steps"],
            "best_update": terminal["best_validation_update"],
            "stop_reason": terminal["stop_reason"],
            "terminal_state": terminal["terminal_state"],
            "selected_checkpoint": terminal["selected_checkpoint"],
            "selected_checkpoint_hash": terminal["selected_checkpoint_hash"],
        })
        selected.append(terminal["selected_checkpoint_hash"])

expected_updates = [300, 300, 300, 300, 300, 300, 440, 740, 300]
expected_best = [100, 40, 40, 40, 20, 40, 240, 540, 20]
mapping_pass = ([row["optimizer_updates"] for row in terminals] == expected_updates and
                [row["best_update"] for row in terminals] == expected_best)
selected_hash_pass = all(any(row["sha256"] == value for row in checkpoint_rows) for value in selected)

manifest = {
    "manifest_version": "stage02mr-freeze-1.0.0",
    "stage": "02M-R",
    "freeze_timing": "before_new_array_decode_forward_backward_jvp_vjp_or_lsqr",
    "historical_state": {
        "stage02m_verdict": "STATIC_PAIR_FORCE_FITTING_NOT_QUALIFIED",
        "stage02n_authorized": False,
        "historical_optimizer_steps": sum(row["optimizer_updates"] for row in terminals),
        "current_test_status": "consumed_confirmatory_test",
        "test_release_historical": "completed_once",
    },
    "run_order": terminals,
    "expected_optimizer_updates": expected_updates,
    "expected_best_updates": expected_best,
    "checkpoint_count": len(checkpoint_rows),
    "selected_checkpoint_count": len(selected),
    "canonical_record_count": len(record_rows),
    "file_count": len(rows),
    "files": rows,
    "checks": {
        "run_mapping_unique_and_exact": mapping_pass,
        "historical_optimizer_steps_3280": sum(row["optimizer_updates"] for row in terminals) == 3280,
        "checkpoint_count_164": len(checkpoint_rows) == 164,
        "selected_checkpoint_count_9": len(selected) == 9,
        "selected_hashes_present": selected_hash_pass,
        "canonical_record_count_20": len(record_rows) == 20,
    },
}
manifest["status"] = "PASS" if all(manifest["checks"].values()) else "FAIL"
output = ROOT / "freeze/stage02mr_historical_freeze_manifest.json"
output.write_text(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n")
print(json.dumps({"status": manifest["status"], "file_count": len(rows), "checkpoint_count": len(checkpoint_rows), "record_count": len(record_rows)}))
