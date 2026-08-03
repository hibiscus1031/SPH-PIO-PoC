import csv
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "06_experiments/stage_01h_viscous_decay_diagnosis/results/stage01h_effective_viscosity.csv"


def test_effective_viscosity_is_consistent_and_converges_from_below():
    with RESULT.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert [int(row["N"]) for row in rows] == [24, 32, 48]
    k2 = (2.0 * math.pi) ** 2
    biases = []
    for row in rows:
        decay = float(row["lambda_num"])
        nu_eff = float(row["nu_eff"])
        bias = float(row["relative_viscosity_bias"])
        assert abs(nu_eff - decay / k2) < 1.0e-15
        assert row["bias_direction"] == "LOW"
        assert bias < 0.0
        assert float(row["r_squared"]) > 0.999999
        assert abs(float(row["lambda_evaluator_difference"])) < 1.0e-14
        biases.append(abs(bias))
    assert biases[0] > biases[1] > biases[2]
