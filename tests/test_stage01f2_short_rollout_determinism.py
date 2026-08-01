from pathlib import Path
import sys
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "01_solver"))
from dynamic_solver.acceleration import DynamicPhysicalParameters  # noqa: E402
from dynamic_solver.sourced_integrator_adapter import explicit_midpoint_sourced_step  # noqa: E402
from dynamic_solver.sourced_acceleration import initialize_mms_state  # noqa: E402


def _run() -> tuple[torch.Tensor, ...]:
    state = initialize_mms_state("MMS_B", 16, support_ratio=4.0)
    parameters = DynamicPhysicalParameters()
    with torch.no_grad():
        for _ in range(3):
            state = explicit_midpoint_sourced_step(
                state, dt=5e-4, parameters=parameters, solution_id="MMS_B"
            ).state
    return state.positions, state.velocities, state.densities, state.pressures


def test_independent_short_runs_are_bitwise_equal() -> None:
    assert all(torch.equal(left, right) for left, right in zip(_run(), _run()))
