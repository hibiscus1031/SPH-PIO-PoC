import csv
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01f5p_branch_completeness"


def test_extended_matrix_is_62_plus_7_with_unique_ids_and_outputs():
    matrix = STAGE / "manifests/stage01f5_execution_run_matrix_v2.csv"
    with matrix.open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 69
    assert sum(row["conditional"] == "false" for row in rows) == 62
    assert sum(row["conditional"] == "true" for row in rows) == 7
    assert len({row["run_id"] for row in rows}) == 69
    assert len({row["output_dir"] for row in rows}) == 69
    assert hashlib.sha256(matrix.read_bytes()).hexdigest() == "ebbfa5fd3ffced88d1995fc34000b4e1a25524cb93d23e9d6fd9b9a4c4ab061b"
