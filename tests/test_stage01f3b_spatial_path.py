from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[1];CFG=yaml.safe_load((ROOT/"06_experiments/stage_01f3b_mms_convergence/configs/preregistered_stage01f3b.yml").read_text())

def test_increasing_neighbor_path_is_exactly_preregistered()->None:
    path=CFG["space"]["increasing_neighbor_path"]
    assert path=={16:4.06155281280883,24:4.5,32:5.049509756796392,48:5.5,64:6.041381265149109}
    assert CFG["space"]["formal_resolutions"]==[16,24,32,48]
    assert CFG["space"]["fixed_ratio"]==4.5
