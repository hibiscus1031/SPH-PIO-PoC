from __future__ import annotations

import gc

import torch

from resource_diagnostics.semantic_tensor_ledger import SemanticTensorLedger


def test_static_semantic_state_has_constant_unique_storage_bytes() -> None:
    positions = torch.zeros((32, 2), dtype=torch.float64)
    velocities = torch.ones((32, 2), dtype=torch.float64)
    ledger = SemanticTensorLedger()
    ledger.register_many(
        {"positions": positions, "velocities": velocities},
        category="current_state",
        generation=0,
    )
    totals = []
    for step in range(5):
        gc.collect()
        snapshot = ledger.snapshot(step=step)
        totals.append(snapshot["summary"]["semantic_current_state_bytes"])
        del snapshot
    assert totals == [positions.nbytes + velocities.nbytes] * 5
