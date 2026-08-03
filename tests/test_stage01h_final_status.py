import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01h_viscous_decay_diagnosis"
REPORTS = (
    "stage01h_freeze_and_scope.md", "stage01h_shear_error_decomposition.md",
    "stage01h_effective_viscosity.md", "stage01h_support_sensitivity.md",
    "stage01h_time_error_audit.md", "stage01h_operator_diagnosis.md",
    "stage01h_final_report.md",
)


def test_stage01h_unique_status_and_downstream_boundary():
    evaluation = json.loads((STAGE / "results/stage01h_evaluation.json").read_text())
    assert evaluation["unique_status"] == "VISCOSITY_DIAGNOSIS_COMPLETE"
    assert evaluation["classification"] == "FINITE_RESOLUTION_DOMINANT"
    assert evaluation["operator_form_failure_confirmed"] is False
    assert evaluation["viscosity_operator_redesign_required"] is False
    assert evaluation["solver_modified"] is False
    assert evaluation["benchmark_modified"] is False
    assert evaluation["evaluator_gate_modified"] is False
    assert evaluation["uncertainty_complete"] is True
    assert not any(evaluation["downstream"].values())


def test_all_reports_and_evidence_hashes_are_complete():
    assert all((ROOT / "07_reports" / name).is_file() for name in REPORTS)
    manifest = STAGE / "results/stage01h_evidence_sha256.csv"
    with manifest.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) >= 17
    for row in rows:
        path = ROOT / row["path"]
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]
