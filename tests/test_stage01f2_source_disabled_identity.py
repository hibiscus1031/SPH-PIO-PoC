from pathlib import Path
import sys
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "01_solver"))
from dynamic_solver.acceleration import DynamicPhysicalParameters  # noqa: E402
from dynamic_solver.periodic_rollout import explicit_midpoint_dynamic_step, prepare_dynamic_state  # noqa: E402
from dynamic_solver.sourced_integrator_adapter import explicit_midpoint_sourced_step  # noqa: E402
from dynamic_solver.taylor_green import initialize_taylor_green_state  # noqa: E402


def test_source_disabled_is_bitwise_identical() -> None:
    state = initialize_taylor_green_state(16, support_ratio=4.0)
    parameters = DynamicPhysicalParameters()
    state, evaluation = prepare_dynamic_state(state, parameters)
    original = explicit_midpoint_dynamic_step(
        state, dt=5e-4, parameters=parameters, start_evaluation=evaluation
    )
    disabled = explicit_midpoint_sourced_step(
        state, dt=5e-4, parameters=parameters, solution_id=None,
        start_evaluation=evaluation,
    )
    for name in ("positions", "velocities", "densities", "pressures"):
        assert torch.equal(getattr(original.state, name), getattr(disabled.state, name))
    for stage in ("start_evaluation", "midpoint_evaluation", "end_evaluation"):
        left, right = getattr(original, stage), getattr(disabled, stage)
        assert torch.equal(left.neighborhood.row, right.neighborhood.row)
        assert torch.equal(left.neighborhood.col, right.neighborhood.col)
        assert torch.equal(left.total_force, right.total_force)
