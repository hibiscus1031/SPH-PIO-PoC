from __future__ import annotations

import gc

import torch

from resource_diagnostics.storage_lifetime_tracker import StorageLifetimeTracker, storage_keys


def test_frozen_control_old_storage_is_not_retained_by_tracker() -> None:
    tracker = StorageLifetimeTracker()
    old_workspace = torch.ones((128, 2), dtype=torch.float64)
    tracker.watch(generation=1, semantic_slot="pressure_pair_result", value=old_workspace)
    current_workspace = torch.zeros_like(old_workspace)
    current = storage_keys((current_workspace,))
    del old_workspace
    gc.collect()
    observed = tracker.observe(
        current_step=3,
        current_storage_keys=current,
        collect=True,
    )
    assert observed["old_survivor_storage_count"] == 0
    assert observed["old_survivor_bytes"] == 0
    assert observed["same_slot_multiple_generation_count"] == 0
