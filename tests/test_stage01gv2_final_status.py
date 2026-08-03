import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "06_experiments/stage_01g_execution_preflight_v2"
AUTHORIZED = "INDEPENDENT_VALIDATION_EXECUTION_AUTHORIZED"


def test_unique_preflight_status_is_authorized_only_after_every_check_passes():
    evaluation = json.loads((V2 / "results/stage01gv2_evaluation.json").read_text())
    assert evaluation["unique_status"] == AUTHORIZED
    assert all(evaluation["checks"].values())
    assert evaluation["current_v2_status"] == "V2_QUALIFICATION_EVIDENCE_INCOMPLETE"
    assert all(value == 0 for value in evaluation["execution_counts"].values())
    assert evaluation["authorization"] == {
        "stage01g_benchmark_execution_may_start": True,
        "automatic_benchmark_start": False,
        "v2_status_generated": False,
        "stage02_started": False,
    }


def test_all_ten_execution_risks_pass_and_final_report_states_boundary():
    with (V2 / "manifests/stage01gv2_risk_scan.csv").open(newline="") as stream:
        risks = list(csv.DictReader(stream))
    assert len(risks) == 10
    assert [row["risk_id"] for row in risks] == [str(index) for index in range(1, 11)]
    assert {row["status"] for row in risks} == {"PASS"}

    report = (ROOT / "07_reports/stage01g_preflight_v2_final.md").read_text()
    assert report.count(AUTHORIZED) == 1
    assert "V2_QUALIFICATION_EVIDENCE_INCOMPLETE" in report
    assert "does not start it automatically" in report
