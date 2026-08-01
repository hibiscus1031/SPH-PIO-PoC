from pathlib import Path
import sys
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "01_solver"))
from dynamic_solver.acceleration import DynamicPhysicalParameters  # noqa: E402
from dynamic_solver.sourced_integrator_adapter import explicit_midpoint_sourced_step  # noqa: E402
from dynamic_solver.sourced_acceleration import initialize_mms_state  # noqa: E402
from manufactured_solutions.dynamic_source_adapter import evaluate_mms_source  # noqa: E402


def test_midpoint_source_uses_midpoint_numerical_object() -> None:
    state = initialize_mms_state("MMS_B", 16, support_ratio=4.0)
    result = explicit_midpoint_sourced_step(
        state, dt=5e-4, parameters=DynamicPhysicalParameters(), solution_id="MMS_B"
    )
    expected = evaluate_mms_source(
        "MMS_B", result.midpoint_numerical_positions, 0.00025
    )
    assert result.source_calls[1].position_object_identity == id(
        result.midpoint_numerical_positions
    )
    assert torch.equal(result.midpoint_external_acceleration, expected)
