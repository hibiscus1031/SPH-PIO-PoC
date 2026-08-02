from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "06_experiments/stage_01f5q_space_horizon_amendment/configs/formal_space_horizon_amendment.yml"


def test_formal_space_horizon_is_a_new_prospective_decision():
    config = yaml.safe_load(CONFIG.read_text())
    formal = config["formal_space"]
    assert config["amendment_type"] == "prospective_pre_execution_design_decision"
    assert formal == {
        "t_final": 0.02,
        "sample_start": 0.0,
        "sample_end": 0.02,
        "sample_interval": 0.001,
        "sample_count": 21,
        "interpolation_allowed": False,
        "construction": "integer_tick_times_0_through_20_divided_by_1000",
        "common_times_csv": "06_experiments/stage_01f5q_space_horizon_amendment/configs/formal_space_common_times.csv",
    }
    rationale = " ".join(config["rationale"])
    assert "not inferred from the N20 or N28" in rationale
    assert "new prospective design decision" in rationale
