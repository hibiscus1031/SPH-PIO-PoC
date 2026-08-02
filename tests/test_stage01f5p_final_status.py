import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01f5p_branch_completeness"


def test_formal_space_t_final_gap_forces_incomplete_status():
    config = yaml.safe_load((STAGE / "configs/preregistered_stage01f5p.yml").read_text())
    evaluation = json.loads((STAGE / "results/stage01f5p_evaluation.json").read_text())
    assert not config["n64_mms_b_reference"]["formal_space_t_final"]["resolved"]
    assert evaluation["status"] in config["allowed_statuses"]
    assert evaluation["status"] == config["final_status"] == "EXECUTION_MANIFEST_INCOMPLETE"
    assert not evaluation["checks"]["formal_space_t_final_uniquely_resolved"]
    assert evaluation["numerical_runs_executed"] == 0
    assert not evaluation["stage01f5b_execution_application_eligible"]
    assert not evaluation["stage01f5b_started"]
    assert not evaluation["stage01g_started"]
    assert not evaluation["v3_started"]
    assert not evaluation["stage02_started"]
    assert not evaluation["v2_qualification_generated"]
    assert not evaluation["v3_qualification_generated"]
