from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01f5b_requalification_execution"


def test_strict_phase_order_and_counts():
    config = yaml.safe_load((STAGE / "configs/stage01f5b_execution.yml").read_text())
    assert config["phase_order"] == list("ABCDEFGHIJK")
    assert [len(config["phases"][x]["run_ids"]) for x in config["phase_order"]] == [12, 10, 10, 4, 4, 0, 12, 8, 2, 0, 7]
    source = (STAGE / "run_stage01f5b_campaign.py").read_text()
    assert 'for phase in config["phase_order"]' in source
    assert "commit_decision(decision_path" in source

