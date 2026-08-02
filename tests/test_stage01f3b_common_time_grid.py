from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[1];CFG=yaml.safe_load((ROOT/"06_experiments/stage_01f3b_mms_convergence/configs/preregistered_stage01f3b.yml").read_text())

def test_all_time_matrices_have_exact_common_grids()->None:
    for name in ("semidiscrete_time","continuous_time"):
        block=CFG[name]
        for dt in block["dt"]:
            steps=round(block["t_final"]/dt)
            assert steps%(block["sample_count"]-1)==0
