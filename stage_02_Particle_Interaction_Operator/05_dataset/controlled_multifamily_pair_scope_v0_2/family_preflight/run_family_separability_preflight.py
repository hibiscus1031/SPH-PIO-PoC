#!/usr/bin/env python3
"""Run Stage 02J-R lineage separability before any new target evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
STAGE_ROOT = REPO_ROOT / "stage_02_Particle_Interaction_Operator"
DATA_ROOT = STAGE_ROOT / "05_dataset/controlled_multifamily_pair_scope_v0_2"
PREREG = DATA_ROOT / "family_design/family_preregistration.yaml"
SPLIT_CONTRACT = STAGE_ROOT / "03_dataset/splitting/split_strategy.md"
OUTPUT = DATA_ROOT / "family_preflight/family_separability_preflight.json"


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        parser.error("Preflight requires explicit --execute")
    if OUTPUT.exists():
        raise FileExistsError(f"No-overwrite contract: {OUTPUT}")
    prereg = yaml.safe_load(PREREG.read_text(encoding="utf-8"))
    split_text = SPLIT_CONTRACT.read_text(encoding="utf-8")
    required_terms = ["同一 trajectory", "initial-condition", "deterministic repeat", "直接", "connected component"]
    if not all(term in split_text for term in required_terms):
        raise RuntimeError("Frozen Stage 02B split/leakage contract is not uniquely readable")
    families = prereg["families"]
    ids = [row["family_id"] for row in families]
    if ids != ["FAMILY_PV_EXISTING", "FAMILY_CROSSMODE_A", "FAMILY_DIAGONAL_B", "FAMILY_MIXED_C"]:
        raise RuntimeError("Family order or inventory mismatch")
    cross_edges = []
    rows = []
    for family in families:
        independent = (
            family["no_parent_trajectory"] is True
            and family["no_shared_seed"] is True
            and family["resample_or_restart_ancestry"] == "none"
            and family["initial_condition_lineage"]
            and family["solution_family"]
        )
        formula_hash = digest(canonical(family.get("formulas", {"source": family["source_lineage"]})))
        rows.append(
            {
                "family_id": family["family_id"],
                "split_role": family["split_role"],
                "initial_condition_lineage": family["initial_condition_lineage"],
                "solution_family": family["solution_family"],
                "formula_hash": formula_hash,
                "no_parent_trajectory": family["no_parent_trajectory"],
                "no_shared_seed": family["no_shared_seed"],
                "no_resample_or_restart_ancestry": family["resample_or_restart_ancestry"] == "none",
                "lineage_status": "PASS" if independent else "FAIL",
            }
        )
    for i, left in enumerate(families):
        for right in families[i + 1 :]:
            direct_reasons = []
            if left["initial_condition_lineage"] == right["initial_condition_lineage"]:
                direct_reasons.append("SAME_INITIAL_CONDITION_LINEAGE")
            if left["solution_family"] == right["solution_family"]:
                direct_reasons.append("SAME_SOLUTION_FAMILY")
            if left["source_lineage"] == right["source_lineage"]:
                direct_reasons.append("DIRECT_SOURCE_ANCESTRY")
            if direct_reasons:
                cross_edges.append({"left": left["family_id"], "right": right["family_id"], "reasons": direct_reasons})
    infrastructure = [
        "same_EOS_implementation",
        "same_baseline_SPH_code",
        "same_Fourier_implementation",
        "same_periodic_domain",
        "same_target_schema",
        "same_serialization_code",
    ]
    status = "PASS" if not cross_edges and all(row["lineage_status"] == "PASS" for row in rows) else "FAIL"
    result = {
        "preflight_version": "stage02jr-family-separability-0.2.0",
        "executed_before_new_acceleration_or_target": True,
        "frozen_contract_path": str(SPLIT_CONTRACT.relative_to(REPO_ROOT)),
        "frozen_contract_hash": digest(SPLIT_CONTRACT.read_bytes()),
        "shared_infrastructure_not_direct_lineage": infrastructure,
        "direct_lineage_relation_types": [
            "same_trajectory", "same_initial_condition_lineage", "same_deterministic_seed_lineage",
            "restart_resample_or_direct_derivation", "same_frame_or_view", "same_solution_or_benchmark_family",
            "direct_source_record_ancestry",
        ],
        "family_rows": rows,
        "cross_family_leakage_edges": cross_edges,
        "anticipated_family_component_count": 4 if not cross_edges else None,
        "machine_implementation_connects_by_shared_reference_code": False,
        "Stage02B_contract_modified": False,
        "status": status,
    }
    if status != "PASS":
        raise RuntimeError("Family separability preflight failed; expansion must stop")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "anticipated_components": 4, "cross_family_edges": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

