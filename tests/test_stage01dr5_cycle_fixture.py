from __future__ import annotations

import gc
import weakref

import torch

from resource_diagnostics.gc_cycle_tracker import GCCycleTracker


class _CycleOwner:
    def __init__(self, tensor: torch.Tensor) -> None:
        self.tensor = tensor
        self.cycle = self


def test_cycle_fixture_survives_before_gc_and_dies_after_collect() -> None:
    was_enabled = gc.isenabled()
    gc.disable()
    try:
        tracker = GCCycleTracker()
        tensor = torch.ones(4, dtype=torch.float64)
        owner = _CycleOwner(tensor)
        reference = weakref.ref(tensor)
        tracker.register_current(step=0, named_values={"current": tensor})
        tracker.watch_replacement(
            generation=0,
            replacement_step=1,
            semantic_slot="fixture.tensor",
            value=tensor,
        )
        current = torch.zeros_like(tensor)
        tracker.register_current(step=1, named_values={"current": current})
        del tensor, owner
        assert tracker.observe(step=2)["retired_old_survivor_count"] == 1
        gc.collect()
        assert reference() is None
    finally:
        if was_enabled:
            gc.enable()
