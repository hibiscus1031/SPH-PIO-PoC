from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "01_solver"))
from dynamic_solver.acceleration import DynamicPhysicalParameters  # noqa: E402
from dynamic_solver.sourced_integrator_adapter import explicit_midpoint_sourced_step  # noqa: E402
from dynamic_solver.sourced_acceleration import initialize_mms_state  # noqa: E402


def test_exactly_start_and_midpoint_calls() -> None:
    state = initialize_mms_state("MMS_B", 16, support_ratio=4.0)
    result = explicit_midpoint_sourced_step(
        state, dt=5e-4, parameters=DynamicPhysicalParameters(), solution_id="MMS_B"
    )
    assert [call.stage for call in result.source_calls] == ["start", "midpoint"]
    assert [call.physical_time for call in result.source_calls] == [0.0, 0.00025]
    assert len(result.source_calls) == 2
