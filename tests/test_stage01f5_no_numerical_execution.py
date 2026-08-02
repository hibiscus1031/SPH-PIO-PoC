from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01f5_requalification_design"


def test_stage01f5_contains_design_metadata_only():
    config = yaml.safe_load((STAGE / "configs/preregistered_stage01f5.yml").read_text())
    scope = config["scope"]
    assert not config["numerical_execution_authorized"]
    assert scope["numerical_trajectory_count"] == 0
    assert not scope["dynamic_solver_imported_or_called"]
    assert not scope["sph_run_started"]
    assert not scope["rk2_run_started"]
    assert not scope["dop853_run_started"]
    assert not scope["reference_npz_generated"]
    assert not scope["temporal_or_spatial_convergence_executed"]
    assert {path.suffix for path in STAGE.rglob("*") if path.is_file()} <= {
        ".csv",
        ".json",
        ".yml",
    }
    assert not list(STAGE.rglob("*.npz"))
    assert not list(STAGE.rglob("*.py"))
