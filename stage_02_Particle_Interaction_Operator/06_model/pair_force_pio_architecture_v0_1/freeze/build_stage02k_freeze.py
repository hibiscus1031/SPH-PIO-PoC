#!/usr/bin/env python3
"""Freeze Stage 02K inputs and architecture before any record-array access."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
STAGE = REPO / "stage_02_Particle_Interaction_Operator"
ROOT = STAGE / "06_model/pair_force_pio_architecture_v0_1"


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def main() -> int:
    inventory_path = STAGE / "05_dataset/blind_multifamily_pair_scope_v1_0/canonical_records/canonical_inventory.json"
    inventory = json.loads(inventory_path.read_text())
    final_manifest_path = STAGE / "05_dataset/blind_multifamily_pair_scope_v1_0/manifests/stage02jw_final_manifest.json"
    dataset_manifest_path = STAGE / "05_dataset/blind_multifamily_pair_scope_v1_0/manifests/stage02jw_dataset_manifest.json"
    final_manifest = json.loads(final_manifest_path.read_text())
    dataset_manifest = json.loads(dataset_manifest_path.read_text())
    if final_manifest["status"] != "BLIND_MULTIFAMILY_DATASET_READY" or not final_manifest["stage02k_authorized"]:
        raise RuntimeError("Stage 02J-W does not authorize Stage 02K")
    if dataset_manifest["dataset_collection"] != "blind_multifamily_pair_scope_v1_0":
        raise RuntimeError("collection identity mismatch")
    architecture_files = [
        ROOT / "contracts/architecture_contract_v0_1.json",
        ROOT / "contracts/feature_contract_v0_1.json",
        ROOT / "implementations/pair_force_models.py",
    ]
    architecture_entries = [
        {"path": str(p.relative_to(REPO)), "sha256": sha(p), "byte_count": p.stat().st_size}
        for p in architecture_files
    ]
    architecture_hash = "sha256:" + hashlib.sha256(canonical(architecture_entries)).hexdigest()
    inputs = [
        STAGE / "07_reports/stage02jw_final_report.md",
        final_manifest_path,
        dataset_manifest_path,
        inventory_path,
        STAGE / "05_dataset/blind_multifamily_pair_scope_v1_0/eligibility/record_eligibility_results.json",
        STAGE / "05_dataset/blind_multifamily_pair_scope_v1_0/leakage/leakage_graph.json",
        STAGE / "05_dataset/blind_multifamily_pair_scope_v1_0/splits/prefrozen_split_manifest.json",
        STAGE / "05_dataset/blind_multifamily_pair_scope_v1_0/normalization/train_only_graph_balanced_statistics.json",
        STAGE / "05_dataset/blind_multifamily_pair_scope_v1_0/eligibility_contract/blind_dataset_eligibility_contract_v1_0.yaml",
        STAGE / "05_dataset/controlled_regular_pair_scope_v0_1/schema/feature_permission_table.yaml",
        STAGE / "05_dataset/controlled_regular_pair_scope_v0_1/schema/stage02j_graph_record_schema.json",
        STAGE / "05_dataset/controlled_regular_pair_scope_v0_1/schema/canonical_serialization_contract.yaml",
        STAGE / "05_dataset/controlled_regular_pair_scope_v0_1/manifests/run_stage02j_controlled_dataset.py",
        STAGE / "04_target_attribution/conservation_closure/architecture_scope/architecture_scope_decision.json",
        STAGE / "07_reports/stage02a_conservation_contract.md",
        STAGE / "07_reports/stage02a_equivariance_contract.md",
    ]
    manifest = {
        "manifest_version": "stage02k-freeze-1.0.0",
        "created_before_canonical_record_decode": True,
        "created_before_validation_test_or_target_array_access": True,
        "authorization": "Stage02J-W:BLIND_MULTIFAMILY_DATASET_READY",
        "collection_id": "blind_multifamily_pair_scope_v1_0",
        "schema_compatibility_identifier": "controlled_regular_pair_scope_v0_1",
        "record_count": len(inventory["rows"]),
        "canonical_records": [
            {
                "case_id": row["case_id"],
                "path": row["canonical_path"],
                "sha256": row["canonical_sha256"],
                "split_role": row["split_role"],
            }
            for row in inventory["rows"]
        ],
        "inputs": [
            {"path": str(p.relative_to(REPO)), "sha256": sha(p), "byte_count": p.stat().st_size}
            for p in inputs
        ],
        "architecture_files": architecture_entries,
        "architecture_hash": architecture_hash,
        "architecture_frozen": True,
        "no_target_arrays_read_by_this_script": True,
        "status": "PASS",
    }
    path = ROOT / "freeze/stage02k_input_and_architecture_freeze_manifest.json"
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"architecture_hash": architecture_hash, "records": len(inventory["rows"]), "status": "PASS"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
