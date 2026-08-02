import csv
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01f5p_branch_completeness"
F5 = ROOT / "06_experiments/stage_01f5_requalification_design/configs/preregistered_stage01f5.yml"


def test_three_n64_reference_ids_inherit_reference_levels_but_not_t_final():
    config = yaml.safe_load((STAGE / "configs/preregistered_stage01f5p.yml").read_text())
    original = yaml.safe_load(F5.read_text())
    reference = config["n64_mms_b_reference"]
    assert reference["run_ids"] == [
        "f5_ref_space_b_n64_baseline",
        "f5_ref_space_b_n64_tighter",
        "f5_ref_space_b_n64_third",
    ]
    assert reference["levels"] == original["reference_design"]["levels"]
    assert not reference["formal_space_t_final"]["resolved"]
    assert reference["formal_space_t_final"]["value"] is None
    assert reference["formal_space_t_final"]["inference_from_main_or_heldout_forbidden"]
    assert "t_final" not in original["spatial_matrix"]
    with (STAGE / "manifests/stage01f5_execution_run_matrix_v2.csv").open() as stream:
        rows = {row["run_id"]: row for row in csv.DictReader(stream)}
    assert all(rows[run_id]["method"] == "DOP853" for run_id in reference["run_ids"])
