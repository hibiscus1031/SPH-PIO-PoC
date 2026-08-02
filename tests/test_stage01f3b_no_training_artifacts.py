from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[1];STAGE=ROOT/"06_experiments/stage_01f3b_mms_convergence";CFG=yaml.safe_load((STAGE/"configs/preregistered_stage01f3b.yml").read_text())

def test_scope_forbids_downstream_and_training_artifacts()->None:
    assert all(CFG["scope"][key] is False for key in ("stage01g_started","v3_started","stage02_started","training_started","labels_generated"))
    forbidden={".pt",".pth",".ckpt",".onnx"}
    assert not any(path.suffix in forbidden for path in STAGE.rglob("*"))
