import inspect
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "06_experiments/stage_01ge_evaluator_qualification"
sys.path.insert(0, str(STAGE))

from evaluator.gate_rules import evaluate_acoustic_gates, evaluate_shear_gates, metric_binding
from evaluator.provenance import verify_frozen_inputs


def test_threshold_sources_match_frozen_stage01g_and_have_no_override_argument():
    checks = verify_frozen_inputs(
        ROOT / "06_experiments/stage_01g_validation_design/configs/preregistered_stage01g.yml",
        ROOT / "07_reports/stage_01g_validation_metrics.md",
        ROOT / "06_experiments/stage_01g_validation_design/manifests/stage01g_run_matrix.csv",
    )
    assert all(checks.values())
    assert list(inspect.signature(evaluate_shear_gates).parameters) == ["run_results"]
    assert list(inspect.signature(evaluate_acoustic_gates).parameters) == ["run_results"]
    binding = metric_binding()
    assert binding["normalization"]["epsilon_denominator"] is False
    assert binding["normalization"]["adaptive_threshold"] is False
