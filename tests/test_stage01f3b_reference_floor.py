from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[1];CFG=yaml.safe_load((ROOT/"06_experiments/stage_01f3b_mms_convergence/configs/preregistered_stage01f3b.yml").read_text())

def test_reference_floor_is_preregistered_before_fit()->None:
    block=CFG["semidiscrete_time"]
    assert block["reference_floor_multiplier"]==20.0
    assert block["minimum_valid_points"]==4
    source=(ROOT/"06_experiments/stage_01f3b_mms_convergence/analyze_stage01f3b.py").read_text()
    assert 'error > block["reference_floor_multiplier"] * uncertainty[field]' in source
