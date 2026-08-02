import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01f5b_requalification_execution"
ALLOWED = {"PLATEAU_AWARE_MMS_REQUALIFICATION_PASS", "PLATEAU_AWARE_MMS_REQUALIFICATION_FAIL", "PLATEAU_AWARE_MMS_REQUALIFICATION_EVIDENCE_INCOMPLETE"}


def test_final_evaluator_permits_only_three_unique_statuses():
    source = (STAGE / "evaluate_stage01f5b.py").read_text()
    assert "CONDITIONAL" not in source
    for value in ALLOWED:
        assert value in source
    result = STAGE / "results/stage01f5b_evaluation.json"
    if result.exists():
        assert json.loads(result.read_text())["unique_status"] in ALLOWED

