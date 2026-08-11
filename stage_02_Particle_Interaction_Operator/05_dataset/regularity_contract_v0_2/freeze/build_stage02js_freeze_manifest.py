#!/usr/bin/env python3
"""Freeze Stage 02J-S inputs and the prospective v0.2 contract."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ROOT = REPO / "stage_02_Particle_Interaction_Operator"
OUT = ROOT / "05_dataset/regularity_contract_v0_2/freeze/stage02js_input_freeze_manifest.json"

REQUIRED = [
    "stage_02_Particle_Interaction_Operator/07_reports/stage02jr_final_report.md",
    "stage_02_Particle_Interaction_Operator/05_dataset/controlled_multifamily_pair_scope_v0_2/target_qualification/new_family_target_candidates.json",
    "stage_02_Particle_Interaction_Operator/05_dataset/controlled_multifamily_pair_scope_v0_2/target_qualification/six_component_attribution.json",
    "stage_02_Particle_Interaction_Operator/05_dataset/controlled_multifamily_pair_scope_v0_2/family_design/family_preregistration.yaml",
    "stage_02_Particle_Interaction_Operator/05_dataset/controlled_multifamily_pair_scope_v0_2/family_design/analytic_family_definitions.py",
    "stage_02_Particle_Interaction_Operator/05_dataset/controlled_multifamily_pair_scope_v0_2/reference_qualification/reference_qualification_results.json",
    "stage_02_Particle_Interaction_Operator/05_dataset/controlled_multifamily_pair_scope_v0_2/conservation/pair_only_conservation_qualification.json",
    "stage_02_Particle_Interaction_Operator/04_target_attribution/qualified_spatial_targets/attribution/six_component_attribution.json",
    "stage_02_Particle_Interaction_Operator/04_target_attribution/smoothness_audit/smoothness_criterion_contract.yaml",
    "stage_02_Particle_Interaction_Operator/03_dataset/schema/pio_dataset_schema.json",
    "stage_02_Particle_Interaction_Operator/03_dataset/eligibility/label_eligibility_rules.yaml",
    "stage_02_Particle_Interaction_Operator/03_dataset/splitting/split_strategy.md",
    "stage_02_Particle_Interaction_Operator/03_dataset/uncertainty/uncertainty_contract.md",
    "stage_02_Particle_Interaction_Operator/05_dataset/controlled_regular_pair_scope_v0_1/schema/stage02j_graph_record_schema.json",
    "stage_02_Particle_Interaction_Operator/05_dataset/controlled_regular_pair_scope_v0_1/schema/canonical_serialization_contract.yaml",
    "stage_02_Particle_Interaction_Operator/05_dataset/controlled_regular_pair_scope_v0_1/schema/feature_permission_table.yaml",
    "stage_02_Particle_Interaction_Operator/05_dataset/controlled_regular_pair_scope_v0_1/manifests/run_stage02j_controlled_dataset.py",
    "stage_02_Particle_Interaction_Operator/05_dataset/regularity_contract_v0_2/freeze/development_heldout_scope.yaml",
    "stage_02_Particle_Interaction_Operator/05_dataset/regularity_contract_v0_2/contract_design/regularity_contract_v0_2.yaml",
]


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if OUT.exists():
        raise FileExistsError(f"No-overwrite freeze: {OUT}")
    missing = [name for name in REQUIRED if not (REPO / name).is_file()]
    if missing:
        raise FileNotFoundError(missing)
    historical = {}
    for base in (REPO / "stage_01_verification", ROOT):
        for path in sorted(p for p in base.rglob("*") if p.is_file()):
            if "05_dataset/regularity_contract_v0_2" in path.as_posix() or "05_dataset/controlled_multifamily_pair_scope_v0_3" in path.as_posix():
                continue
            historical[str(path.relative_to(REPO))] = sha(path)
    manifest = {
        "manifest_version": "stage02js-input-freeze-0.2.0",
        "required_inputs": {name: sha(REPO / name) for name in REQUIRED},
        "historical_file_hashes_before_stage02js": historical,
        "historical_file_count": len(historical),
        "heldout_roles_frozen_before_metric_execution": True,
        "contract_hash": sha(REPO / REQUIRED[-1]),
        "scope_hash": sha(REPO / REQUIRED[-2]),
        "manual_override_permitted": False,
    }
    OUT.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"historical_file_count": len(historical), "contract_hash": manifest["contract_hash"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
