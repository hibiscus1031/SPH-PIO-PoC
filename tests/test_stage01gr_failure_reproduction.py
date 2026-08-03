import dataclasses
import inspect
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "01_solver"))

from dynamic_solver.periodic_rollout import DynamicStepResult
from structure_preserving.neighborhood import periodic_cartesian_layout


def test_canonical_type_error_contract_is_reproducible_without_solver_call():
    signature = inspect.signature(periodic_cartesian_layout)
    assert signature.parameters["jitter_fraction"].default is inspect.Parameter.empty
    assert signature.parameters["seed"].default is inspect.Parameter.empty
    with pytest.raises(TypeError, match="jitter_fraction"):
        periodic_cartesian_layout(24)
    failure = (ROOT / "06_experiments/stage_01g_validation_execution/runs/g_shear_n24/failure.txt").read_text()
    assert "missing 2 required keyword-only arguments" in failure


def test_retry1_key_error_contract_is_reproducible_without_solver_call():
    reference = {"position": [], "velocity": [], "density": [], "pressure": []}
    with pytest.raises(KeyError, match="positions"):
        _ = reference["positions"]
    failure = (ROOT / "06_experiments/stage_01g_validation_execution/runs/g_shear_n24/failure.infra_retry1.txt").read_text()
    assert "KeyError: 'positions'" in failure


def test_retry2_attribute_error_contract_is_reproducible_without_time_integration():
    fields = {field.name for field in dataclasses.fields(DynamicStepResult)}
    assert fields == {"state", "start_evaluation", "midpoint_evaluation", "end_evaluation"}
    assert "midpoint_state" not in fields
    failure = (ROOT / "06_experiments/stage_01g_validation_execution/runs/g_shear_n24/failure.infra_retry2.txt").read_text()
    assert "has no attribute 'midpoint_state'" in failure


def test_failure_classifications_remain_infrastructure_not_benchmark():
    evaluation = json.loads(
        (ROOT / "06_experiments/stage_01g_validation_execution/results/stage01g_execution_evaluation.json").read_text()
    )
    assert evaluation["executed_run_count"] == 0
    assert [item["failure_type"] for item in evaluation["preserved_infrastructure_failures"]] == [
        "TypeError", "KeyError", "AttributeError"
    ]
