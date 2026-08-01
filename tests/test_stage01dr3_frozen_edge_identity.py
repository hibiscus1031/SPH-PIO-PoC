from __future__ import annotations

import torch

from dynamic_solver.taylor_green import initialize_taylor_green_state
from resource_diagnostics.frozen_topology_control import (
    freeze_initial_topology,
    frozen_periodic_neighborhood,
)
from resource_diagnostics.support_margin_control import edge_identity_sha256


def test_frozen_edge_identity_survives_position_perturbation() -> None:
    state = initialize_taylor_green_state(8, support_ratio=3.0)
    topology = freeze_initial_topology(state)
    shifted = state.with_updates(
        positions=state.positions + torch.finfo(torch.float64).eps
    )
    neighborhood = frozen_periodic_neighborhood(shifted, topology)
    assert torch.equal(neighborhood.row, topology.row)
    assert torch.equal(neighborhood.col, topology.col)
    assert edge_identity_sha256(neighborhood) == topology.edge_key_sha256
