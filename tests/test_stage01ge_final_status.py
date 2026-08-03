import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01ge_evaluator_qualification"
REPORT = ROOT / "07_reports/stage_01ge_final_report.md"
ALLOWED = {"INDEPENDENT_VALIDATION_EVALUATOR_READY", "INDEPENDENT_VALIDATION_EVALUATOR_INCOMPLETE"}


def test_final_status_is_unique_ready_and_does_not_generate_v2_or_downstream_state():
    evaluation = json.loads((STAGE / "results/stage01ge_evaluation.json").read_text())
    assert evaluation["unique_status"] in ALLOWED
    assert evaluation["unique_status"] == "INDEPENDENT_VALIDATION_EVALUATOR_READY"
    assert all(evaluation["checks"].values())
    assert evaluation["current_v2_status"] == "V2_QUALIFICATION_EVIDENCE_INCOMPLETE"
    assert not any(evaluation["downstream"].values())
    report = REPORT.read_text()
    assert report.count("`INDEPENDENT_VALIDATION_EVALUATOR_READY`") == 1
    assert "Benchmark execution count = **0**" in report
    assert "eligible to re-apply" in report
