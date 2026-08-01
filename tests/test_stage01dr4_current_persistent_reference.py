from __future__ import annotations

import torch

from resource_diagnostics.weakref_semantics import WeakrefSemanticGate


def test_current_persistent_reference_is_not_retention() -> None:
    gate = WeakrefSemanticGate()
    current = torch.ones(8, dtype=torch.float64)
    gate.register_current(step=0, named_values={"current": current})
    gate.watch(generation=0, semantic_slot="current", value=current)
    for step in range(1, 4):
        current.add_(1.0)
        gate.register_current(step=step, named_values={"current": current})
    result = gate.observe(current_step=2, collect=True)
    assert result["current_persistent_reference_count"] == 1
    assert result["retired_reference_count"] == 0
    assert result["retention_signal"] is False
