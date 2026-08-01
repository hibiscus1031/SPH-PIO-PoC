from pathlib import Path


def test_no_stage01f2_training_or_label_artifacts() -> None:
    root = Path(__file__).resolve().parents[1]
    stage = root / "06_experiments/stage_01f2_mms_implementation"
    prohibited = ("mlp", "transformer", "attention", "training", "learning_label")
    assert not any(any(token in path.name.lower() for token in prohibited) for path in stage.rglob("*"))
