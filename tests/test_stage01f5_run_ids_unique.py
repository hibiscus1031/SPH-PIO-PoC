import csv
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01f5_requalification_design"


def test_machine_readable_run_matrix_ids_and_outputs_are_unique():
    with (STAGE / "manifests/stage01f5_run_matrix.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    ids = [row["run_id"] for row in rows]
    outputs = [row["output_dir"] for row in rows]
    assert len(rows) == len(set(ids)) == len(set(outputs)) == 64
    assert sum(row["conditional"] == "true" for row in rows) == 2
    expected = {
        "main_reference": 6,
        "main_rk2": 10,
        "heldout_reference": 6,
        "heldout_rk2": 10,
        "space_dt_isolation": 4,
        "formal_space": 8,
        "determinism_repeat": 6,
        "space_mms_b_reference": 12,
        "conditional_n64": 2,
    }
    assert Counter(row["category"] for row in rows) == expected
    audit = json.loads((STAGE / "results/run_matrix_audit.json").read_text())
    assert audit["status"] == "PASS"
    assert audit["unconditional_count"] == 62
