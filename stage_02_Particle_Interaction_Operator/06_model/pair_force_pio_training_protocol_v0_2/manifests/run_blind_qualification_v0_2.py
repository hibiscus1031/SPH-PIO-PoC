#!/usr/bin/env python3
"""Run frozen Stage 02J-W physics/reference/target/conservation qualification on v0.2 families."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
STAGE = REPO / "stage_02_Particle_Interaction_Operator"
ROOT = STAGE / "06_model/pair_force_pio_training_protocol_v0_2"
SOURCE = STAGE / "05_dataset/blind_multifamily_pair_scope_v1_0/manifests/run_stage02jw_qualification.py"


def load_source():
    spec = importlib.util.spec_from_file_location("stage02mp_reused_stage02jw_qualification", SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError(SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rewrite(path: Path, updates: dict[str, object]) -> dict[str, object]:
    value = json.loads(path.read_text())
    value.update(updates)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
    return value


protocol_hash = json.loads((ROOT / "freeze/protocol_v0_2_hash.json").read_text())["protocol_sha256"]
qualification = load_source()
qualification.FREEZE_PATH = ROOT / "freeze/protocol_v0_2_hash.json"
qualification.FORMULAS_PATH = ROOT / "blind_family_generator/blind_family_formulas_v0_2.json"
qualification.PHYSICAL_OUT = ROOT / "reference_qualification/physical_preflight.json"
qualification.REFERENCE_OUT = ROOT / "reference_qualification/reference_qualification.json"
qualification.TARGETS_OUT = ROOT / "target_qualification/blind_target_candidates.json"
qualification.CORE_OUT = ROOT / "target_qualification/target_core_qualification.json"
qualification.PATHS_OUT = ROOT / "target_qualification/resolution_support_qualification.json"
qualification.CONSERVATION_OUT = ROOT / "conservation/pair_only_conservation.json"
qualification.FAMILY_OUT = ROOT / "target_qualification/family_all_or_none_qualification.json"
outputs = [qualification.PHYSICAL_OUT, qualification.REFERENCE_OUT, qualification.TARGETS_OUT, qualification.CORE_OUT, qualification.PATHS_OUT, qualification.CONSERVATION_OUT, qualification.FAMILY_OUT]
for output in outputs:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(output)
qualification.main()

physical = rewrite(qualification.PHYSICAL_OUT, {"protocol_sha256": protocol_hash, "family_count": 2, "case_count": 10, "all_2_families_PASS": json.loads(qualification.PHYSICAL_OUT.read_text())["all_4_families_PASS"]})
reference = rewrite(qualification.REFERENCE_OUT, {"protocol_sha256": protocol_hash, "family_count": 2, "case_count": 10, "all_10_PASS": json.loads(qualification.REFERENCE_OUT.read_text())["all_20_PASS"]})
targets = rewrite(qualification.TARGETS_OUT, {"protocol_sha256": protocol_hash, "family_count": 2, "candidate_count": 10})
core = rewrite(qualification.CORE_OUT, {"protocol_sha256": protocol_hash, "case_count": 10, "all_10_PASS": json.loads(qualification.CORE_OUT.read_text())["all_20_PASS"]})
paths = rewrite(qualification.PATHS_OUT, {"protocol_sha256": protocol_hash, "family_count": 2, "all_2_families_resolution_support_PASS": json.loads(qualification.PATHS_OUT.read_text())["all_4_families_resolution_support_PASS"]})
conservation = rewrite(qualification.CONSERVATION_OUT, {"protocol_sha256": protocol_hash, "family_count": 2, "case_count": 10, "all_10_PASS": json.loads(qualification.CONSERVATION_OUT.read_text())["all_20_PASS"]})
family = rewrite(qualification.FAMILY_OUT, {"protocol_sha256": protocol_hash, "family_count": 2, "all_2_families_materialization_authorized": json.loads(qualification.FAMILY_OUT.read_text())["all_4_families_materialization_authorized"]})

for family_id, directory in (("V02_BLIND_VALIDATION_01", "blind_validation"), ("V02_BLIND_TEST_01", "blind_test")):
    formula = next(row for row in json.loads((ROOT / "blind_family_generator/blind_family_formulas_v0_2.json").read_text())["families"] if row["family_id"] == family_id)
    summary = {
        "family_id": family_id,
        "role": formula["role"],
        "root_seed": formula["root_seed"],
        "formula_hash": formula["formula_hash"],
        "derivative_hash": formula["derivative_hash"],
        "protocol_sha256": protocol_hash,
        "case_count": 5,
        "physical_PASS": next(row for row in physical["families"] if row["family_id"] == family_id)["family_5_of_5_PASS"],
        "reference_PASS": next(row for row in reference["families"] if row["family_id"] == family_id)["family_5_of_5_PASS"],
        "resolution_support_PASS": next(row for row in paths["families"] if row["family_id"] == family_id)["family_paths_PASS"],
        "conservation_PASS": next(row for row in conservation["families"] if row["family_id"] == family_id)["family_5_of_5_PASS"],
        "whole_family_status": next(row for row in family["families"] if row["family_id"] == family_id)["whole_family_status"],
        "partial_record_selection_permitted": False,
        "regularity_role": "diagnostic_only",
    }
    summary["status"] = "PASS" if all(summary[key] is True for key in ("physical_PASS", "reference_PASS", "resolution_support_PASS", "conservation_PASS")) and summary["whole_family_status"] == "PASS" else "FAIL"
    output = ROOT / directory / "family_qualification.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

print(json.dumps({"physical": physical["all_2_families_PASS"], "reference": reference["all_10_PASS"], "target_core": core["all_10_PASS"], "paths": paths["all_2_families_resolution_support_PASS"], "conservation": conservation["all_10_PASS"], "families": family["all_2_families_materialization_authorized"]}, sort_keys=True))
