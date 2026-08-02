import csv
import hashlib
import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01f5q_space_horizon_amendment"


def test_all_69_dry_resolutions_are_complete_and_unique():
    with (STAGE / "results/stage01f5q_dry_resolution_audit.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == len({row["run_id"] for row in rows}) == 69
    assert len({row["output_directory"] for row in rows}) == 69
    assert all(all(value for value in row.values()) for row in rows)
    assert all(row["resolution_status"] == "RESOLVED" for row in rows)
    assert sum(row["t_final_contract"] == "0.02" for row in rows) == 31
    assert sum(row["t_final_contract"] == "0.015" for row in rows) == 36
    assert sum(row["steps_or_integration_contract"] == "20" for row in rows) == 2
    forbidden = {"null", "implicit_default", "unresolved", "UNKNOWN", "TBD"}
    assert not any(value in forbidden for row in rows for value in row.values())


def test_bundle_v3_hashes_and_gate_identities_are_reproducible():
    bundle = json.loads((STAGE / "manifests/stage01f5_execution_bundle_v3.json").read_text())
    assert bundle["schema_version"] == 3
    assert bundle["status"] == "FORMAL_SPACE_EXECUTION_BUNDLE_READY"
    assert bundle["numerical_runs_executed"] == 0
    for item in (
        bundle["provenance"]["original_64_row_matrix"],
        bundle["provenance"]["extended_69_row_matrix"],
        bundle["n64_dependency_dag"],
        bundle["dry_resolution"],
    ):
        assert hashlib.sha256((ROOT / item["path"]).read_bytes()).hexdigest() == item["sha256"]
    for prefix in ("horizon_amendment", "common_times", "parameter_binding"):
        path = bundle["formal_space_binding"][prefix + "_path"]
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == bundle["formal_space_binding"][prefix + "_sha256"]
    f5 = yaml.safe_load((ROOT / bundle["frozen_gate_hashes"]["source"]).read_text())
    sections = {
        "T1_T5": f5["time_gates"],
        "P1_P3": f5["platform_gates"],
        "H1_H5": f5["heldout"]["gates"],
        "S1_S4": f5["spatial_matrix"]["gates"],
        "hard_safety": f5["hard_safety_gates"],
    }
    for name, section in sections.items():
        canonical = json.dumps(section, sort_keys=True, separators=(",", ":")).encode()
        assert hashlib.sha256(canonical).hexdigest() == bundle["frozen_gate_hashes"][name]
    assert bundle["parameter_resolution_priority"][-1] == "no_implicit_default_or_inference"
