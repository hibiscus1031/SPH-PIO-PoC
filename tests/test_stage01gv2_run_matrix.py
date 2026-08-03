import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "06_experiments/stage_01g_execution_preflight_v2"
SOURCE = ROOT / "06_experiments/stage_01g_validation_design/manifests/stage01g_run_matrix.csv"
EXPECTED_SHEAR = {
    "g_shear_n24",
    "g_shear_n32",
    "g_shear_n48",
    "g_shear_n32_dt_half",
    "g_shear_n48_rep2",
}
EXPECTED_ACOUSTIC = {
    "g_acoustic_e5e3_n24",
    "g_acoustic_e5e3_n32",
    "g_acoustic_e5e3_n48",
    "g_acoustic_e5e3_n32_dt_half",
    "g_acoustic_e5e3_n48_rep2",
    "g_acoustic_e2p5e3_n48",
    "g_acoustic_e1e2_n48",
}


def _csv(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def test_frozen_matrix_has_exactly_the_twelve_unique_unexecuted_runs():
    rows = _csv(SOURCE)
    assert len(rows) == 12
    assert {row["run_id"] for row in rows if row["benchmark"] == "shear"} == EXPECTED_SHEAR
    assert {row["run_id"] for row in rows if row["benchmark"] == "acoustic"} == EXPECTED_ACOUSTIC
    assert len({row["run_id"] for row in rows}) == 12
    assert len({row["future_output_directory"] for row in rows}) == 12
    assert {row["stage01g_status"] for row in rows} == {"PREREGISTERED_NOT_EXECUTED"}
    for row in rows:
        output = ROOT / row["future_output_directory"]
        assert not output.exists() or not any(output.iterdir())


def test_machine_readable_matrix_audit_matches_frozen_source():
    audit_rows = _csv(V2 / "manifests/stage01gv2_run_matrix_audit.csv")
    result = json.loads((V2 / "results/stage01gv2_run_matrix_audit.json").read_text())
    assert len(audit_rows) == result["total_runs"] == 12
    assert result["source_sha256"] == hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    assert result["shear_runs"] == 5 and result["acoustic_runs"] == 7
    assert result["unique_run_ids"] == result["unique_output_directories"] == 12
    assert result["preregistered_not_executed"] == 12
    assert result["nonempty_output_directories"] == 0
    assert all(row["status"] == "PASS" and row["artifact_count"] == "0" for row in audit_rows)
