import importlib.util
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "06_experiments/stage_01f3c_ct2_adjudication/analyze_stage01f3c.py"
SPEC = importlib.util.spec_from_file_location("stage01f3c_analysis", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_vector_closure_is_evaluated_before_norm_reduction():
    space = np.array([[[1.0, -2.0], [0.5, 0.25]]])
    temporal = np.array([[[-0.4, 0.3], [0.1, -0.2]]])
    total = space + temporal
    metrics = MODULE.metric_block(total, space, temporal)
    assert metrics["maximum_absolute_vector_closure"] < 1.0e-15
    assert metrics["maximum_relative_vector_closure"] < 1.0e-15
    assert metrics["squared_norm_reconstruction_absolute_residual"] < 1.0e-15
