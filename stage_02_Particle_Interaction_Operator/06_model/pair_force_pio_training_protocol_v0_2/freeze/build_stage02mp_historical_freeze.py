#!/usr/bin/env python3
"""Freeze Stage 02M-P historical evidence before train-target decode."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
STAGE = REPO / "stage_02_Particle_Interaction_Operator"
ROOT = STAGE / "06_model/pair_force_pio_training_protocol_v0_2"
MR = STAGE / "06_model/pair_force_pio_failure_attribution_v0_1"
M = STAGE / "06_model/pair_force_pio_static_fitting_v0_1"
K = STAGE / "06_model/pair_force_pio_architecture_v0_1"
JW = STAGE / "05_dataset/blind_multifamily_pair_scope_v1_0"


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


paths = {
    STAGE / "07_reports/stage02m_final_report.md",
    STAGE / "07_reports/stage02mr_final_report.md",
    MR / "results/failure_attribution.json",
    MR / "optimization_conditioning/zero_step_conditioning.json",
    MR / "target_scaling/target_scale_audit.json",
    MR / "tangent_space/tangent_space_audit.json",
    MR / "feature_identifiability/feature_identifiability_audit.json",
    MR / "route_decision/route_decision.json",
    MR / "freeze/stage02mr_historical_freeze_manifest.json",
    K / "contracts/architecture_contract_v0_1.json",
    K / "contracts/feature_contract_v0_1.json",
    K / "implementations/pair_force_models.py",
    JW / "manifests/stage02jw_dataset_manifest.json",
    JW / "canonical_records/canonical_inventory.json",
    JW / "normalization/train_only_graph_balanced_statistics.json",
    STAGE / "04_target_attribution/acceptance/reference_acceptance_rules.yaml",
    STAGE / "04_target_attribution/resolution_extension/resolution_extension_matrix.yaml",
    STAGE / "04_target_attribution/semidiscrete_reference/r2s_reference_design.yaml",
    STAGE / "04_target_attribution/conservation_closure/freeze/stage02ir_scope_and_decision_rules.yaml",
    STAGE / "04_target_attribution/conservation_closure/pair_representability/pair_representability_audit.json",
    STAGE / "05_dataset/controlled_regular_pair_scope_v0_1/schema/stage02j_graph_record_schema.json",
    STAGE / "05_dataset/controlled_regular_pair_scope_v0_1/schema/canonical_serialization_contract.yaml",
    STAGE / "05_dataset/controlled_regular_pair_scope_v0_1/schema/feature_permission_table.yaml",
    STAGE / "05_dataset/controlled_regular_pair_scope_v0_1/manifests/run_stage02j_controlled_dataset.py",
    STAGE / "05_dataset/regularity_contract_v0_3/blind_family_generator/generate_blind_families.py",
    STAGE / "05_dataset/regularity_contract_v0_3/blind_family_generator/blind_generator_freeze.yaml",
    ROOT / "blind_family_generator/blind_generator_config_v0_2.yaml",
}
inventory = json.loads((JW / "canonical_records/canonical_inventory.json").read_text())
for row in inventory["rows"]:
    paths.add(REPO / row["canonical_path"])
for path in sorted((K / "implementations").glob("*.py")):
    paths.add(path)

missing = [str(path) for path in paths if not path.is_file()]
if missing:
    raise FileNotFoundError(missing)

mr_freeze = json.loads((MR / "freeze/stage02mr_historical_freeze_manifest.json").read_text())
mr_mismatches = []
for row in mr_freeze["files"]:
    actual = sha(REPO / row["path"])
    if actual != row["sha256"]:
        mr_mismatches.append({"path": row["path"], "expected": row["sha256"], "actual": actual})

rows = [{"path": str(path.relative_to(REPO)), "sha256": sha(path), "bytes": path.stat().st_size} for path in sorted(paths)]
train_rows = [row for row in inventory["rows"] if row["split_role"] == "future_train"]
manifest = {
    "manifest_version": "stage02mp-historical-freeze-1.0.0",
    "freeze_timing": "before_any_train_target_decode_or_blind_formula_materialization",
    "authorization": "STATIC_FITTING_FAILURE_ATTRIBUTED_OPTIMIZATION_CONDITIONING",
    "historical_states": {
        "stage02m": "STATIC_PAIR_FORCE_FITTING_NOT_QUALIFIED",
        "stage02mr": "STATIC_FITTING_FAILURE_ATTRIBUTED_OPTIMIZATION_CONDITIONING",
        "stage02n_authorized": False,
        "BLIND_FAMILY_03": "consumed_historical_validation_only",
        "BLIND_FAMILY_04": "consumed_historical_test_only",
    },
    "stage02mr_285_file_verification": {
        "expected_count": 285,
        "manifest_count": mr_freeze["file_count"],
        "mismatch_count": len(mr_mismatches),
        "mismatches": mr_mismatches,
        "status": "PASS" if mr_freeze["file_count"] == 285 and not mr_mismatches else "FAIL",
    },
    "current_record_count": len(inventory["rows"]),
    "current_train_record_count": len(train_rows),
    "current_train_record_hashes": [row["canonical_sha256"] for row in train_rows],
    "input_normalization_hash": "sha256:2208d2f4b9b7c848f2cd1b93624f9f6a3d9fb29e65cdd70ee453e6122c43d051",
    "files": rows,
    "file_count": len(rows),
    "counters": {"new_optimizer_steps": 0, "new_training_runs": 0, "new_test_evaluations": 0},
}
manifest["status"] = "PASS" if manifest["stage02mr_285_file_verification"]["status"] == "PASS" and len(inventory["rows"]) == 20 and len(train_rows) == 10 else "FAIL"
output = ROOT / "freeze/stage02mp_historical_freeze_manifest.json"
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n")
print(json.dumps({"status": manifest["status"], "frozen_files": len(rows), "stage02mr_285": manifest["stage02mr_285_file_verification"]["status"]}))
