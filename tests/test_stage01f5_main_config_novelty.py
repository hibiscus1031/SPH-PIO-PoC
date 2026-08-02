import json
import math
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01f5_requalification_design"


def test_n20_main_configuration_and_shell_midpoint_are_exactly_frozen():
    config = yaml.safe_load((STAGE / "configs/preregistered_stage01f5.yml").read_text())
    main = config["main_configuration"]
    expected_ratio = (math.sqrt(18) + math.sqrt(20)) / 2
    assert (main["resolution"], main["particle_count"], main["dx"]) == (20, 400, 0.1)
    assert math.isclose(main["support_ratio"], expected_ratio, rel_tol=0, abs_tol=1e-15)
    assert math.isclose(main["support_radius"], 0.1 * expected_ratio, rel_tol=0, abs_tol=1e-15)
    assert main["t_final"] == 0.015
    assert main["immutable_during_execution"]


def test_static_novelty_audit_excludes_old_trajectory_evidence():
    audit = json.loads((STAGE / "results/main_config_novelty_audit.json").read_text())
    assert audit["status"] == "PASS"
    assert audit["novel"]
    assert all(audit["checks"].values())
