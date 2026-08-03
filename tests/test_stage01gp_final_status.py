import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "06_experiments/stage_01gp_preexecution_audit"
REPORT = ROOT / "07_reports/stage_01gp_final_report.md"
ALLOWED = {
    "INDEPENDENT_VALIDATION_EXECUTION_READY",
    "INDEPENDENT_VALIDATION_EXECUTION_BLOCKED",
    "INDEPENDENT_VALIDATION_AUDIT_INCOMPLETE",
}


def test_final_status_is_unique_allowed_ready_and_zero_execution():
    evaluation = json.loads((AUDIT / "results/stage01gp_evaluation.json").read_text())
    assert evaluation["unique_status"] in ALLOWED
    assert evaluation["unique_status"] == "INDEPENDENT_VALIDATION_EXECUTION_READY"
    assert all(evaluation["audit_checks"].values())
    assert evaluation["numerical_run_count"] == 0
    assert evaluation["benchmark_execution_count"] == 0
    assert evaluation["v2_status"] is None
    report = REPORT.read_text()
    assert report.count("`INDEPENDENT_VALIDATION_EXECUTION_READY`") == 1
    assert "eligible to **apply for a separately authorized Stage 01G independent-validation execution stage**" in report
    assert "Numerical run count = **0**" in report
