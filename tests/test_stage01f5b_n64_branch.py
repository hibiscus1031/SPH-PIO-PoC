import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01f5b_requalification_execution"


def test_n64_branch_has_seven_runs_and_four_frozen_triggers():
    config = yaml.safe_load((STAGE / "configs/stage01f5b_execution.yml").read_text())
    assert len(config["phases"]["K"]["run_ids"]) == 7
    assert len(config["n64_branch"]["triggers"]) == 4
    decision = STAGE / "manifests/n64_trigger_decision.json"
    if decision.exists():
        payload = json.loads(decision.read_text())
        assert payload["immutable"] is True
        assert payload["decision"] in {"TRIGGERED", "NOT_TRIGGERED"}

