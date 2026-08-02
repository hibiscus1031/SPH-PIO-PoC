import csv
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01f5p_branch_completeness"


def test_two_n64_smokes_have_frozen_ids_and_parameters():
    config = yaml.safe_load((STAGE / "configs/preregistered_stage01f5p.yml").read_text())
    with (STAGE / "manifests/stage01f5_execution_run_matrix_v2.csv").open() as stream:
        rows = {row["run_id"]: row for row in csv.DictReader(stream)}
    ids = config["n64_smoke"]["run_ids"]
    assert ids == ["f5_n64_smoke_a", "f5_n64_smoke_b"]
    assert config["n64_smoke"]["steps"] == 20
    assert config["n64_smoke"]["t_final_rule"] == "20_times_committed_dt_space"
    assert not config["n64_smoke"]["part_of_formal_spatial_error_sequence"]
    for run_id in ids:
        row = rows[run_id]
        assert (row["resolution"], row["particle_count"], row["support_ratio"]) == (
            "64",
            "4096",
            "6.041381265149109",
        )
        assert row["time_control"] == "dt=SPACE_STEP_DECISION;steps=20"
        assert row["conditional"] == "true"
