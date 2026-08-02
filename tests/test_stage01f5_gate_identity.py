from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
F4 = ROOT / "06_experiments/stage_01f4_protocol_adjudication/configs/preregistered_stage01f4.yml"
F5 = ROOT / "06_experiments/stage_01f5_requalification_design/configs/preregistered_stage01f5.yml"


def test_t1_to_t5_thresholds_preserve_stage01f4_identity():
    old = yaml.safe_load(F4.read_text())["time_gates"]
    new = yaml.safe_load(F5.read_text())["time_gates"]
    assert new["T2"]["minimum"] == old["T2"]["minimum"] == 1.80
    assert new["T3"]["interval"] == old["T3"]["interval"] == [1.70, 2.30]
    assert new["T4"]["multiplier"] == 20.0
    assert new["T4"]["minimum_points_each_combination"] == old["T4"]["minimum_usable_points_per_field_and_norm"] == 4
    assert new["T5"]["maximum"] == old["T5"]["finest_to_coarsest_maximum_ratio"] == 0.30
    assert new["any_failure_blocks_pass"]


def test_p1_to_p3_thresholds_preserve_stage01f4_identity():
    old = yaml.safe_load(F4.read_text())["platform_gates"]
    new = yaml.safe_load(F5.read_text())["platform_gates"]
    assert new["P1"]["maximum"] == old["P1"]["maximum"] == 0.01
    assert new["P2"]["maximum"] == old["P2"]["maximum"] == 0.01
    assert new["P3"]["maximum"] == old["P3"]["maximum"] == 2.0
    assert not new["P3"]["strict_monotonicity_inside_platform_required"]
    assert not new["diagnostic_sign_is_qualification_gate"]
