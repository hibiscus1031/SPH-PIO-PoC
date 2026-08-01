"""Sparse, non-retaining inventory of live PyTorch tensors."""

from __future__ import annotations

import gc
import warnings
from typing import Any

import torch


def collect_tensor_inventory() -> dict[str, int]:
    """Return tensor counts and byte estimates without returning tensors.

    Logical bytes sum every tensor view. ``unique_storage_bytes`` deduplicates
    tensors sharing the same storage, which is useful when autograd views are
    present. The temporary object list is explicitly released before return.
    """

    objects = gc.get_objects()
    tensor_count = 0
    logical_bytes = 0
    requires_grad_count = 0
    grad_fn_count = 0
    error_count = 0
    storages: dict[tuple[str, int, int], int] = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for obj in objects:
            try:
                is_tensor = isinstance(obj, torch.Tensor)
            except Exception:
                error_count += 1
                continue
            if not is_tensor:
                continue
            try:
                tensor_count += 1
                logical_bytes += int(obj.numel()) * int(obj.element_size())
                requires_grad_count += int(bool(obj.requires_grad))
                grad_fn_count += int(obj.grad_fn is not None)
                storage = obj.untyped_storage()
                storage_bytes = int(storage.nbytes())
                key = (str(obj.device), int(storage.data_ptr()), storage_bytes)
                storages[key] = storage_bytes
                del storage
            except Exception:
                error_count += 1
    if objects:
        del obj
    gc_count = len(objects)
    del objects
    return {
        "gc_tracked_object_count": int(gc_count),
        "live_tensor_count": int(tensor_count),
        "live_tensor_logical_bytes": int(logical_bytes),
        "live_tensor_unique_storage_bytes": int(sum(storages.values())),
        "live_tensor_requires_grad_count": int(requires_grad_count),
        "live_tensor_grad_fn_count": int(grad_fn_count),
        "tensor_inventory_error_count": int(error_count),
    }
