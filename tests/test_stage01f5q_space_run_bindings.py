import csv
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01f5q_space_horizon_amendment"


def test_exactly_31_unique_space_runs_are_bound_to_0p02():
    with (STAGE / "manifests/stage01f5q_space_parameter_binding.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    with (
        ROOT
        / "06_experiments/stage_01f5p_branch_completeness/manifests/stage01f5_execution_run_matrix_v2.csv"
    ).open() as stream:
        matrix = list(csv.DictReader(stream))
    assert len(rows) == len({row["run_id"] for row in rows}) == 31
    assert all(row["formal_space_t_final"] == "0.02" for row in rows)
    assert all(row["binding_status"] == "FROZEN" for row in rows)
    assert Counter(row["execution_group"] for row in rows) == {
        "space_dt_isolation": 4,
        "formal_space": 8,
        "space_determinism_repeat": 2,
        "space_mms_b_reference": 12,
        "conditional_formal_space": 2,
        "conditional_space_mms_b_reference": 3,
    }
    forbidden = {
        "f5_n64_smoke_a",
        "f5_n64_smoke_b",
        "f5_main_a_dt1e3",
        "f5_hold_a_dt1e3",
        "f5_ref_main_a_baseline",
        "f5_ref_hold_a_baseline",
    }
    assert forbidden.isdisjoint({row["run_id"] for row in rows})
    formal_categories = {
        "space_dt_isolation",
        "formal_space",
        "space_mms_b_reference",
        "conditional_n64",
        "conditional_n64_reference",
    }
    expected_ids = {
        row["run_id"]
        for row in matrix
        if row["category"] in formal_categories
        or row["run_id"] in {"f5_space_a_n32_rep2", "f5_space_b_n32_rep2"}
    }
    assert {row["run_id"] for row in rows} == expected_ids
