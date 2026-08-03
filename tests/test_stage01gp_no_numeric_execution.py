import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "06_experiments/stage_01gp_preexecution_audit"


def test_preexecution_audit_contains_no_numeric_execution_artifacts():
    config = yaml.safe_load((AUDIT / "configs/stage01gp_audit_protocol.yml").read_text())
    execution = config["execution_audit"]
    assert config["stage"]["numerical_execution_authorized"] is False
    assert config["stage"]["benchmark_execution_authorized"] is False
    numeric_counts = [value for key, value in execution.items() if key.endswith("_count")]
    assert numeric_counts and all(value == 0 for value in numeric_counts)
    assert execution["v2_status"] is None
    assert execution["v3_started"] is False
    assert execution["stage02_started"] is False

    evaluation = json.loads((AUDIT / "results/stage01gp_evaluation.json").read_text())
    for field in ("numerical_run_count", "benchmark_execution_count", "trajectory_count", "checkpoint_count", "reference_data_count"):
        assert evaluation[field] == 0
    assert evaluation["v2_status"] is None

    files = [path for path in AUDIT.rglob("*") if path.is_file()]
    assert {path.suffix for path in files} <= {".yml", ".csv", ".json"}
    assert not list(AUDIT.rglob("*.npz"))
    assert not list(AUDIT.rglob("*.pt"))
    assert not list(AUDIT.rglob("*.log"))
