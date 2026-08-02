from fractions import Fraction
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "06_experiments/stage_01f5q_space_horizon_amendment/configs/formal_space_horizon_amendment.yml"


def test_both_space_step_branches_equal_0p02_exactly():
    contract = yaml.safe_load(CONFIG.read_text())["space_step_contract"]
    expected = [(Fraction(1, 16000), 320), (Fraction(1, 32000), 640)]
    for branch, (dt, steps) in zip(contract["branches"], expected, strict=True):
        assert Fraction(str(branch["dt_space"])) == dt
        assert branch["formal_space_steps"] == steps
        assert dt * steps == Fraction(1, 50)
    assert contract["formal_space_t_final_rational"] == "1/50"
    assert not contract["floating_approximation_used_for_identity_check"]
