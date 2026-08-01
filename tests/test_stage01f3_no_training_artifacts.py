from pathlib import Path

def test_no_training_or_label_artifact_names()->None:
    stage=Path(__file__).resolve().parents[1]/"06_experiments/stage_01f3_mms_convergence"
    prohibited=("mlp","transformer","attention","training","learning_label")
    assert not any(any(token in path.name.lower() for token in prohibited) for path in stage.rglob("*"))
