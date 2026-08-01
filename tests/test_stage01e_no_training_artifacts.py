from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[1]; STAGE=ROOT/"06_experiments/stage_01e_error_decomposition"


def test_scope_and_no_training_artifacts() -> None:
    cfg=yaml.safe_load((STAGE/"configs/preregistered_stage01e.yml").read_text()); scope=cfg["scope"]
    assert not scope["v3_started"] and not scope["stage02_started"] and not scope["training_started"] and not scope["learning_labels_generated"]
    forbidden={".pt",".pth",".ckpt",".onnx"}
    assert not [path for path in STAGE.rglob("*") if path.suffix.lower() in forbidden]
    source="\n".join(path.read_text(errors="ignore") for path in STAGE.rglob("*.py"))
    assert "optimizer.step(" not in source and ".backward(" not in source
