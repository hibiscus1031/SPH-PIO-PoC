import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01f4_protocol_adjudication"
CONFIG = STAGE / "configs/preregistered_stage01f4.yml"
EVALUATION = STAGE / "results/stage01f4_evaluation.json"


def test_time_and_platform_gates_are_plateau_aware_and_locked():
    config = yaml.safe_load(CONFIG.read_text())
    time = config["time_gates"]
    platform = config["platform_gates"]
    assert time["fields"] == ["position", "velocity"]
    assert time["T2"]["minimum"] == 1.80
    assert time["T3"]["interval"] == [1.70, 2.30]
    assert time["T4"]["minimum_usable_points_per_field_and_norm"] == 4
    assert time["T5"]["finest_to_coarsest_maximum_ratio"] == 0.30
    assert platform["P1"]["maximum"] == 0.01
    assert platform["P2"]["maximum"] == 0.01
    assert platform["P3"]["all_total_exact_errors_finite"]
    assert not platform["P3"]["strict_monotonicity_inside_platform_required"]
    assert platform["old_ct2_percent_relaxation_forbidden"]


def test_space_and_new_heldout_contracts_are_complete():
    config = yaml.safe_load(CONFIG.read_text())
    space = config["space_gates"]
    heldout = config["prospective_heldout"]
    assert space["path_name"] == "increasing-neighbor consistency path"
    assert not space["fixed_stencil_single_h_claim_allowed"]
    assert space["fields"] == ["position", "velocity", "density", "pressure"]
    assert space["strict_levelwise_l2_decrease_each_field"]
    assert space["positive_global_loglog_slope_each_field"]
    assert space["gci"]["qualified_separately_per_field"]
    assert not space["fixed_ratio_family"]["can_qualify_space_gate"]
    sealed = heldout["sealed_configuration"]
    assert (sealed["resolution"], sealed["support_ratio"], sealed["t_final"]) == (
        28,
        4.75,
        0.015,
    )
    assert sealed["repository_precheck_no_prior_matching_configuration"]
    assert not sealed["prior_trajectory_or_reference_data_used_to_set_gates"]
    not_imposed = heldout["requirements_explicitly_not_imposed"]
    assert not_imposed["cross_term_sign_matches_primary"]
    assert not_imposed["platform_approach_direction_matches_primary"]
    assert not_imposed["total_exact_error_strictly_monotone"]


def test_unique_approved_status_only_authorizes_a_design_application():
    config = yaml.safe_load(CONFIG.read_text())
    evaluation = json.loads(EVALUATION.read_text())
    assert evaluation["status"] in config["allowed_statuses"]
    assert evaluation["status"] == "PLATEAU_AWARE_PROTOCOL_APPROVED"
    assert evaluation["new_requalification_design_application_eligible"]
    assert evaluation["numerical_runs_executed"] == 0
    assert not evaluation["historical_stage01f3b_status_changed"]
    assert not evaluation["historical_stage01f3c_status_changed"]
    assert not evaluation["stage01f3d_started"]
    assert not evaluation["stage01g_started"]
    assert not evaluation["v3_started"]
    assert not evaluation["stage02_started"]
    assert not evaluation["v2_qualification_generated"]
    assert not evaluation["v3_qualification_generated"]
    assert not evaluation["stage01g_qualification_generated"]
    assert not evaluation["stage02_qualification_generated"]
