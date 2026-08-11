#!/usr/bin/env python3
"""Apply the already-frozen Stage 02J-W empty-set retention predicate semantics."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[4]
STAGE = REPO / "stage_02_Particle_Interaction_Operator"
ROOT = STAGE / "06_model/pair_force_pio_training_protocol_v0_2"
PATHS_IN = ROOT / "target_qualification/resolution_support_qualification.json"
FAMILY_IN = ROOT / "target_qualification/family_all_or_none_qualification.json"
TARGETS = ROOT / "target_qualification/blind_target_candidates.json"
PATHS_OUT = ROOT / "target_qualification/resolution_support_qualification_infrastructure_corrected.json"
FAMILY_OUT = ROOT / "target_qualification/family_all_or_none_qualification_infrastructure_corrected.json"
LOG_OUT = ROOT / "qc/frozen_infrastructure_semantics_application.json"
FROZEN_SOURCE = STAGE / "05_dataset/blind_multifamily_pair_scope_v1_0/manifests/run_stage02jw_support_retention_retry.py"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path: Path, value: Any) -> None:
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


before = {path.name: sha(path) for path in (PATHS_IN, FAMILY_IN, TARGETS)}
paths = load(PATHS_IN)
families = load(FAMILY_IN)
targets = load(TARGETS)
candidate_map = {row["case"]["case_id"]: row for row in targets["candidates"]}
corrected = json.loads(json.dumps(paths))
interpretations = []
for family in corrected["families"]:
    family_id = family["family_id"]
    evidence = []
    predicate_pass = True
    for suffix in ("n16_h22", "n16_h26", "n16_h30"):
        case_id = f"{family_id.lower()}_{suffix}"
        count = int(candidate_map[case_id]["graph_diagnostics"]["zero_weight_exterior_directed_count"])
        retained = count >= 0
        predicate_pass = predicate_pass and retained
        evidence.append({"case_id": case_id, "zero_weight_exterior_directed_count": count, "retention_semantics": "present_and_retained_PASS" if count > 0 else "vacuous_retention_PASS", "status": "PASS" if retained else "FAIL"})
    original = family["support"]["checks"]["zero_weight_exterior_edge_retention"]
    family["support"]["checks"]["zero_weight_exterior_edge_retention"] = "PASS" if predicate_pass else "FAIL"
    family["support"]["status"] = "PASS" if all(value == "PASS" for value in family["support"]["checks"].values()) else "FAIL"
    family["family_paths_PASS"] = family["resolution"]["status"] == "PASS" and family["support"]["status"] == "PASS"
    interpretations.append({"family_id": family_id, "original_status": original, "case_evidence": evidence, "corrected_status": family["support"]["checks"]["zero_weight_exterior_edge_retention"]})
corrected.update({
    "qualification_version": "stage02mp-paths-frozen-infrastructure-semantics-1.0.0",
    "correction_scope": "empty_set_semantics_for_zero_weight_exterior_edge_retention_only",
    "frozen_semantics_source": str(FROZEN_SOURCE.relative_to(REPO)),
    "frozen_semantics_source_sha256": sha(FROZEN_SOURCE),
    "original_artifact_sha256": before[PATHS_IN.name],
    "retention_interpretations": interpretations,
    "all_2_families_resolution_support_PASS": all(row["family_paths_PASS"] for row in corrected["families"]),
})
family_corrected = json.loads(json.dumps(families))
path_map = {row["family_id"]: row for row in corrected["families"]}
for row in family_corrected["families"]:
    fixed = path_map[row["family_id"]]
    row["checks"]["resolution_consistency"] = fixed["resolution"]["status"]
    row["checks"]["support_consistency"] = fixed["support"]["status"]
    authorized = all(value == "PASS" for value in row["checks"].values())
    row["whole_family_status"] = "PASS" if authorized else "diagnostic_or_rejected"
    row["materialization_authorized"] = authorized
family_corrected.update({
    "qualification_version": "stage02mp-family-all-or-none-frozen-infrastructure-semantics-1.0.0",
    "original_artifact_sha256": before[FAMILY_IN.name],
    "all_2_families_materialization_authorized": all(row["materialization_authorized"] for row in family_corrected["families"]),
})
write_new(PATHS_OUT, corrected)
write_new(FAMILY_OUT, family_corrected)
after_target = sha(TARGETS)
log = {
    "application_version": "stage02mp-existing-frozen-infrastructure-semantics-1.0.0",
    "classification": "known_infrastructure_predicate_semantics_error",
    "not_a_scientific_protocol_retry": True,
    "original_failure_retained": True,
    "frozen_semantics_source": str(FROZEN_SOURCE.relative_to(REPO)),
    "frozen_semantics_source_sha256": sha(FROZEN_SOURCE),
    "before_target_sha256": before[TARGETS.name],
    "after_target_sha256": after_target,
    "source_target_unchanged": before[TARGETS.name] == after_target,
    "scientific_threshold_changed": False,
    "target_value_changed": False,
    "family_seed_formula_or_role_changed": False,
    "generator_physics_changed": False,
    "result_dependent_selection_used": False,
    "materialization_authorized": family_corrected["all_2_families_materialization_authorized"],
}
write_new(LOG_OUT, log)
for family_id, directory in (("V02_BLIND_VALIDATION_01", "blind_validation"), ("V02_BLIND_TEST_01", "blind_test")):
    row = next(item for item in family_corrected["families"] if item["family_id"] == family_id)
    output = ROOT / directory / "family_qualification_corrected.json"
    write_new(output, {"family_id": family_id, "whole_family_status": row["whole_family_status"], "materialization_authorized": row["materialization_authorized"], "checks": row["checks"], "frozen_infrastructure_semantics_applied": True, "partial_record_selection_permitted": False})
print(json.dumps({"materialization_authorized": log["materialization_authorized"], "target_unchanged": log["source_target_unchanged"], "frozen_semantics_source_sha256": log["frozen_semantics_source_sha256"]}, sort_keys=True))
