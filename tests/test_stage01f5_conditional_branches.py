from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "06_experiments/stage_01f5_requalification_design/configs/preregistered_stage01f5.yml"


def test_space_step_decision_is_binary_and_precedes_formal_runs():
    isolation = yaml.safe_load(CONFIG.read_text())["space_time_step_isolation"]
    decision = isolation["decision"]
    assert isolation["dt_candidates"] == [0.0000625, 0.00003125]
    assert decision["if_any_field_relative_change_greater_than"] == 0.10
    assert decision["then_dt_space"] == 0.00003125
    assert decision["else_dt_space"] == 0.0000625
    assert decision["must_be_committed_before_formal_n16_n24_n48_runs"]
    assert not decision["may_change_after_viewing_spatial_trend"]


def test_n64_trigger_and_preflight_are_unambiguous():
    branch = yaml.safe_load(CONFIG.read_text())["conditional_n64"]
    assert len(branch["trigger_if_any"]) == 4
    assert branch["run_ids"] == ["f5_space_a_n64", "f5_space_b_n64"]
    assert branch["preflight_all_required"] == {
        "smoke_steps": 20,
        "peak_rss_bytes_less_than": 2000000000,
        "estimated_single_run_wall_seconds_less_than": 7200,
        "cutoff_margin_greater_than": 1e-12,
        "structural_topology_defects": 0,
    }
    assert not branch["adverse_results_may_be_deleted"]
