import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01f5_requalification_design"


def test_unique_design_status_only_allows_stage01f5b_application():
    config = yaml.safe_load((STAGE / "configs/preregistered_stage01f5.yml").read_text())
    evaluation = json.loads((STAGE / "results/stage01f5_evaluation.json").read_text())
    machine = config["state_machine"]
    assert evaluation["status"] in machine["allowed_statuses"]
    assert evaluation["status"] == config["final_status"]
    assert evaluation["status"] == "PLATEAU_AWARE_REQUALIFICATION_DESIGN_APPROVED"
    assert evaluation["stage01f5b_execution_application_eligible"]
    assert machine["approved_status_allows_only"] == "apply_for_stage01f5b_execution"
    assert machine["approved_status_does_not_start_execution"]
    assert evaluation["numerical_runs_executed"] == 0
    assert not evaluation["stage01f5b_started"]
    assert not evaluation["stage01g_started"]
    assert not evaluation["v3_started"]
    assert not evaluation["stage02_started"]
    assert not evaluation["v2_qualification_generated"]
    assert not evaluation["stage01g_qualification_generated"]
    assert not evaluation["v3_qualification_generated"]
    assert not evaluation["stage02_qualification_generated"]
