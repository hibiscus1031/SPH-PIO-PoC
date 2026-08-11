#!/usr/bin/env python3
"""Freeze historical evidence and the Stage 02J-W eligibility contract."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
STAGE = REPO / "stage_02_Particle_Interaction_Operator"
ROOT = STAGE / "05_dataset/blind_multifamily_pair_scope_v1_0"
OUT = ROOT / "freeze/stage02jw_input_freeze_manifest.json"

REQUIRED = [
    "stage_02_Particle_Interaction_Operator/07_reports/stage02jv_final_report.md",
    "stage_02_Particle_Interaction_Operator/05_dataset/regularity_contract_v0_4/manifests/route_termination_decision.json",
    "stage_02_Particle_Interaction_Operator/05_dataset/regularity_contract_v0_3/blind_family_generator/generate_blind_families.py",
    "stage_02_Particle_Interaction_Operator/05_dataset/regularity_contract_v0_3/blind_family_generator/blind_generator_freeze.yaml",
    "stage_02_Particle_Interaction_Operator/05_dataset/regularity_contract_v0_4/blind_materialization/blind_materialization_status.json",
    "stage_02_Particle_Interaction_Operator/05_dataset/regularity_contract_v0_3/blind_family_generator/blind_generation_status.json",
    "stage_02_Particle_Interaction_Operator/05_dataset/regularity_contract_v0_2/contract_design/regularity_contract_v0_2.yaml",
    "stage_02_Particle_Interaction_Operator/05_dataset/controlled_multifamily_pair_scope_v0_2/target_qualification/new_family_target_candidates.json",
    "stage_02_Particle_Interaction_Operator/05_dataset/controlled_regular_pair_scope_v0_1/canonical_records/canonical_serialization_manifest.json",
    "stage_02_Particle_Interaction_Operator/04_target_attribution/acceptance/reference_acceptance_rules.yaml",
    "stage_02_Particle_Interaction_Operator/04_target_attribution/qualified_spatial_targets/targets/spatial_target_candidates.json",
    "stage_02_Particle_Interaction_Operator/04_target_attribution/conservation_closure/freeze/stage02ir_scope_and_decision_rules.yaml",
    "stage_02_Particle_Interaction_Operator/04_target_attribution/conservation_closure/architecture_scope/architecture_scope_decision.json",
    "stage_02_Particle_Interaction_Operator/03_dataset/schema/pio_dataset_schema.json",
    "stage_02_Particle_Interaction_Operator/03_dataset/splitting/split_strategy.md",
    "stage_02_Particle_Interaction_Operator/03_dataset/uncertainty/uncertainty_contract.md",
    "stage_02_Particle_Interaction_Operator/03_dataset/eligibility/label_eligibility_rules.yaml",
    "stage_02_Particle_Interaction_Operator/05_dataset/controlled_regular_pair_scope_v0_1/schema/stage02j_graph_record_schema.json",
    "stage_02_Particle_Interaction_Operator/05_dataset/controlled_regular_pair_scope_v0_1/schema/canonical_serialization_contract.yaml",
    "stage_02_Particle_Interaction_Operator/05_dataset/controlled_regular_pair_scope_v0_1/schema/feature_permission_table.yaml",
    "stage_02_Particle_Interaction_Operator/05_dataset/controlled_regular_pair_scope_v0_1/manifests/run_stage02j_controlled_dataset.py",
    "stage_02_Particle_Interaction_Operator/04_target_attribution/resolution_extension/resolution_extension_matrix.yaml",
    "stage_02_Particle_Interaction_Operator/04_target_attribution/semidiscrete_reference/r2s_reference_design.yaml",
    "stage_02_Particle_Interaction_Operator/05_dataset/blind_multifamily_pair_scope_v1_0/eligibility_contract/blind_dataset_eligibility_contract_v1_0.yaml",
]


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if OUT.exists(): raise FileExistsError(OUT)
    missing = [name for name in REQUIRED if not (REPO / name).is_file()]
    if missing: raise FileNotFoundError(missing)
    history = {}
    for base in (REPO / "stage_01_verification", STAGE):
        for path in sorted(p for p in base.rglob("*") if p.is_file()):
            if "05_dataset/blind_multifamily_pair_scope_v1_0" in path.as_posix(): continue
            history[str(path.relative_to(REPO))] = sha(path)
    manifest = {
        "manifest_version": "stage02jw-input-freeze-1.0.0",
        "required_inputs": {name: sha(REPO / name) for name in REQUIRED},
        "historical_file_hashes_before_stage02jw": history,
        "historical_file_count": len(history),
        "eligibility_contract_hash": sha(ROOT / "eligibility_contract/blind_dataset_eligibility_contract_v1_0.yaml"),
        "blind_generator_source_hash": sha(REPO / REQUIRED[2]),
        "blind_generator_configuration_hash": sha(REPO / REQUIRED[3]),
        "regularity_hard_gate_permitted": False,
        "regularity_diagnostic_only": True,
        "historical_statuses": {
            "stage02j": "CONTROLLED_REGULAR_DATASET_NOT_READY",
            "stage02jr": "MULTIFAMILY_CONTROLLED_DATASET_NOT_READY",
            "stage02js": "VERSIONED_MULTIFAMILY_DATASET_NOT_READY",
            "stage02jt": "REGULARITY_GATE_V03_NOT_QUALIFIED",
            "stage02jv": "REGULARITY_HARD_GATE_ROUTE_TERMINATED",
            "stage02k_authorized": False,
        },
        "manual_override_permitted": False,
    }
    OUT.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"historical_file_count": len(history), "eligibility_contract_hash": manifest["eligibility_contract_hash"]}, sort_keys=True))
    return 0


if __name__ == "__main__": raise SystemExit(main())
