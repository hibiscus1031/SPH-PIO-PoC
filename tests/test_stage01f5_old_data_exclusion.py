from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "06_experiments/stage_01f5_requalification_design/configs/preregistered_stage01f5.yml"


def test_old_data_cannot_enter_new_qualification_or_relax_old_ct2():
    config = yaml.safe_load(CONFIG.read_text())
    assert not config["main_configuration"]["novelty_audit"]["old_trajectory_can_supply_new_evidence"]
    assert not config["anti_posthoc_controls"]["old_stage01f3b_or_stage01f3c_trajectory_can_qualify"]
    assert config["historical_states"]["reclassification_forbidden"]
    assert config["platform_gates"]["old_ct2_percent_tolerance_forbidden"]
    forbidden = config["anti_posthoc_controls"]["after_first_trajectory_forbidden"]
    assert "add_old_trajectory" in forbidden
    assert "delete_adverse_run" in forbidden
