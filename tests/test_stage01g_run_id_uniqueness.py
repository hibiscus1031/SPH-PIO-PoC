import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "06_experiments/stage_01g_validation_design/manifests/stage01g_run_matrix.csv"
EXPECTED = {
    "g_shear_n24", "g_shear_n32", "g_shear_n48", "g_shear_n32_dt_half",
    "g_shear_n48_rep2", "g_acoustic_e5e3_n24", "g_acoustic_e5e3_n32",
    "g_acoustic_e5e3_n48", "g_acoustic_e5e3_n32_dt_half",
    "g_acoustic_e5e3_n48_rep2", "g_acoustic_e2p5e3_n48",
    "g_acoustic_e1e2_n48",
}


def test_all_preregistered_run_ids_and_output_directories_are_unique():
    with MATRIX.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    ids = [row["run_id"] for row in rows]
    directories = [row["future_output_directory"] for row in rows]
    assert set(ids) == EXPECTED
    assert len(ids) == len(set(ids)) == 12
    assert len(directories) == len(set(directories)) == 12
    assert all(row["stage01g_status"] == "PREREGISTERED_NOT_EXECUTED" for row in rows)
