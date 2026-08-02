from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
F5 = ROOT / "06_experiments/stage_01f5_requalification_design/configs/preregistered_stage01f5.yml"
Q = ROOT / "06_experiments/stage_01f5q_space_horizon_amendment/configs/formal_space_horizon_amendment.yml"


def test_n20_and_n28_remain_at_0p015_and_16_common_times():
    old = yaml.safe_load(F5.read_text())
    amendment = yaml.safe_load(Q.read_text())["unchanged_identity"]
    assert old["main_configuration"]["t_final"] == amendment["n20_main_t_final"] == 0.015
    assert old["main_configuration"]["common_times"]["count"] == amendment["n20_main_common_time_count"] == 16
    assert old["heldout"]["t_final"] == amendment["n28_heldout_t_final"] == 0.015
    assert old["heldout"]["common_times"]["count"] == amendment["n28_heldout_common_time_count"] == 16
    assert amendment["T1_T5"] == "unchanged"
    assert amendment["P1_P3"] == "unchanged"
    assert amendment["H1_H5"] == "unchanged"
