"""Unique Stage 01F3B status evaluator."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / "06_experiments/stage_01f3b_mms_convergence"
CONFIG = STAGE / "configs/preregistered_stage01f3b.yml"


def classify_status(checks: dict[str, bool]) -> str:
    if not checks["evidence_complete"] or not checks["provenance_complete"]:
        return "MMS_CONVERGENCE_EVIDENCE_INCOMPLETE"
    if not all(checks[key] for key in ("prerequisite", "semidiscrete_time", "continuous_time", "hard_paths", "balance_resources", "determinism", "reference_source_topology")):
        return "MMS_CONVERGENCE_VERIFICATION_FAIL"
    if checks["space_formal_pass"]:
        return "MMS_CONVERGENCE_VERIFICATION_PASS"
    if checks["space_platform_explainable"]:
        return "MMS_CONVERGENCE_VERIFICATION_CONDITIONAL"
    return "MMS_CONVERGENCE_VERIFICATION_FAIL"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    output = STAGE / "results/stage01f3b_evaluation.json"
    if output.exists():
        raise RuntimeError(f"refusing to overwrite {output}")
    names = (
        "prerequisite_checks.json", "semidiscrete_time_analysis.json",
        "continuous_time_analysis.json", "space_dt_selection.json",
        "space_analysis.json", "fixed_ratio_analysis.json",
        "determinism_analysis.json", "balance_resource_summary.json",
        "order_gci_analysis.json", "n64_decision.json",
    )
    complete = all((STAGE / "results" / name).is_file() for name in names)
    data = {name: json.loads((STAGE / "results" / name).read_text()) for name in names} if complete else {}
    config = yaml.safe_load(CONFIG.read_text())
    n64_complete = True
    if complete and data["n64_decision.json"]["required"]:
        preflight = STAGE / "results/n64_preflight.json"
        n64_complete = preflight.exists() and all((STAGE / "run_summaries" / f"f3b_space_{letter}_n64.json").exists() for letter in ("a", "b"))
    evidence_complete = complete and n64_complete
    space = data.get("space_analysis.json", {})
    hard_paths = complete and data["fixed_ratio_analysis.json"]["status"] == "PASS" and all(solution["checks"].get("four_of_four_hard_paths", False) for solution in space.get("solutions", {}).values())
    spatial_endpoint_and_slope = False
    if complete:
        a = space["solutions"]["MMS_A"]; b = space["solutions"]["MMS_B"]
        spatial_endpoint_and_slope = all((
            a["checks"]["velocity_endpoint_improves"], a["checks"]["density_endpoint_improves"], a["checks"]["pressure_endpoint_improves"], a["checks"]["three_positive_slopes"],
            b["checks"]["position_endpoint_improves"], b["checks"]["velocity_endpoint_improves"], b["checks"]["density_pressure_endpoint_improve"], b["checks"]["four_positive_slopes"],
        ))
    downstream_false = all(not config["scope"][key] for key in ("stage01g_started", "v3_started", "stage02_started", "training_started", "labels_generated"))
    checks = {
        "evidence_complete": evidence_complete,
        "provenance_complete": complete and downstream_false,
        "prerequisite": complete and data["prerequisite_checks.json"]["status"] == "PASS",
        "semidiscrete_time": complete and data["semidiscrete_time_analysis.json"]["status"] == "PASS",
        "continuous_time": complete and data["continuous_time_analysis.json"]["status"] == "PASS",
        "hard_paths": hard_paths,
        "balance_resources": complete and data["balance_resource_summary.json"]["status"] == "PASS",
        "determinism": complete and data["determinism_analysis.json"]["status"] == "PASS",
        "reference_source_topology": complete and data["prerequisite_checks.json"]["status"] == "PASS" and hard_paths,
        "space_formal_pass": complete and space.get("status") == "PASS",
        "space_platform_explainable": complete and hard_paths and spatial_endpoint_and_slope,
    }
    status = classify_status(checks)
    evidence = {name: {"path": f"06_experiments/stage_01f3b_mms_convergence/results/{name}", "sha256": sha(STAGE / "results" / name)} for name in names if (STAGE / "results" / name).exists()}
    payload = {
        "schema_version": "sph-pio-poc.stage01f3b.evaluation.v1",
        "status": status, "checks": checks, "evidence": evidence,
        "stage01f3r_status_frozen": "SEMIDISCRETE_REFERENCE_QUALIFIED_DENSE_EQUIVALENT",
        "stage01f3_historical_status_unchanged": "MMS_CONVERGENCE_VERIFICATION_FAIL",
        "stage01g_application_permitted": status == "MMS_CONVERGENCE_VERIFICATION_PASS",
        "scope": config["scope"], "config_sha256": sha(CONFIG),
        "code_git_hash": subprocess.check_output(("git", "rev-parse", "HEAD"), cwd=ROOT, text=True).strip(),
    }
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": status}))
    return 0 if status in ("MMS_CONVERGENCE_VERIFICATION_PASS", "MMS_CONVERGENCE_VERIFICATION_CONDITIONAL") else 1


if __name__ == "__main__":
    raise SystemExit(main())
