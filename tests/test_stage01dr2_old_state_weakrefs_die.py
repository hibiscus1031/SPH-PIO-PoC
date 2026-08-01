from __future__ import annotations

import gc

import torch

from resource_diagnostics.storage_lifetime_tracker import (
    StorageLifetimeTracker,
    storage_keys,
)


def test_noncurrent_state_storage_dies_before_two_steps() -> None:
    tracker = StorageLifetimeTracker()
    old = torch.ones((64, 2), dtype=torch.float64)
    tracker.watch(generation=1, semantic_slot="old_positions", value=old)
    replacement = torch.zeros_like(old)
    current = storage_keys((replacement,))
    del old
    gc.collect()
    observation = tracker.observe(
        current_step=3,
        current_storage_keys=current,
        collect=True,
    )
    assert observation["old_survivor_storage_count"] == 0
    assert observation["old_survivor_bytes"] == 0
    assert observation["same_slot_multiple_generation_count"] == 0
