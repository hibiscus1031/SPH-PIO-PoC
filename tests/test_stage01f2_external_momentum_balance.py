from pathlib import Path
import sys
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "01_solver"))
from dynamic_solver.acceleration import DynamicPhysicalParameters  # noqa: E402
from dynamic_solver.sourced_integrator_adapter import explicit_midpoint_sourced_step  # noqa: E402
from dynamic_solver.sourced_acceleration import initialize_mms_state  # noqa: E402
from manufactured_solutions.external_balance import force_balance  # noqa: E402


def test_force_assembly_and_midpoint_momentum_update() -> None:
    state = initialize_mms_state("MMS_B", 16, support_ratio=4.0)
    result = explicit_midpoint_sourced_step(
        state, dt=5e-4, parameters=DynamicPhysicalParameters(), solution_id="MMS_B"
    )
    balance = force_balance(
        state.masses,
        result.midpoint_evaluation.acceleration,
        result.midpoint_external_acceleration,
    )
    assert float(torch.linalg.vector_norm(balance["assembly_defect"])) <= 1e-12
    assert float(torch.linalg.vector_norm(result.momentum_defect)) <= 1e-10
