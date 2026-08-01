"""Evaluate only Stage 01F2 implementation gates and evidence completeness."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import yaml


ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / "06_experiments" / "stage_01f2_mms_implementation"
CONFIG = STAGE / "configs" / "preregistered_stage01f2.yml"
OUTPUT = STAGE / "results" / "stage01f2_evaluation.json"


def load(path: Path) -> dict[str, Any] | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def state_identical(left: str, right: str) -> bool:
    with np.load(ROOT / left) as first, np.load(ROOT / right) as second:
        return first.files == second.files and all(np.array_equal(first[key], second[key]) for key in first.files)


def main() -> int:
    if OUTPUT.exists():
        raise SystemExit("refusing to overwrite Stage 01F2 evaluation")
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    required = {
        "freeze": STAGE / "results" / "stage01f_freeze_audit.json",
        "mass": STAGE / "results" / "mass_initialization_summary.json",
        "ad_fd": STAGE / "results" / "source_ad_fd_summary.json",
        **{f"zero_{task['run_id']}": STAGE / "results" / f"zero_source_{task['run_id']}.json" for task in cfg["zero_source_regression"]},
        **{f"reference_n{n}": STAGE / "results" / f"mms_b_n{n}_reference_summary.json" for n in (16, 32)},
        **{f"run_{task['run_id']}": STAGE / "run_summaries" / f"{task['run_id']}.json" for task in cfg["mms_runs"]},
    }
    loaded = {name: load(path) for name, path in required.items()}
    missing = [name for name, payload in loaded.items() if payload is None]
    explicit_failures = [name for name, payload in loaded.items() if payload is not None and payload.get("status") != "PASS"]
    index = list(csv.DictReader((STAGE / "results" / "campaign_index.csv").open(encoding="utf-8"))) if (STAGE / "results" / "campaign_index.csv").exists() else []
    child_policy = bool(index) and all(row["child_reclaimed"] == "True" and row["scalar_only_summary"] == "True" and row["return_code"] == "0" for row in index)
    repeat_checks = {}
    if not missing:
        repeat_checks = {
            "A2": state_identical(loaded["run_A2_repeat1"]["state_path"], loaded["run_A2_repeat2"]["state_path"]),
            "B2": state_identical(loaded["run_B2_repeat1"]["state_path"], loaded["run_B2_repeat2"]["state_path"]),
        }
    if missing:
        status = "MMS_IMPLEMENTATION_EVIDENCE_INCOMPLETE"
    elif explicit_failures or not child_policy or not all(repeat_checks.values()):
        status = "MMS_IMPLEMENTATION_FAIL"
    else:
        status = "MMS_IMPLEMENTATION_VERIFIED_PASS"
    payload = {
        "schema_version": "sph-pio-poc.stage01f2.evaluation.v1",
        "status": status, "missing_evidence": missing,
        "failed_evidence": explicit_failures,
        "stage01f_frozen_identity_pass": loaded.get("freeze", {}).get("status") == "PASS" if loaded.get("freeze") else False,
        "source_disabled_regression_pass": all(loaded.get(f"zero_{task['run_id']}", {}).get("status") == "PASS" for task in cfg["zero_source_regression"]),
        "source_start_midpoint_contract_pass": all(loaded.get(f"run_{task['run_id']}", {}).get("checks", {}).get("source_contract", False) for task in cfg["mms_runs"]),
        "mms_a_closed_reference_pass": not missing,
        "mms_b_reference_sensitivity_pass": all(loaded.get(f"reference_n{n}", {}).get("status") == "PASS" for n in (16, 32)),
        "mass_initialization_pass": loaded.get("mass", {}).get("status") == "PASS" if loaded.get("mass") else False,
        "internal_external_balance_pass": all(loaded.get(f"run_{task['run_id']}", {}).get("checks", {}).get("force_assembly", False) and loaded.get(f"run_{task['run_id']}", {}).get("checks", {}).get("momentum_update", False) for task in cfg["mms_runs"]),
        "implementation_smoke_pass": all(loaded.get(f"run_{task['run_id']}", {}).get("status") == "PASS" for task in cfg["mms_runs"]),
        "deterministic_repeat_checks": repeat_checks,
        "source_ad_fd_pass": loaded.get("ad_fd", {}).get("status") == "PASS" if loaded.get("ad_fd") else False,
        "resource_policy_pass": child_policy and all(loaded.get(f"run_{task['run_id']}", {}).get("checks", {}).get("current_rss", False) and loaded.get(f"run_{task['run_id']}", {}).get("checks", {}).get("peak_rss", False) and loaded.get(f"run_{task['run_id']}", {}).get("checks", {}).get("rss_quartile_absolute", False) and loaded.get(f"run_{task['run_id']}", {}).get("checks", {}).get("rss_quartile_relative", False) and loaded.get(f"run_{task['run_id']}", {}).get("checks", {}).get("step_time_ratio", False) for task in cfg["mms_runs"]),
        "child_process_policy_pass": child_policy,
        "application_for_stage01f3_permitted": status == "MMS_IMPLEMENTATION_VERIFIED_PASS",
        "stage01d2_historical_status_changed": False,
        "v3_started": False, "stage02_started": False,
        "training_started": False, "learning_labels_generated": False,
        "evidence_language": ["implementation smoke", "code-path verification", "deterministic repeat", "reference sensitivity", "balance audit"],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"status": status}))
    return 0 if status == "MMS_IMPLEMENTATION_VERIFIED_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
