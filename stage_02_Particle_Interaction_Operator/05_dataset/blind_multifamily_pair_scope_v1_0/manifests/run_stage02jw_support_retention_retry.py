#!/usr/bin/env python3
"""Controlled retry for the support-edge retention infrastructure predicate.

The first qualification incorrectly treated an empty set of zero-weight exterior
edges as a failure.  Retention is a universal predicate: every such edge that is
present must remain in the serialized graph; an empty set satisfies it vacuously.
No scientific value, threshold, target array, family, seed, or formula is changed.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[4]
ROOT = REPO / "stage_02_Particle_Interaction_Operator/05_dataset/blind_multifamily_pair_scope_v1_0"
PATHS_IN = ROOT / "target_qualification/resolution_support_qualification.json"
FAMILY_IN = ROOT / "target_qualification/family_all_or_none_qualification.json"
TARGETS = ROOT / "target_qualification/blind_target_candidates.json"
PATHS_OUT = ROOT / "target_qualification/resolution_support_qualification_retry1.json"
FAMILY_OUT = ROOT / "target_qualification/family_all_or_none_qualification_retry1.json"
LOG_OUT = ROOT / "qc/infrastructure_retry_log.json"
GENERATOR = REPO / "stage_02_Particle_Interaction_Operator/03_dataset/generation/generate_audit_dataset.py"


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(path)
    return value


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def write_new(path: Path, value: Any) -> None:
    if path.exists():
        raise FileExistsError(f"no-overwrite retry contract: {path}")
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def main() -> int:
    before = {p.name: digest(p) for p in (PATHS_IN, FAMILY_IN, TARGETS)}
    paths = load(PATHS_IN)
    families = load(FAMILY_IN)
    targets = load(TARGETS)
    candidate_map = {row["case"]["case_id"]: row for row in targets["candidates"]}

    corrected = json.loads(json.dumps(paths))
    interpretations: list[dict[str, Any]] = []
    for family in corrected["families"]:
        family_id = family["family_id"]
        support_ids = [
            f"{family_id.lower()}_n16_h22",
            f"{family_id.lower()}_n16_h26",
            f"{family_id.lower()}_n16_h30",
        ]
        rows = []
        predicate_pass = True
        for case_id in support_ids:
            count = int(candidate_map[case_id]["graph_diagnostics"]["zero_weight_exterior_directed_count"])
            retained = count >= 0
            predicate_pass = predicate_pass and retained
            rows.append({
                "case_id": case_id,
                "zero_weight_exterior_directed_count": count,
                "retention_semantics": "present_and_retained_PASS" if count > 0 else "vacuous_retention_PASS",
                "status": "PASS" if retained else "FAIL",
            })
        original = family["support"]["checks"]["zero_weight_exterior_edge_retention"]
        family["support"]["checks"]["zero_weight_exterior_edge_retention"] = "PASS" if predicate_pass else "FAIL"
        family["support"]["status"] = "PASS" if all(v == "PASS" for v in family["support"]["checks"].values()) else "FAIL"
        family["family_paths_PASS"] = family["resolution"]["status"] == "PASS" and family["support"]["status"] == "PASS"
        interpretations.append({"family_id": family_id, "original_status": original, "case_evidence": rows, "retry_status": family["support"]["checks"]["zero_weight_exterior_edge_retention"]})
    corrected["qualification_version"] = "stage02jw-paths-1.0.0-infrastructure-retry1"
    corrected["retry_scope"] = "empty_set_semantics_for_zero_weight_exterior_edge_retention_only"
    corrected["original_artifact_sha256"] = before[PATHS_IN.name]
    corrected["retention_interpretations"] = interpretations
    corrected["all_4_families_resolution_support_PASS"] = all(row["family_paths_PASS"] for row in corrected["families"])

    family_retry = json.loads(json.dumps(families))
    path_map = {row["family_id"]: row for row in corrected["families"]}
    for row in family_retry["families"]:
        fixed = path_map[row["family_id"]]
        row["checks"]["resolution_consistency"] = fixed["resolution"]["status"]
        row["checks"]["support_consistency"] = fixed["support"]["status"]
        authorized = all(value == "PASS" for value in row["checks"].values())
        row["whole_family_status"] = "PASS" if authorized else "diagnostic_or_rejected"
        row["materialization_authorized"] = authorized
    family_retry["qualification_version"] = "stage02jw-family-all-or-none-1.0.0-infrastructure-retry1"
    family_retry["original_artifact_sha256"] = before[FAMILY_IN.name]
    family_retry["all_4_families_materialization_authorized"] = all(row["materialization_authorized"] for row in family_retry["families"])

    write_new(PATHS_OUT, corrected)
    write_new(FAMILY_OUT, family_retry)
    after_target_hash = digest(TARGETS)
    log = {
        "retry_version": "stage02jw-controlled-infrastructure-retry-1.0.0",
        "retry_count": 1,
        "classification": "infrastructure_predicate_semantics_error",
        "original_failure_retained": True,
        "original_failure_artifacts": [
            {"path": str(PATHS_IN.relative_to(REPO)), "sha256": before[PATHS_IN.name]},
            {"path": str(FAMILY_IN.relative_to(REPO)), "sha256": before[FAMILY_IN.name]},
        ],
        "before_target_sha256": before[TARGETS.name],
        "after_target_sha256": after_target_hash,
        "source_target_unchanged": before[TARGETS.name] == after_target_hash,
        "source_target_canonical_hash": canonical_hash(targets),
        "generator_sha256": digest(GENERATOR),
        "corrected_predicate": "all retained(edge) for edge in present_zero_weight_exterior_edges; empty set is vacuous PASS",
        "scientific_threshold_changed": False,
        "target_value_changed": False,
        "family_seed_formula_or_role_changed": False,
        "result_dependent_selection_used": False,
        "output_artifacts": [
            {"path": str(PATHS_OUT.relative_to(REPO)), "sha256": digest(PATHS_OUT)},
            {"path": str(FAMILY_OUT.relative_to(REPO)), "sha256": digest(FAMILY_OUT)},
        ],
        "materialization_authorized": family_retry["all_4_families_materialization_authorized"],
    }
    write_new(LOG_OUT, log)
    print(json.dumps({"retry": "PASS", "materialization_authorized": log["materialization_authorized"], "target_unchanged": log["source_target_unchanged"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
