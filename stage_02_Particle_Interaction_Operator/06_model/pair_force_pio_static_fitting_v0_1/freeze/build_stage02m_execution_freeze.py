#!/usr/bin/env python3
"""Freeze all Stage 02M execution inputs before target decode or optimizer updates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[4]
STAGE = REPO / "stage_02_Particle_Interaction_Operator"
ROOT = STAGE / "06_model/pair_force_pio_static_fitting_v0_1"
L = STAGE / "06_model/pair_force_pio_training_protocol_v0_1"
K = STAGE / "06_model/pair_force_pio_architecture_v0_1"
DATA = STAGE / "05_dataset/blind_multifamily_pair_scope_v1_0"
PROTOCOL_HASH = "sha256:ab02a49a508c4ddcab5db037886abd329ab29d2eedfc8ffe5d818ad691668648"
ARCHITECTURE_HASH = "sha256:1e313f871b13f3f2fc0cc780ab24d50a7fd9fe8a96866da91fae5ede9ab555a4"
NORMALIZATION_HASH = "sha256:2208d2f4b9b7c848f2cd1b93624f9f6a3d9fb29e65cdd70ee453e6122c43d051"


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    protocol_path = L / "freeze/training_protocol_v0_1.yaml"
    protocol = yaml.safe_load(protocol_path.read_text())
    l_summary = json.loads((L / "results/stage02l_qualification_summary.json").read_text())
    k_summary = json.loads((K / "results/stage02k_qualification_summary.json").read_text())
    dataset_manifest = json.loads((DATA / "manifests/stage02jw_dataset_manifest.json").read_text())
    inventory = json.loads((DATA / "canonical_records/canonical_inventory.json").read_text())
    split = json.loads((DATA / "splits/prefrozen_split_manifest.json").read_text())
    normalization = json.loads((DATA / "normalization/train_only_graph_balanced_statistics.json").read_text())
    test_seal = json.loads((L / "test_seal/test_seal_status.json").read_text())
    checks = {
        "stage02l_authorization": l_summary.get("status") == "STATIC_FITTING_PROTOCOL_READY" and l_summary.get("stage02m_authorized") is True,
        "protocol_hash": sha(protocol_path) == PROTOCOL_HASH == l_summary.get("protocol_sha256"),
        "architecture_hash": k_summary.get("architecture_hash") == ARCHITECTURE_HASH == l_summary.get("architecture_hash"),
        "collection_id": dataset_manifest.get("dataset_collection") == "blind_multifamily_pair_scope_v1_0",
        "record_count": len(inventory.get("rows", [])) == 20,
        "split": split.get("counts") == {"future_train": 10, "future_validation": 5, "future_test": 5},
        "normalization_hash": normalization.get("statistics_hash") == NORMALIZATION_HASH,
        "run_matrix": len(protocol["run_matrix"]["runs"]) == 9,
        "test_target_access_false": test_seal.get("test_target_access") is False,
        "test_release_absent": not (L / "test_seal/test_release_manifest.json").exists(),
        "stage02l_target_decode_zero": l_summary.get("dataset_target_arrays_decoded") == 0,
    }
    if not all(checks.values()):
        raise RuntimeError(f"execution freeze failed: {checks}")
    inputs = [
        STAGE / "07_reports/stage02l_final_report.md",
        protocol_path,
        L / "freeze/stage02l_input_and_protocol_freeze_manifest.json",
        L / "run_matrix/run_matrix.json",
        L / "loss/loss_contract.py",
        L / "loss/loss_static_audit.json",
        L / "optimizer/prospective_optimizer.py",
        L / "optimizer/optimizer_schedule_audit.json",
        L / "static_metrics/static_metric_contract_audit.json",
        L / "success_gates/future_success_gates.json",
        L / "checkpointing/checkpoint_roundtrip_audit.json",
        L / "test_seal/test_seal_status.json",
        L / "results/stage02l_qualification_summary.json",
        K / "implementations/pair_force_models.py",
        K / "contracts/architecture_contract_v0_1.json",
        K / "contracts/feature_contract_v0_1.json",
        DATA / "manifests/stage02jw_dataset_manifest.json",
        DATA / "manifests/stage02jw_final_manifest.json",
        DATA / "canonical_records/canonical_inventory.json",
        DATA / "splits/prefrozen_split_manifest.json",
        DATA / "normalization/train_only_graph_balanced_statistics.json",
        STAGE / "05_dataset/controlled_regular_pair_scope_v0_1/schema/feature_permission_table.yaml",
    ]
    manifest = {
        "manifest_version": "stage02m-execution-freeze-1.0.0",
        "created_before_any_stage02m_target_decode": True,
        "created_before_any_optimizer_step": True,
        "checks": {key: "PASS" if value else "FAIL" for key, value in checks.items()},
        "protocol_sha256": PROTOCOL_HASH,
        "architecture_sha256": ARCHITECTURE_HASH,
        "normalization_statistics_hash": NORMALIZATION_HASH,
        "collection_id": "blind_multifamily_pair_scope_v1_0",
        "split_counts": split["counts"],
        "run_matrix": protocol["run_matrix"]["runs"],
        "canonical_records": [{"case_id": row["case_id"], "path": row["canonical_path"], "sha256": row["canonical_sha256"], "split_role": row["split_role"]} for row in inventory["rows"]],
        "input_files": [{"path": str(path.relative_to(REPO)), "sha256": sha(path), "byte_count": path.stat().st_size} for path in inputs],
        "prefreeze_test_target_decode_count": 0,
        "prefreeze_optimizer_steps": 0,
        "status": "PASS",
    }
    path = ROOT / "freeze/stage02m_execution_freeze_manifest.json"
    if path.exists(): raise FileExistsError(path)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"protocol": PROTOCOL_HASH, "architecture": ARCHITECTURE_HASH, "records": 20, "inputs": len(inputs), "status": "PASS"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
