import csv
from fractions import Fraction
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01f5q_space_horizon_amendment"


def test_n64_smokes_keep_the_independent_20_step_horizon():
    config = yaml.safe_load((STAGE / "configs/formal_space_horizon_amendment.yml").read_text())
    smoke = config["n64_smoke_horizon"]
    assert smoke["run_ids"] == ["f5_n64_smoke_a", "f5_n64_smoke_b"]
    assert smoke["formal_space_binding_forbidden"]
    assert smoke["steps"] == 20
    assert not smoke["uses_formal_space_common_times"]
    expected = [(Fraction(1, 16000), Fraction(1, 800)), (Fraction(1, 32000), Fraction(1, 1600))]
    for branch, (dt, t_final) in zip(smoke["branches"], expected, strict=True):
        assert Fraction(str(branch["dt_space"])) == dt
        assert Fraction(str(branch["t_final_smoke"])) == t_final
        assert dt * 20 == t_final
    with (STAGE / "manifests/stage01f5q_space_parameter_binding.csv").open() as stream:
        bound = {row["run_id"] for row in csv.DictReader(stream)}
    assert set(smoke["run_ids"]).isdisjoint(bound)
