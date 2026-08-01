from __future__ import annotations

import torch

from dynamic_solver.acceleration import DynamicPhysicalParameters
from dynamic_solver.periodic_rollout import explicit_midpoint_dynamic_step, prepare_dynamic_state
from dynamic_solver.taylor_green import initialize_taylor_green_state
from resource_diagnostics.cutoff_shell_audit import select_mid_shell_support
from resource_diagnostics.support_margin_control import edge_identity_sha256


def test_non_degenerate_support_keeps_zero_flow_topology_constant() -> None:
    support = select_mid_shell_support(32).support_ratio
    state = initialize_taylor_green_state(32, support_ratio=support)
    state = state.with_updates(velocities=torch.zeros_like(state.velocities))
    parameters = DynamicPhysicalParameters(
        reference_density=float(state.densities.mean()),
        sound_speed=20.0,
        physical_viscosity=0.02,
    )
    with torch.no_grad():
        state, evaluation = prepare_dynamic_state(state, parameters)
        identity = edge_identity_sha256(evaluation.neighborhood)
        edge_count = int(evaluation.neighborhood.row.numel())
        for _ in range(5):
            result = explicit_midpoint_dynamic_step(
                state,
                dt=5.0e-4,
                parameters=parameters,
                start_evaluation=evaluation,
            )
            state = result.state
            evaluation = result.end_evaluation
            assert int(evaluation.neighborhood.row.numel()) == edge_count
            assert edge_identity_sha256(evaluation.neighborhood) == identity
