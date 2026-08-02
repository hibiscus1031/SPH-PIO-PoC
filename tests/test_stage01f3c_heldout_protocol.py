from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "06_experiments/stage_01f3c_ct2_adjudication/configs/preregistered_stage01f3c.yml"


def test_heldout_configuration_is_distinct_and_noninterpolated():
    config = yaml.safe_load(CONFIG.read_text())
    n32 = config["n32"]
    heldout = config["heldout"]
    assert (heldout["resolution"], heldout["support_ratio"], heldout["t_final"]) == (24, 4.5, 0.01)
    assert (heldout["resolution"], heldout["support_ratio"], heldout["t_final"]) != (
        n32["resolution"], n32["support_ratio"], n32["t_final"]
    )
    assert heldout["dt"] == [0.001, 0.0005, 0.00025, 0.000125, 0.0000625]
    assert heldout["sample_count"] == 11
    assert heldout["deterministic_repeat_dt"] == min(heldout["dt"])
