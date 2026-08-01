from __future__ import annotations

import gc
import weakref

import torch

from resource_diagnostics.instrumentation_isolation import external_gc_type_snapshot


def test_external_type_snapshot_does_not_retain_tensor() -> None:
    tensor = torch.ones(3, dtype=torch.float64)
    reference = weakref.ref(tensor)
    snapshot = external_gc_type_snapshot()
    assert snapshot["tracked_tensor_count"] >= 1
    del tensor
    gc.collect()
    assert reference() is None
