#!/usr/bin/env python3
"""Freeze Stage 02L inputs and preregistered protocol without reading record arrays."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[4]
STAGE = REPO / "stage_02_Particle_Interaction_Operator"
ROOT = STAGE / "06_model/pair_force_pio_training_protocol_v0_1"
K = STAGE / "06_model/pair_force_pio_architecture_v0_1"
DATA = STAGE / "05_dataset/blind_multifamily_pair_scope_v1_0"


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    protocol_path = ROOT / "freeze/training_protocol_v0_1.yaml"
    protocol = yaml.safe_load(protocol_path.read_text())
    k_summary = json.loads((K / "results/stage02k_qualification_summary.json").read_text())
    dataset_manifest = json.loads((DATA / "manifests/stage02jw_dataset_manifest.json").read_text())
    inventory = json.loads((DATA / "canonical_records/canonical_inventory.json").read_text())
    split = json.loads((DATA / "splits/prefrozen_split_manifest.json").read_text())
    normalization_path = DATA / "normalization/train_only_graph_balanced_statistics.json"
    normalization = json.loads(normalization_path.read_text())
    if k_summary.get("status") != "PAIR_FORCE_PIO_ARCHITECTURE_QUALIFIED" or not k_summary.get("stage02l_authorized"):
        raise RuntimeError("Stage 02K authorization missing")
    if dataset_manifest.get("dataset_collection") != "blind_multifamily_pair_scope_v1_0":
        raise RuntimeError("collection mismatch")
    if split.get("counts") != {"future_train": 10, "future_validation": 5, "future_test": 5}:
        raise RuntimeError("split mismatch")
    expected_norm = "sha256:2208d2f4b9b7c848f2cd1b93624f9f6a3d9fb29e65cdd70ee453e6122c43d051"
    if normalization.get("statistics_hash") != expected_norm:
        raise RuntimeError("normalization statistics hash mismatch")
    runs = protocol["run_matrix"]["runs"]
    if len(runs) != 9 or {x["architecture"] for x in runs} != {"K0", "K1", "K2"}:
        raise RuntimeError("run matrix incomplete")
    inputs = [
        STAGE / "07_reports/stage02k_final_report.md",
        K / "contracts/architecture_contract_v0_1.json",
        K / "implementations/pair_force_models.py",
        K / "contracts/feature_contract_v0_1.json",
        K / "contracts/dataset_loader_identity_audit.json",
        K / "symmetry_tests/symmetry_equivariance_results.json",
        K / "conservation_tests/conservation_results.json",
        K / "differentiability/differentiability_results.json",
        K / "resource_audit/resource_results.json",
        K / "results/stage02k_qualification_summary.json",
        K / "freeze/stage02k_input_and_architecture_freeze_manifest.json",
        DATA / "manifests/stage02jw_final_manifest.json",
        DATA / "manifests/stage02jw_dataset_manifest.json",
        DATA / "canonical_records/canonical_inventory.json",
        DATA / "splits/prefrozen_split_manifest.json",
        normalization_path,
        DATA / "eligibility/record_eligibility_results.json",
        STAGE / "04_target_attribution/conservation_closure/freeze/stage02ir_scope_and_decision_rules.yaml",
        STAGE / "07_reports/stage02ir_pair_representability.md",
    ]
    manifest = {
        "manifest_version": "stage02l-input-protocol-freeze-1.0.0",
        "created_before_any_stage02l_target_validation_or_test_array_decode": True,
        "protocol_file": str(protocol_path.relative_to(REPO)),
        "protocol_sha256": sha(protocol_path),
        "protocol_immutable": True,
        "architecture_hash": k_summary["architecture_hash"],
        "collection_id": dataset_manifest["dataset_collection"],
        "record_schema_compatibility_identifier": "controlled_regular_pair_scope_v0_1",
        "split_counts": split["counts"],
        "normalization_statistics_hash": normalization["statistics_hash"],
        "canonical_records": [
            {"case_id": row["case_id"], "path": row["canonical_path"], "sha256": row["canonical_sha256"], "split_role": row["split_role"]}
            for row in inventory["rows"]
        ],
        "input_files": [{"path": str(path.relative_to(REPO)), "sha256": sha(path), "byte_count": path.stat().st_size} for path in inputs],
        "model_arms_frozen": ["K0", "K1", "K2"],
        "training_seeds_frozen": [20261201, 20261202, 20261203],
        "prospective_run_count": 9,
        "test_target_access": False,
        "optimizer_steps": 0,
        "training_runs": 0,
        "no_record_array_decode_by_this_script": True,
        "status": "PASS",
    }
    path = ROOT / "freeze/stage02l_input_and_protocol_freeze_manifest.json"
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    (ROOT / "freeze/training_protocol_v0_1.sha256").write_text(f"{manifest['protocol_sha256'].removeprefix('sha256:')}  training_protocol_v0_1.yaml\n")
    print(json.dumps({"protocol_sha256": manifest["protocol_sha256"], "inputs": len(inputs), "records": len(inventory["rows"]), "status": "PASS"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
