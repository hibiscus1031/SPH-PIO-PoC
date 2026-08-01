from pathlib import Path
import yaml

def test_stage01f2_smoke_is_excluded_from_formal_matrix()->None:
    cfg=yaml.safe_load((Path(__file__).resolve().parents[1]/"06_experiments/stage_01f3_mms_convergence/configs/preregistered_stage01f3.yml").read_text())
    assert cfg["scope"]["stage01f2_smoke_reused"] is False
    assert "A1" not in str(cfg) and "B1" not in str(cfg)
