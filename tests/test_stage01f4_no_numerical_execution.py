from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01f4_protocol_adjudication"


def test_stage_is_protocol_only_and_contains_no_run_artifacts():
    config = yaml.safe_load((STAGE / "configs/preregistered_stage01f4.yml").read_text())
    scope = config["scope"]
    assert not config["numerical_runs_authorized"]
    assert scope["numerical_trajectory_count"] == 0
    assert not scope["sph_run_started"]
    assert not scope["dop853_run_started"]
    assert not scope["convergence_matrix_started"]
    assert not scope["training_started"]
    assert not scope["labels_generated"]
    assert {path.suffix for path in STAGE.rglob("*") if path.is_file()} <= {
        ".csv",
        ".json",
        ".yml",
    }
    forbidden_names = ("trajectory", "checkpoint", "train", "label", "reference.npz")
    assert not [
        path
        for path in STAGE.rglob("*")
        if path.is_file() and any(token in path.name.lower() for token in forbidden_names)
    ]
