from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[1]; STAGE=ROOT/"06_experiments/stage_01f_mms_design"


def test_no_training_or_v3_artifacts()->None:
    cfg=yaml.safe_load((STAGE/"configs/preregistered_mms_specification.yml").read_text()); scope=cfg["scope"]
    assert not scope["training_started"] and not scope["learning_labels_generated"] and not scope["v3_started"] and not scope["stage02_started"] and not scope["dynamic_rollout_run"]
    assert not [p for p in STAGE.rglob("*") if p.suffix.lower() in {".pt",".pth",".ckpt",".onnx"}]
