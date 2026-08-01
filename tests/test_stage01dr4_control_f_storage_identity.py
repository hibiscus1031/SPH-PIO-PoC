from __future__ import annotations

from dynamic_solver.taylor_green import initialize_taylor_green_state
from resource_diagnostics.frozen_topology_control import (
    freeze_initial_topology,
    frozen_periodic_neighborhood,
)
from resource_diagnostics.weakref_semantics import WeakrefSemanticGate
from resource_diagnostics.weakref_tracker import tensor_storage_key


def test_frozen_edge_storage_is_current_not_retired() -> None:
    state = initialize_taylor_green_state(8, support_ratio=3.0)
    topology = freeze_initial_topology(state)
    neighborhood = frozen_periodic_neighborhood(state, topology)
    gate = WeakrefSemanticGate()
    gate.register_current(step=0, named_values={"neighborhood": neighborhood})
    gate.watch(generation=0, semantic_slot="start_stage_neighborhood", value=neighborhood)
    gate.register_current(step=2, named_values={"neighborhood": neighborhood})
    fixed = {tensor_storage_key(topology.row), tensor_storage_key(topology.col)}
    rows = gate.audit_rows(
        current_step=2,
        include_referrers=False,
        fixed_edge_storage_keys=fixed,
    )
    fixed_rows = [row for row in rows if row["belongs_to_fixed_initial_edge_index"]]
    assert len(fixed_rows) == 2
    assert all(row["is_current_working_set"] for row in fixed_rows)
    assert all(not row["is_retired_reference"] for row in fixed_rows)
