import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01g_validation_design"
REPORT = ROOT / "07_reports/stage_01g_final_report.md"
ALLOWED = {
    "INDEPENDENT_VALIDATION_AND_V2_DESIGN_APPROVED",
    "INDEPENDENT_VALIDATION_DESIGN_REJECTED",
    "INDEPENDENT_VALIDATION_DESIGN_INCOMPLETE",
}


def test_final_stage01g_status_is_unique_allowed_and_evidence_backed():
    evaluation = json.loads((STAGE / "results/stage01g_design_evaluation.json").read_text())
    assert evaluation["unique_status"] in ALLOWED
    assert evaluation["unique_status"] == "INDEPENDENT_VALIDATION_AND_V2_DESIGN_APPROVED"
    assert all(evaluation["design_checks"].values())
    assert evaluation["numerical_execution_count"] == 0
    assert evaluation["v2_status"] is None

    report = REPORT.read_text()
    assert report.count("`INDEPENDENT_VALIDATION_AND_V2_DESIGN_APPROVED`") == 1
    assert "eligible to **apply for a separately authorized independent-validation execution stage**" in report
    assert "no benchmark has been run" in report
    assert "V3 and Stage 02 remain unstarted" in report
