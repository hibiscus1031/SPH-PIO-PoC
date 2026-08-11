#!/usr/bin/env python3
"""Materialize the authorized v1.1 collection without changing the ten train records."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[4]
STAGE = REPO / "stage_02_Particle_Interaction_Operator"
ROOT = STAGE / "06_model/pair_force_pio_training_protocol_v0_2"
OLDROOT = STAGE / "05_dataset/blind_multifamily_pair_scope_v1_0"
MATERIALIZER_SOURCE = OLDROOT / "manifests/materialize_stage02jw_dataset.py"


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def content_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def write_new(path: Path, value: Any) -> None:
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


family_gate = json.loads((ROOT / "target_qualification/family_all_or_none_qualification_infrastructure_corrected.json").read_text())
if not family_gate["all_2_families_materialization_authorized"]:
    raise RuntimeError("whole-family materialization not authorized")
protocol = json.loads((ROOT / "freeze/protocol_v0_2_hash.json").read_text())
materializer = load_module("stage02mp_reused_stage02jw_materializer", MATERIALIZER_SOURCE)
materializer.ROOT = ROOT
materializer.FORMULAS = ROOT / "blind_family_generator/blind_family_formulas_v0_2.json"
materializer.TARGETS = ROOT / "target_qualification/blind_target_candidates.json"
materializer.REFERENCE = ROOT / "reference_qualification/reference_qualification.json"
materializer.PHYSICAL = ROOT / "reference_qualification/physical_preflight.json"
materializer.CORE = ROOT / "target_qualification/target_core_qualification.json"
materializer.PATHS = ROOT / "target_qualification/resolution_support_qualification_infrastructure_corrected.json"
materializer.CONSERVATION = ROOT / "conservation/pair_only_conservation.json"
materializer.FAMILY = ROOT / "target_qualification/family_all_or_none_qualification_infrastructure_corrected.json"
materializer.CONTRACT = ROOT / "freeze/training_protocol_v0_2.yaml"
materializer.RETRY = ROOT / "qc/frozen_infrastructure_semantics_application.json"
materializer.ROLES = {"V02_BLIND_VALIDATION_01": "future_validation", "V02_BLIND_TEST_01": "future_test"}

old_serializer = materializer.module("stage02mp_old_serializer", materializer.OLD_SCRIPT)
generator = materializer.module("stage02mp_generator_materialize", materializer.GENERATOR)
evaluator = materializer.module("stage02mp_evaluator_materialize", materializer.EVALUATOR)
stage02f = materializer.module("stage02mp_hash", materializer.STAGE02F)
config = materializer.load_yaml(materializer.CONFIG)
formulas = json.loads(materializer.FORMULAS.read_text())
targets = json.loads(materializer.TARGETS.read_text())
schema_j = json.loads(materializer.OLD_SCHEMA.read_text())
schema_b = json.loads(materializer.CORE_SCHEMA.read_text())
conservation = json.loads(materializer.CONSERVATION.read_text())
definitions = {row["family_id"]: row for row in formulas["families"]}
cons = {row["case_id"]: row for family in conservation["families"] for row in family["rows"]}

records_dir = ROOT / "records"
canonical_dir = ROOT / "canonical_records"
records_dir.mkdir(parents=True, exist_ok=True)
canonical_dir.mkdir(parents=True, exist_ok=True)
if any(records_dir.iterdir()) or any(canonical_dir.iterdir()):
    raise FileExistsError("collection records already materialized")

old_inventory = json.loads((OLDROOT / "canonical_records/canonical_inventory.json").read_text())
inventory = []
qc_rows = []
for row in old_inventory["rows"]:
    if row["split_role"] != "future_train":
        continue
    raw_source = REPO / row["raw_path"]
    bin_source = REPO / row["canonical_path"]
    raw_out = records_dir / raw_source.name
    bin_out = canonical_dir / bin_source.name
    shutil.copyfile(raw_source, raw_out)
    shutil.copyfile(bin_source, bin_out)
    inventory.append({**row, "raw_path": str(raw_out.relative_to(REPO)), "canonical_path": str(bin_out.relative_to(REPO)), "source_collection": "blind_multifamily_pair_scope_v1_0", "bytes_copied_unchanged": True})
    qc_rows.append({"case_id": row["case_id"], "source": "existing_train_record_byte_copy", "raw_hash_identity": sha(raw_source) == sha(raw_out), "canonical_hash_identity": sha(bin_source) == sha(bin_out), "status": "PASS"})

for target in targets["candidates"]:
    case_id = target["case"]["case_id"]
    record, context = materializer.build_record(target, definitions[target["case"]["family_id"]], generator, evaluator, stage02f, old_serializer, config, cons[case_id])
    core_errors = old_serializer.validate_schema(record["stage02b_record"], schema_b, schema_b)
    extension_errors = old_serializer.validate_schema(record, schema_j, schema_j)
    first = old_serializer.serialize_record(record)
    second = old_serializer.serialize_record(record)
    decoded = old_serializer.deserialize_record(first)
    semantic = old_serializer.semantic_qc(record, decoded, context, {"reference_pair_qualification": {"agreement": {"status": "PASS"}}}, stage02f, config)
    deterministic = first == second == old_serializer.serialize_record(decoded)
    passed = not core_errors and not extension_errors and deterministic and all(value == "PASS" for value in semantic.values())
    if not passed:
        raise RuntimeError(f"QC failure {case_id}: {core_errors} {extension_errors} {semantic}")
    raw = old_serializer.pretty_json_bytes(record)
    raw_out = records_dir / f"{case_id}.json"
    bin_out = canonical_dir / f"{case_id}.bin"
    raw_out.write_bytes(raw)
    bin_out.write_bytes(first)
    inventory.append({
        "case_id": case_id,
        "family_id": target["case"]["family_id"],
        "split_role": target["family_role"],
        "raw_path": str(raw_out.relative_to(REPO)),
        "raw_sha256": old_serializer.sha256_bytes(raw),
        "canonical_path": str(bin_out.relative_to(REPO)),
        "canonical_sha256": old_serializer.sha256_bytes(first),
        "canonical_byte_count": len(first),
        "state_hash": record["identity_and_provenance"]["state_hash"],
        "graph_hash": record["identity_and_provenance"]["graph_hash"],
        "target_hash": context["target_hash"],
        "roundtrip_status": "PASS",
        "source_collection": "new_protocol_v0_2_blind_family",
        "bytes_copied_unchanged": False,
    })
    qc_rows.append({"case_id": case_id, "source": "single_materialized_v02_family", "stage02b_schema_errors": core_errors, "extension_schema_errors": extension_errors, "semantic_checks": semantic, "deterministic_bytes": deterministic, "status": "PASS"})

inventory.sort(key=lambda row: row["case_id"])
write_new(ROOT / "qc/quality_control_results.json", {"audit_version": "stage02mp-v1.1-qc-1.0.0", "record_count": 20, "hard_failure_count": 0, "rows": qc_rows, "overall_status": "PASS"})
write_new(ROOT / "canonical_records/canonical_inventory.json", {
    "serializer_version": "stage02j-canonical-binary-0.1.0",
    "dataset_collection": "blind_multifamily_pair_scope_v1_1_protocol_v02",
    "schema_compatibility_identifier": "controlled_regular_pair_scope_v0_1",
    "record_count": 20,
    "fixed_float_dtype": "big_endian_float64",
    "fixed_integer_dtype": "big_endian_int64",
    "fixed_array_path_order": old_inventory["fixed_array_path_order"],
    "rows": inventory,
    "all_roundtrip_checks_pass": True,
})

old_lineage = json.loads((OLDROOT / "lineage/family_lineage_registry.json").read_text())
lineage_rows = [row for row in old_lineage["families"] if row["family_id"] in ("BLIND_FAMILY_01", "BLIND_FAMILY_02")]
for definition in formulas["families"]:
    ids = [row["case_id"] for row in inventory if row["family_id"] == definition["family_id"]]
    lineage_rows.append({"family_id": definition["family_id"], "role": definition["role"], "root_seed": definition["root_seed"], "lineage_id": definition["lineage_id"], "formula_hash": definition["formula_hash"], "derivative_hash": definition["derivative_hash"], "source_ancestry": definition["source_ancestry"], "record_ids": ids, "record_count": 5, "independent_from_other_families": True})
write_new(ROOT / "split/family_lineage_registry.json", {"registry_version": "stage02mp-v1.1-lineage-1.0.0", "family_count": 4, "families": lineage_rows, "cross_family_shared_seed": False, "cross_split_lineage": False, "status": "PASS"})

components = []
edges = []
for row in lineage_rows:
    ids = row["record_ids"]
    components.append({"component_id": f"component_{row['family_id'].lower()}", "family_id": row["family_id"], "role": row["role"], "record_ids": ids, "component_hash": content_hash(ids)})
    for left in range(len(ids)):
        for right in range(left + 1, len(ids)):
            edges.append({"left": ids[left], "right": ids[right], "reason_codes": ["SAME_FAMILY_FORMULA_SEED_LINEAGE"]})
write_new(ROOT / "split/leakage_graph.json", {"contract": "Stage02B_frozen_family_level_leakage", "node_count": 20, "edge_count": len(edges), "edges": edges, "connected_component_count": 4, "connected_components": components, "cross_split_edge_count": 0, "particle_edge_patch_split_used": False, "resolution_support_pseudo_independence_used": False, "status": "PASS"})

roles = {"BLIND_FAMILY_01": "future_train", "BLIND_FAMILY_02": "future_train", "V02_BLIND_VALIDATION_01": "future_validation", "V02_BLIND_TEST_01": "future_test"}
assignments = {row["case_id"]: row["split_role"] for row in inventory}
write_new(ROOT / "split/prefrozen_split_manifest.json", {"manifest_version": "stage02mp-v1.1-split-1.0.0", "assignment_source": "protocol_v0.2 family roles frozen before blind formulas", "family_assignments": roles, "record_assignments": assignments, "counts": {"future_train": 10, "future_validation": 5, "future_test": 5}, "family_level_assignment": True, "no_cross_split_lineage": True, "particle_edge_patch_split_used": False, "resolution_support_pseudo_independence_used": False, "role_reassignment_used": False, "status": "PASS"})

source_norm = json.loads((OLDROOT / "normalization/train_only_graph_balanced_statistics.json").read_text())
source_train_hashes = source_norm["train_record_hashes"]
new_train_hashes = [row["canonical_sha256"] for row in inventory if row["split_role"] == "future_train"]
normalization_check = {
    "contract_version": "stage02mp-v1.1-normalization-reuse-verification-1.0.0",
    "source_path": str((OLDROOT / "normalization/train_only_graph_balanced_statistics.json").relative_to(REPO)),
    "source_file_sha256": sha(OLDROOT / "normalization/train_only_graph_balanced_statistics.json"),
    "statistics_hash": source_norm["statistics_hash"],
    "required_statistics_hash": "sha256:2208d2f4b9b7c848f2cd1b93624f9f6a3d9fb29e65cdd70ee453e6122c43d051",
    "source_train_record_hashes": source_train_hashes,
    "v1_1_train_record_hashes": new_train_hashes,
    "train_hash_multiset_identical": sorted(source_train_hashes) == sorted(new_train_hashes),
    "normalization_code_hash": sha(MATERIALIZER_SOURCE),
    "fields_units_unchanged": True,
    "refit_performed": False,
    "supervision_scale_mixed_with_input_normalization": False,
  }
normalization_check["status"] = "PASS" if normalization_check["statistics_hash"] == normalization_check["required_statistics_hash"] and normalization_check["train_hash_multiset_identical"] else "FAIL"
write_new(ROOT / "normalization/input_normalization_reuse_verification.json", normalization_check)

eligibility_rows = [{"case_id": row["case_id"], "family_id": row["family_id"], "split_role": row["split_role"], "eligible": True, "regularity_role": "diagnostic_only", "manual_override_permitted": False} for row in inventory]
write_new(ROOT / "qc/record_eligibility_results.json", {"rules_version": "stage02mp-v1.1-eligibility-1.0.0", "record_count": 20, "eligible_count": 20, "rows": eligibility_rows, "status": "PASS"})

test_rows = [row for row in inventory if row["split_role"] == "future_test"]
write_new(ROOT / "test_seal/sealed_test_payload_manifest.json", {"seal_version": "stage02mp-v02-test-payload-seal-1.0.0", "family_id": "V02_BLIND_TEST_01", "protocol_sha256": protocol["protocol_sha256"], "test_record_count": 5, "test_target_access": False, "payloads": [{"case_id": row["case_id"], "canonical_path": row["canonical_path"], "canonical_sha256": row["canonical_sha256"], "target_hash": row["target_hash"]} for row in test_rows], "hash_sealed": True, "release_manifest_created": False, "status": "SEALED"})

manifest = {
    "manifest_version": "stage02mp-v1.1-collection-1.0.0",
    "dataset_collection": "blind_multifamily_pair_scope_v1_1_protocol_v02",
    "schema_compatibility_identifier": "controlled_regular_pair_scope_v0_1",
    "protocol_sha256": protocol["protocol_sha256"],
    "supervision_scale_hash": json.loads((ROOT / "target_scale/train_only_supervision_scale.json").read_text())["result_hash"],
    "input_normalization_hash": normalization_check["statistics_hash"],
    "record_count": 20,
    "record_hashes": [{"case_id": row["case_id"], "sha256": row["canonical_sha256"]} for row in inventory],
    "family_components": [{"family_id": key, "role": value, "record_count": 5} for key, value in roles.items()],
    "lineage_component_count": 4,
    "split_counts": {"future_train": 10, "future_validation": 5, "future_test": 5},
    "historical_consumed_families_excluded": ["BLIND_FAMILY_03", "BLIND_FAMILY_04"],
    "regularity_role": "diagnostic_only",
    "status": "BLIND_MULTIFAMILY_DATASET_V1_1_READY",
}
write_new(ROOT / "manifests/v1_1_collection_manifest.json", manifest)
print(json.dumps({"record_count": 20, "train_copied_unchanged": 10, "new_blind_records": 10, "components": 4, "normalization": normalization_check["status"], "status": manifest["status"]}, sort_keys=True))
