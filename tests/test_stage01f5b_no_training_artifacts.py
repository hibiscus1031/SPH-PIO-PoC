from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01f5b_requalification_execution"


def test_stage_contains_no_models_training_or_label_artifacts():
    forbidden_suffixes = {".pt", ".pth", ".ckpt", ".onnx"}
    assert not [path for path in STAGE.rglob("*") if path.is_file() and path.suffix in forbidden_suffixes]
    assert not (STAGE / "training").exists()
    assert not (STAGE / "labels").exists()
