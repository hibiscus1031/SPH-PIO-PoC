from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "06_experiments/stage_01g_validation_design/configs/preregistered_stage01g.yml"


def test_v2_is_not_declared_and_downstream_actions_remain_closed():
    config = yaml.safe_load(CONFIG.read_text())
    boundary = config["v2_boundary"]
    assert config["stage"]["v2_status_generated"] is False
    assert boundary["current_v2_status"] is None
    assert boundary["future_pass_status"] == "V2_QUALIFICATION_PASS"
    assert boundary["future_fail_status"] == "V2_QUALIFICATION_FAIL"
    assert boundary["future_incomplete_status"] == "V2_QUALIFICATION_EVIDENCE_INCOMPLETE"
    assert len(boundary["pass_requires"]) == 6
    assert boundary["pass_automatically_starts_v3"] is False
    assert boundary["pass_automatically_starts_stage02"] is False
    assert boundary["pass_authorizes_training_or_labels"] is False

    excluded = set(config["domain_of_validity"]["excluded"])
    assert excluded == {"free_surface", "solid_wall_boundary", "shocks", "multiphase", "FSI", "turbulence", "3D", "learned_corrector"}
