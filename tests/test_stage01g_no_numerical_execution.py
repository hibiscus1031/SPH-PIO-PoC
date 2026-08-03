import csv
import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01g_validation_design"


def test_stage01g_contains_design_and_static_audit_artifacts_only():
    config = yaml.safe_load((STAGE / "configs/preregistered_stage01g.yml").read_text())
    audit = config["execution_audit"]
    assert config["stage"]["numerical_execution_authorized"] is False
    assert audit["numerical_trajectory_count"] == 0
    assert audit["sph_runs"] == audit["rk2_runs"] == audit["dop853_runs"] == 0
    assert audit["benchmark_runs"] == audit["training_runs"] == audit["label_generation_runs"] == 0
    assert audit["future_run_ids_executed"] == []

    result = json.loads((STAGE / "results/stage01g_design_evaluation.json").read_text())
    assert result["numerical_execution_count"] == 0
    assert result["executed_future_run_ids"] == []
    assert result["benchmark_results_present"] is False

    with (STAGE / "manifests/stage01g_run_matrix.csv").open(newline="") as stream:
        assert {row["stage01g_status"] for row in csv.DictReader(stream)} == {"PREREGISTERED_NOT_EXECUTED"}
    assert {path.suffix for path in STAGE.rglob("*") if path.is_file()} <= {".csv", ".json", ".yml"}
    assert not list(STAGE.rglob("*.npz"))
    assert not list(STAGE.rglob("*.pt"))
    assert not list(STAGE.rglob("*.log"))
