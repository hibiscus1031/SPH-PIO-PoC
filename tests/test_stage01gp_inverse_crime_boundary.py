from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "06_experiments/stage_01g_validation_design/configs/preregistered_stage01g.yml"
REPORT = ROOT / "07_reports/stage_01g_final_report.md"
METRICS = ROOT / "07_reports/stage_01g_validation_metrics.md"


def test_frozen_independence_flags_close_mms_old_data_and_feedback_paths():
    config = yaml.safe_load(CONFIG.read_text())
    boundary = config["independence"]
    false_flags = [
        "manufactured_force_used", "f_MMS_used", "stage01f_source_adapter_called",
        "stage01f_trajectories_used_as_validation_results",
        "stage01f_mms_used_as_physical_validation",
        "validation_metrics_enter_solver_rhs", "reference_corrected_by_sph_residual",
        "reference_uses_project_rk2",
    ]
    assert all(boundary[key] is False for key in false_flags)
    assert boundary["reference_paths"] == []
    assert config["shear_wave"]["exact_reference"]["kind"] == "closed_form_continuum_and_unwrapped_trajectory"
    assert config["acoustic_wave"]["linear_reference"]["kind"] == "independent_linear_theory"
    report = REPORT.read_text()
    assert "Stage 01F3B/F3C/F5B trajectories/errors" in report
    assert "Validation metrics are evaluator-only quantities" in METRICS.read_text()
