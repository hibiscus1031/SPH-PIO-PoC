import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "06_experiments/stage_01g_validation_design/manifests/stage01g_run_matrix.csv"
AUDITED = ROOT / "06_experiments/stage_01gp_preexecution_audit/results/stage01gp_run_matrix_audit.csv"


def test_normalized_audit_is_an_exact_unexecuted_projection_of_frozen_matrix():
    with ORIGINAL.open(newline="") as stream:
        source = list(csv.DictReader(stream))
    with AUDITED.open(newline="") as stream:
        audit = list(csv.DictReader(stream))
    assert len(source) == len(audit) == 12
    assert sum(row["benchmark"] == "shear" for row in source) == 5
    assert sum(row["benchmark"] == "acoustic" for row in source) == 7
    assert len({row["run_id"] for row in source}) == 12
    assert len({row["future_output_directory"] for row in source}) == 12

    for frozen, checked in zip(source, audit):
        assert checked == {
            "run_id": frozen["run_id"],
            "benchmark": frozen["benchmark"],
            "purpose": frozen["purpose"],
            "N": frozen["N"],
            "H/dx": frozen["H_over_dx"],
            "dt": frozen["dt"],
            "status": frozen["stage01g_status"],
            "executed": "false",
        }
    assert not list((ROOT / "06_experiments/stage_01g_validation_design").rglob("*.npz"))
