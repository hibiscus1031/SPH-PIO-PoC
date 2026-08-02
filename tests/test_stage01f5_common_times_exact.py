from decimal import Decimal
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "06_experiments/stage_01f5_requalification_design/configs/preregistered_stage01f5.yml"


def test_main_and_heldout_use_the_exact_noninterpolated_common_grid():
    config = yaml.safe_load(CONFIG.read_text())
    expected = [index / 1000 for index in range(16)]
    for section in (config["main_configuration"], config["heldout"]):
        grid = section["common_times"]
        assert grid["values"] == expected
        assert grid["count"] == 16
        assert not grid["interpolation_allowed"]
        assert section["t_final"] == expected[-1]
        assert section["dt"] == [0.001, 0.0005, 0.00025, 0.000125, 0.0000625]
        assert all(
            Decimal(str(time)) % Decimal(str(dt)) == 0
            for dt in section["dt"]
            for time in expected
        )
