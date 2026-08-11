#!/usr/bin/env python3
"""Freeze Stage 02M-Q execution inputs before any target decode or optimizer update."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
STAGE = REPO / "stage_02_Particle_Interaction_Operator"
ROOT = STAGE / "06_model/pair_force_pio_static_fitting_v0_2"
P = STAGE / "06_model/pair_force_pio_training_protocol_v0_2"
K = STAGE / "06_model/pair_force_pio_architecture_v0_1"


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


required = {
    STAGE / "07_reports/stage02mp_final_report.md",
    P / "freeze/training_protocol_v0_2.yaml",
    P / "freeze/protocol_v0_2_hash.json",
    P / "target_scale/train_only_supervision_scale.json",
    P / "manifests/v1_1_collection_manifest.json",
    P / "canonical_records/canonical_inventory.json",
    P / "split/prefrozen_split_manifest.json",
    P / "split/family_lineage_registry.json",
    P / "blind_family_generator/blind_family_formulas_v0_2.json",
    P / "test_seal/sealed_test_payload_manifest.json",
    P / "test_seal/test_seal_denial_audit.json",
    P / "test_seal/v02_sealed_loader.py",
    P / "normalization/input_normalization_reuse_verification.json",
    P / "normalization/normalization_code_identity.json",
    P / "results/stage02mp_final_summary.json",
    K / "contracts/architecture_contract_v0_1.json",
    K / "results/stage02k_qualification_summary.json",
    K / "implementations/pair_force_models.py",
    STAGE / "05_dataset/controlled_regular_pair_scope_v0_1/schema/feature_permission_table.yaml",
    P / "conditioning_contract/loss_v0_2.py",
    P / "conditioning_contract/optimizer_conditioning_contract.json",
    P / "success_gates/success_gates_v0_2.json",
    P / "checkpointing/checkpoint_and_stopping_contract.json",
    P / "route_termination/route_termination_contract.json",
    P / "resource_forecast/resource_forecast.json",
    P / "run_matrix/run_matrix_v0_2.json",
}
inventory = json.loads((P / "canonical_records/canonical_inventory.json").read_text())
for row in inventory["rows"]:
    required.add(REPO / row["canonical_path"])
for path in sorted((K / "implementations").glob("*.py")):
    required.add(path)
missing = [str(path) for path in required if not path.is_file()]
if missing:
    raise FileNotFoundError(missing)

protocol_record = json.loads((P / "freeze/protocol_v0_2_hash.json").read_text())
collection = json.loads((P / "manifests/v1_1_collection_manifest.json").read_text())
split = json.loads((P / "split/prefrozen_split_manifest.json").read_text())
scale = json.loads((P / "target_scale/train_only_supervision_scale.json").read_text())
normalization = json.loads((P / "normalization/input_normalization_reuse_verification.json").read_text())
formulas = json.loads((P / "blind_family_generator/blind_family_formulas_v0_2.json").read_text())
mp = json.loads((P / "results/stage02mp_final_summary.json").read_text())
architecture_qualification = json.loads((K / "results/stage02k_qualification_summary.json").read_text())
rows = [{"path": str(path.relative_to(REPO)), "sha256": sha(path), "bytes": path.stat().st_size} for path in sorted(required)]
canonical = [{"case_id": row["case_id"], "family_id": row["family_id"], "split_role": row["split_role"], "path": row["canonical_path"], "sha256": row["canonical_sha256"], "bytes": row["canonical_byte_count"]} for row in inventory["rows"]]
checks = {
    "stage02mp_authorization": mp["status"] == "STATIC_FITTING_PROTOCOL_V02_READY" and mp["Stage_02M_Q_authorized"],
    "collection_id": collection["dataset_collection"] == "blind_multifamily_pair_scope_v1_1_protocol_v02",
    "record_count_20": len(canonical) == 20,
    "record_hashes": all(sha(REPO / row["path"]) == row["sha256"] for row in canonical),
    "split_10_5_5": split["counts"] == {"future_train": 10, "future_validation": 5, "future_test": 5},
    "new_family_identities": {(row["family_id"], row["root_seed"], row["role"]) for row in formulas["families"]} == {("V02_BLIND_VALIDATION_01", 2026080501, "future_validation"), ("V02_BLIND_TEST_01", 2026080502, "future_test")},
    "architecture_hash": architecture_qualification["architecture_hash"] == "sha256:1e313f871b13f3f2fc0cc780ab24d50a7fd9fe8a96866da91fae5ede9ab555a4",
    "protocol_hash": protocol_record["protocol_sha256"] == "sha256:8cd068c5b23eacfbcb2c56846352fd6f3c560b46d8562806e3ed568c278ddb6e" and sha(P / "freeze/training_protocol_v0_2.yaml") == protocol_record["protocol_sha256"],
    "normalization_hash": normalization["statistics_hash"] == "sha256:2208d2f4b9b7c848f2cd1b93624f9f6a3d9fb29e65cdd70ee453e6122c43d051",
    "a_sup": scale["a_sup"] == 0.392220124168075 and scale["units"] == "m s^-2",
    "a_sup_hash": scale["result_hash"] == "sha256:85d5339dde02c29dba5bfa753096ab25598bd29a5df576def7691dcdbfef838e",
    "test_release_absent": not any(ROOT.rglob("test_release_manifest*")),
}
manifest = {
    "manifest_version": "stage02mq-execution-freeze-1.0.0",
    "freeze_timing": "before_target_decode_or_optimizer_update",
    "collection_id": collection["dataset_collection"],
    "architecture_hash": "sha256:1e313f871b13f3f2fc0cc780ab24d50a7fd9fe8a96866da91fae5ede9ab555a4",
    "protocol_hash": protocol_record["protocol_sha256"],
    "input_normalization_hash": normalization["statistics_hash"],
    "a_sup": scale["a_sup"],
    "a_sup_units": scale["units"],
    "a_sup_hash": scale["result_hash"],
    "split_counts": split["counts"],
    "canonical_records": canonical,
    "input_files": rows,
    "checks": checks,
    "historical_boundaries": {"BLIND_FAMILY_03": "consumed_historical_validation_only_excluded", "BLIND_FAMILY_04": "consumed_historical_test_only_excluded"},
}
manifest["status"] = "PASS" if all(checks.values()) else "FAIL"
output = ROOT / "freeze/stage02mq_execution_freeze_manifest.json"
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n")
print(json.dumps({"status": manifest["status"], "input_files": len(rows), "records": len(canonical), "checks": checks}, sort_keys=True))
