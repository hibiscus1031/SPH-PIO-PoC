import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "06_experiments/stage_01f5p_branch_completeness/manifests/stage01f5_execution_run_matrix_v2.csv"


def test_stage01f5p_v2_matrix_is_still_the_frozen_69_row_file():
    assert hashlib.sha256(MATRIX.read_bytes()).hexdigest() == "ebbfa5fd3ffced88d1995fc34000b4e1a25524cb93d23e9d6fd9b9a4c4ab061b"
    assert len(MATRIX.read_text().splitlines()) == 70
