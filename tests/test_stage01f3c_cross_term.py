import importlib.util
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "06_experiments/stage_01f3c_ct2_adjudication/analyze_stage01f3c.py"
SPEC = importlib.util.spec_from_file_location("stage01f3c_cross", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_negative_cross_term_can_put_total_below_space_platform():
    space = np.array([[[1.0, 0.0]]])
    temporal = np.array([[[-0.25, 0.0]]])
    total = space + temporal
    metrics = MODULE.metric_block(total, space, temporal)
    assert metrics["cross_term_2_space_dot_temporal"] < 0.0
    assert metrics["total_l2"] < metrics["space_l2"]
    assert metrics["cosine_space_temporal"] == -1.0
