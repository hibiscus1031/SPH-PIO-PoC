from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "06_experiments/stage_01g_validation_design/configs/preregistered_stage01g.yml"


def test_independent_references_do_not_reuse_mms_or_project_solver_path():
    config = yaml.safe_load(CONFIG.read_text())
    independent = config["independence"]
    assert independent["manufactured_force_used"] is False
    assert independent["f_MMS_used"] is False
    assert independent["stage01f_source_adapter_called"] is False
    assert independent["stage01f_trajectories_used_as_validation_results"] is False
    assert independent["stage01f_mms_used_as_physical_validation"] is False
    assert independent["validation_metrics_enter_solver_rhs"] is False
    assert independent["reference_corrected_by_sph_residual"] is False
    assert independent["reference_uses_project_rk2"] is False
    assert independent["reference_paths"] == []
    assert config["common"]["external_source"] is False
    assert config["common"]["source_call_count_required"] == 0
