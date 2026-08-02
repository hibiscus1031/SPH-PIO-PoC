import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVALUATOR = ROOT / "06_experiments/stage_01f3c_ct2_adjudication/evaluate_stage01f3c.py"
SPEC = importlib.util.spec_from_file_location("stage01f3c_evaluator", EVALUATOR)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_status_classifier_never_returns_stage01f3b_status():
    statuses = {
        MODULE.classify_status(False, True, True, True),
        MODULE.classify_status(True, False, False, False),
        MODULE.classify_status(True, True, False, False),
        MODULE.classify_status(True, True, True, True),
        MODULE.classify_status(True, True, True, False),
    }
    assert statuses == {
        "CT2_EVIDENCE_INCOMPLETE",
        "CT2_TRUE_TEMPORAL_DEGRADATION_CONFIRMED",
        "CT2_MIXED_OR_UNRESOLVED",
        "CT2_SPATIAL_TEMPORAL_CANCELLATION_CONFIRMED",
    }
    historical = json.loads(
        (ROOT / "06_experiments/stage_01f3b_mms_convergence/results/stage01f3b_evaluation.json").read_text()
    )
    assert historical["status"] == "MMS_CONVERGENCE_VERIFICATION_FAIL"
