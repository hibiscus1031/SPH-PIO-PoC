from __future__ import annotations

import torch

from resource_diagnostics.semantic_tensor_ledger import (
    SEMANTIC_CATEGORIES,
    SemanticTensorLedger,
)


def test_registered_tensor_uses_explicit_semantics_and_unregistered_is_unknown() -> None:
    state = torch.zeros((8, 2), dtype=torch.float64)
    unknown = torch.ones((3,), dtype=torch.float64)
    ledger = SemanticTensorLedger()
    ledger.register(
        state,
        category="current_state",
        slot="positions",
        generation=4,
    )
    snapshot = ledger.snapshot(step=4)
    by_id = {row["python_object_id"]: row for row in snapshot["tensors"]}
    assert by_id[id(state)]["semantic_category"] == "current_state"
    assert by_id[id(state)]["semantic_slot"] == "positions"
    assert by_id[id(unknown)]["semantic_category"] == "unknown"
    assert tuple(SEMANTIC_CATEGORIES)[-1] == "unknown"
