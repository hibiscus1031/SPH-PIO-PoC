from pathlib import Path
import sys
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "01_solver"))
from dynamic_solver.acceleration import DynamicPhysicalParameters, evaluate_internal_acceleration  # noqa: E402
from dynamic_solver.sourced_integrator_adapter import explicit_midpoint_sourced_step  # noqa: E402
from dynamic_solver.sourced_acceleration import initialize_mms_state  # noqa: E402


def test_external_source_does_not_modify_internal_pair_result() -> None:
    state = initialize_mms_state("MMS_A", 16, support_ratio=4.0)
    internal = evaluate_internal_acceleration(state, DynamicPhysicalParameters())
    result = explicit_midpoint_sourced_step(
        state, dt=5e-4, parameters=DynamicPhysicalParameters(), solution_id="MMS_A",
        start_evaluation=internal,
    )
    assert result.start_evaluation is internal
    assert torch.equal(result.start_evaluation.total_force, internal.total_force)
    assert not torch.equal(result.start_external_acceleration, internal.acceleration)
