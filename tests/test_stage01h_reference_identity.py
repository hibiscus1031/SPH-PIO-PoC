import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "06_experiments/stage_01h_viscous_decay_diagnosis/results/stage01h_reference_identity.json"


def test_analytic_reference_decay_identity_is_exact():
    value = json.loads(RESULT.read_text())
    expected = 0.02 * (2.0 * math.pi) ** 2
    assert value["reference_kind"] == "analytic shear solution"
    assert abs(value["lambda_formula"] - expected) < 1.0e-15
    assert value["relative_difference"] < 1.0e-12
    assert value["reference_implementation_error_detected"] is False
    assert value["reference_fit_r_squared"] > 1.0 - 1.0e-12
