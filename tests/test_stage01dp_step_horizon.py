from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG = PROJECT_ROOT / "06_experiments" / "stage_01dp_resource_policy" / "configs" / "preregistered_resource_policy.yml"


def test_maximum_planned_step_horizon_is_exact_and_covered_by_r5() -> None:
    configuration = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    horizon = configuration["evidence_horizon"]
    calculated = Decimal(str(horizon["planned_final_time"])) / Decimal(str(horizon["minimum_planned_time_step"]))
    assert calculated == Decimal(1600)
    assert int(horizon["maximum_planned_formal_trajectory_steps"]) == 1600
    assert int(horizon["r5_default_gc_evidence_steps"]) == 2000
    assert int(horizon["r5_default_gc_evidence_steps"]) >= int(horizon["maximum_planned_formal_trajectory_steps"])
