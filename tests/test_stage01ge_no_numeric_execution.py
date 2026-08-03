import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01ge_evaluator_qualification"


def test_stage01ge_has_zero_numeric_reference_and_training_execution():
    audit = json.loads((STAGE / "results/stage01ge_execution_audit.json").read_text())
    count_fields = [field for field in audit if field.endswith("_count")]
    assert count_fields and all(audit[field] == 0 for field in count_fields)
    assert audit["v2_status_generated"] is False
    assert audit["v3_started"] is False
    assert audit["stage02_started"] is False
    assert not list(STAGE.rglob("*.npz"))
    assert not list(STAGE.rglob("*.pt"))
    assert not list(STAGE.rglob("*.log"))
