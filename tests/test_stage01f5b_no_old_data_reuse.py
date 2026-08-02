import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_no_run_output_or_analyzer_input_uses_stage01f3_data():
    matrix = ROOT / "06_experiments/stage_01f5p_branch_completeness/manifests/stage01f5_execution_run_matrix_v2.csv"
    with matrix.open() as stream:
        rows = list(csv.DictReader(stream))
    assert all("stage_01f3" not in row["output_dir"] for row in rows)
    analyzer = (ROOT / "06_experiments/stage_01f5b_requalification_execution/analyze_stage01f5b.py").read_text()
    assert "stage_01f3b" not in analyzer
    assert "stage_01f3c" not in analyzer

