from pathlib import Path
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "01_solver"))
from manufactured_solutions.mms_b_dop853_reference import sensitivity_bundle  # noqa: E402
from manufactured_solutions.particle_initialization import regular_initialization  # noqa: E402


def test_mms_b_dop853_reference_sensitivity() -> None:
    positions = regular_initialization("MMS_B", 16).positions
    bundle = sensitivity_bundle(positions, (0.0, 0.0025, 0.005, 0.01, 0.02))
    assert bundle["baseline_tighter_linf"] <= 1e-10
    assert bundle["baseline_half_max_step_linf"] <= 1e-10
    assert np.array_equal(bundle["baseline"][0], positions.numpy())
    assert np.isfinite(bundle["baseline"]).all()
