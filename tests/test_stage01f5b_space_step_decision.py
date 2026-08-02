import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01f5b_requalification_execution"


def test_space_step_rule_is_exact_and_decision_is_immutable_if_present():
    config = yaml.safe_load((STAGE / "configs/stage01f5b_execution.yml").read_text())
    assert config["space_step_decision"]["relative_change_trigger"] == 0.10
    assert config["space_step_decision"]["if_triggered"] == {"dt_space": 3.125e-5, "steps": 640}
    assert config["space_step_decision"]["otherwise"] == {"dt_space": 6.25e-5, "steps": 320}
    decision = STAGE / "manifests/space_step_decision.json"
    if decision.exists():
        payload = json.loads(decision.read_text())
        assert payload["immutable"] is True
        assert len(payload["comparisons"]) == 8

