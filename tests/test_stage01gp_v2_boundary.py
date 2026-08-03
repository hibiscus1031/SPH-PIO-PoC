import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
G_CONFIG = ROOT / "06_experiments/stage_01g_validation_design/configs/preregistered_stage01g.yml"
GP_RESULT = ROOT / "06_experiments/stage_01gp_preexecution_audit/results/stage01gp_evaluation.json"


def test_no_v2_state_and_all_future_qualification_boundaries_remain_closed():
    config = yaml.safe_load(G_CONFIG.read_text())
    boundary = config["v2_boundary"]
    assert boundary["current_v2_status"] is None
    assert boundary["pass_requires"] == [
        "SHEAR1-SHEAR8 PASS", "ACOUSTIC1-ACOUSTIC10 PASS",
        "Stage 01F5B frozen identity PASS", "hard safety PASS",
        "complete uncertainty budget", "complete provenance",
    ]
    assert boundary["future_fail_status"] == "V2_QUALIFICATION_FAIL"
    assert boundary["future_incomplete_status"] == "V2_QUALIFICATION_EVIDENCE_INCOMPLETE"
    assert boundary["pass_automatically_starts_v3"] is False
    assert boundary["pass_automatically_starts_stage02"] is False
    assert boundary["pass_authorizes_training_or_labels"] is False
    assert json.loads(GP_RESULT.read_text())["v2_status"] is None
