"""Emit the unique Stage 01F3-R reference-qualification status."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / "06_experiments/stage_01f3r_reference_qualification"
CONFIG = STAGE / "configs/preregistered_stage01f3r.yml"
RESULTS = STAGE / "results"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name: str) -> dict[str, Any]:
    return json.loads((RESULTS / name).read_text())


def main() -> int:
    output = RESULTS / "stage01f3r_evaluation.json"
    if output.exists():
        raise RuntimeError(f"refusing to overwrite {output}")
    names = {
        "freeze": "stage01f3_freeze_audit.json",
        "cutoff": "cutoff_smoothness_summary.json",
        "equivalence": "sparse_dense_equivalence_summary.json",
        "events": "topology_event_summary.json",
        "mms_a": "mms_a_reference_qualification.json",
        "mms_b": "mms_b_reference_qualification.json",
        "pilot": "pilot_mms_b_n16.json",
    }
    evidence_complete = all((RESULTS / name).is_file() for name in names.values())
    loaded = {key: load(name) for key, name in names.items()} if evidence_complete else {}
    config = yaml.safe_load(CONFIG.read_text())
    prohibited_scope_false = all(value is False for value in config["scope"].values())
    cutoff_path_pass = evidence_complete and all(
        loaded[key]["status"] == "PASS" for key in ("cutoff", "equivalence", "events")
    )
    dense_reference_pass = evidence_complete and all(
        loaded[key]["status"] == "PASS" for key in ("mms_a", "mms_b")
    )
    pilot_pass = evidence_complete and loaded["pilot"]["status"] == "PASS"
    freeze_pass = evidence_complete and loaded["freeze"]["status"] == "PASS"
    if not evidence_complete or not freeze_pass or not dense_reference_pass or not pilot_pass or not prohibited_scope_false:
        status = "SEMIDISCRETE_REFERENCE_EVIDENCE_INCOMPLETE"
    elif not cutoff_path_pass:
        status = "SEMIDISCRETE_REFERENCE_FAIL_CUTOFF_DISCONTINUITY"
    else:
        status = "SEMIDISCRETE_REFERENCE_QUALIFIED_DENSE_EQUIVALENT"
    evidence = {
        name: {"path": f"06_experiments/stage_01f3r_reference_qualification/results/{filename}", "sha256": sha(RESULTS / filename)}
        for name, filename in names.items()
    } if evidence_complete else {}
    references = {}
    for path in sorted((STAGE / "references").glob("*.npz")):
        references[path.stem] = {"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path)}
    payload = {
        "schema_version": "sph-pio-poc.stage01f3r.evaluation.v1",
        "status": status,
        "checks": {
            "evidence_complete": evidence_complete,
            "stage01f3_frozen": freeze_pass,
            "cutoff_sparse_dense_topology": cutoff_path_pass,
            "dense_three_level_references": dense_reference_pass,
            "single_pilot": pilot_pass,
            "prohibited_scope_false": prohibited_scope_false,
        },
        "stage01f3_historical_status_unchanged": "MMS_CONVERGENCE_VERIFICATION_FAIL",
        "stage01f3b_eligibility": status == "SEMIDISCRETE_REFERENCE_QUALIFIED_DENSE_EQUIVALENT",
        "scope": config["scope"],
        "evidence": evidence,
        "references": references,
        "config_sha256": sha(CONFIG),
        "code_git_hash": subprocess.check_output(("git", "rev-parse", "HEAD"), cwd=ROOT, text=True).strip(),
    }
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": status}))
    return 0 if status == "SEMIDISCRETE_REFERENCE_QUALIFIED_DENSE_EQUIVALENT" else 1


if __name__ == "__main__":
    raise SystemExit(main())
