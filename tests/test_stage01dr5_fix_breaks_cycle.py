from __future__ import annotations

import gc
import weakref

import torch


class _StrongCycle:
    def __init__(self, tensor: torch.Tensor) -> None:
        self.tensor = tensor
        self.back_reference: _StrongCycle | None = self


def test_removing_unnecessary_back_reference_breaks_fixture_cycle() -> None:
    tensor = torch.ones(2, dtype=torch.float64)
    owner = _StrongCycle(tensor)
    reference = weakref.ref(tensor)
    owner.back_reference = None
    del tensor, owner
    gc.collect()
    assert reference() is None
