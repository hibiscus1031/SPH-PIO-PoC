import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01f5q_space_horizon_amendment"


def test_unique_ready_status_only_allows_stage01f5b_application():
    config = yaml.safe_load((STAGE / "configs/formal_space_horizon_amendment.yml").read_text())
    evaluation = json.loads((STAGE / "results/stage01f5q_evaluation.json").read_text())
    assert evaluation["status"] in config["allowed_statuses"]
    assert evaluation["status"] == config["final_status"] == "FORMAL_SPACE_EXECUTION_BUNDLE_READY"
    assert evaluation["stage01f5b_execution_application_eligible"]
    assert evaluation["numerical_runs_executed"] == 0
    assert not evaluation["historical_stage01f5p_status_changed"]
    assert not evaluation["stage01f5b_started"]
    assert not evaluation["stage01g_started"]
    assert not evaluation["v3_started"]
    assert not evaluation["stage02_started"]
    assert not evaluation["v2_qualification_generated"]
    assert not evaluation["v3_qualification_generated"]
