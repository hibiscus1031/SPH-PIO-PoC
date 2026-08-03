import subprocess
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = "06_experiments/stage_01g_validation_design/configs/preregistered_stage01g.yml"
METRIC_REPORT = ROOT / "07_reports/stage_01g_validation_metrics.md"


def test_metric_contract_and_thresholds_are_explicit_evaluator_only_and_tag_frozen():
    payload = (ROOT / CONFIG_PATH).read_bytes()
    tagged = subprocess.run(
        ["git", "show", f"stage-01g-independent-validation-design-approved:{CONFIG_PATH}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    assert payload == tagged
    config = yaml.safe_load(payload)
    assert config["stage"]["threshold_changes_after_results_authorized"] is False
    assert config["independence"]["validation_metrics_enter_solver_rhs"] is False
    assert len(config["shear_wave"]["metrics"]) == 10
    assert len(config["acoustic_wave"]["metrics"]) == 10
    assert len(config["shear_wave"]["common_times"]) == 6
    assert len(config["acoustic_wave"]["common_times"]) == 5
    assert config["common"]["dt_main"] == 6.25e-5
    assert config["common"]["dt_half_n32"] == 3.125e-5
    report = METRIC_REPORT.read_text()
    assert "no epsilon denominator may be introduced" in report
    assert "Validation metrics are evaluator-only quantities" in report
    assert "no regression fit can replace a failed strict ordering gate" in report
