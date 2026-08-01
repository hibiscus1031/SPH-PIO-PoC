"""Low-intrusion probes and component definitions for R5 isolation runs."""

from __future__ import annotations

import gc
from typing import Any
import warnings

import torch

from resource_diagnostics.rss_sampler import current_process_memory_bytes
from resource_diagnostics.weakref_tracker import tensor_storage_key


ISOLATION_COMPONENTS = {
    "I0": frozenset(),
    "I1": frozenset({"weakref_tracker"}),
    "I2": frozenset({"semantic_ledger"}),
    "I3": frozenset({"observer_callback"}),
    "I4": frozenset({"weakref_tracker", "semantic_ledger", "observer_callback"}),
}


def low_intrusion_rss_bytes() -> int:
    return int(current_process_memory_bytes()[0])


def external_gc_type_snapshot() -> dict[str, Any]:
    """Count tracked solver types without retaining any project tensor."""

    objects = gc.get_objects()
    tensor_count = 0
    tensor_storage_bytes = 0
    tensor_storages: set[tuple[str, int, int]] = set()
    type_counts = {
        "PeriodicNeighborhood": 0,
        "ForceEvaluation": 0,
        "DynamicSPHState": 0,
        "function": 0,
        "cell": 0,
    }
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for value in objects:
                name = type(value).__name__
                if name in type_counts:
                    type_counts[name] += 1
                try:
                    is_tensor = isinstance(value, torch.Tensor)
                except Exception:
                    is_tensor = False
                if is_tensor:
                    tensor_count += 1
                    try:
                        tensor_storages.add(tensor_storage_key(value))
                    except Exception:
                        pass
        tensor_storage_bytes = int(sum(key[2] for key in tensor_storages))
        if objects:
            del value
    finally:
        del objects
        tensor_storages.clear()
    return {
        "tracked_tensor_count": tensor_count,
        "tracked_tensor_storage_bytes": tensor_storage_bytes,
        **{f"tracked_type_{name}": count for name, count in type_counts.items()},
    }
