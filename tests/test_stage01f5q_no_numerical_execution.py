from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01f5q_space_horizon_amendment"


def test_stage01f5q_contains_metadata_only_and_zero_runs():
    config = yaml.safe_load((STAGE / "configs/formal_space_horizon_amendment.yml").read_text())
    scope = config["scope"]
    assert not config["numerical_execution_authorized"]
    assert scope["numerical_runs_executed"] == 0
    assert not any(value for key, value in scope.items() if key != "numerical_runs_executed")
    assert {path.suffix for path in STAGE.rglob("*") if path.is_file()} <= {
        ".csv",
        ".json",
        ".yml",
    }
    assert not list(STAGE.rglob("*.npz"))
    assert not list(STAGE.rglob("*.py"))
