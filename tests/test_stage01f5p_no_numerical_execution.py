from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01f5p_branch_completeness"


def test_stage01f5p_is_metadata_only_with_zero_runs():
    config = yaml.safe_load((STAGE / "configs/preregistered_stage01f5p.yml").read_text())
    scope = config["scope"]
    assert not config["numerical_execution_authorized"]
    assert scope["numerical_runs_executed"] == 0
    assert not any(
        scope[key]
        for key in (
            "sph_started",
            "rk2_started",
            "dop853_started",
            "smoke_started",
            "reference_started",
            "convergence_started",
            "reference_npz_generated",
            "stage01f5b_started",
            "training_started",
            "labels_generated",
        )
    )
    assert {path.suffix for path in STAGE.rglob("*") if path.is_file()} <= {
        ".csv",
        ".json",
        ".yml",
    }
    assert not list(STAGE.rglob("*.npz"))
    assert not list(STAGE.rglob("*.py"))
