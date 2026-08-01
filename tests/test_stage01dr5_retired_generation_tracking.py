from __future__ import annotations

import torch

from resource_diagnostics.gc_cycle_tracker import GCCycleTracker


def test_retired_same_slot_generations_are_counted() -> None:
    tracker = GCCycleTracker()
    history: list[torch.Tensor] = []
    current = torch.ones(2, dtype=torch.float64)
    tracker.register_current(step=0, named_values={"current": current})
    observed = {}
    for step in range(1, 6):
        tracker.watch_replacement(
            generation=step - 1,
            replacement_step=step,
            semantic_slot="history.current",
            value=current,
        )
        history.append(current)
        current = torch.full((2,), float(step), dtype=torch.float64)
        tracker.register_current(step=step, named_values={"current": current})
        observed = tracker.observe(step=step)
    assert observed["retired_old_survivor_count"] >= 3
    assert observed["same_slot_multigeneration_count"] == 1
    assert observed["maximum_retired_generations_in_one_slot"] >= 3
