from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[1];CFG=yaml.safe_load((ROOT/"06_experiments/stage_01f3b_mms_convergence/configs/preregistered_stage01f3b.yml").read_text())

def test_old_smoke_and_pilot_data_are_excluded()->None:
    scope=CFG["scope"]
    assert scope["stage01f2_smoke_reused"] is False
    assert scope["stage01f3_pilot_reused"] is False
    assert scope["stage01f3r_pilot_reused"] is False
    worker=(ROOT/"06_experiments/stage_01f3b_mms_convergence/stage01f3b_worker.py").read_text()
    assert 'startswith("f3b_")' in worker
