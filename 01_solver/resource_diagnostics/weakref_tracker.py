"""Non-retaining tensor/object references for Stage 01D-R2.

Only weak references and scalar storage descriptors survive a call.  The
helpers deliberately avoid storing tensor representations or filesystem data.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from typing import Any, Iterable
import weakref

import torch


StorageKey = tuple[str, int, int]


def tensor_storage_key(value: torch.Tensor) -> StorageKey:
    """Return the preregistered ``(device, data_ptr, nbytes)`` key."""

    if not torch.is_tensor(value):
        raise TypeError("value must be a torch.Tensor")
    storage = value.untyped_storage()
    try:
        return (str(value.device), int(storage.data_ptr()), int(storage.nbytes()))
    finally:
        del storage


def walk_tensors(value: Any) -> tuple[torch.Tensor, ...]:
    """Collect tensors from a bounded project container without global state."""

    found: list[torch.Tensor] = []
    visited: set[int] = set()

    def visit(current: Any) -> None:
        identity = id(current)
        if identity in visited:
            return
        visited.add(identity)
        if torch.is_tensor(current):
            found.append(current)
            return
        if is_dataclass(current) and not isinstance(current, type):
            for item in fields(current):
                visit(getattr(current, item.name))
            return
        if isinstance(current, dict):
            for item in current.values():
                visit(item)
            return
        if isinstance(current, (tuple, list)):
            for item in current:
                visit(item)

    visit(value)
    return tuple(found)


@dataclass(frozen=True)
class WeakTensorRecord:
    """Weak tensor reference plus immutable, scalar-only storage metadata."""

    reference: weakref.ReferenceType[torch.Tensor]
    object_id: int
    storage_key: StorageKey
    storage_nbytes: int
    shape: tuple[int, ...]
    dtype: str
    device: str

    @classmethod
    def from_tensor(cls, value: torch.Tensor) -> "WeakTensorRecord":
        key = tensor_storage_key(value)
        return cls(
            reference=weakref.ref(value),
            object_id=id(value),
            storage_key=key,
            storage_nbytes=key[2],
            shape=tuple(int(item) for item in value.shape),
            dtype=str(value.dtype),
            device=str(value.device),
        )

    @property
    def alive(self) -> bool:
        return self.reference() is not None


def weak_tensor_records(value: Any) -> tuple[WeakTensorRecord, ...]:
    """Return storage-deduplicated weak records for a project container."""

    records: dict[StorageKey, WeakTensorRecord] = {}
    tensors = walk_tensors(value)
    try:
        for tensor in tensors:
            record = WeakTensorRecord.from_tensor(tensor)
            records.setdefault(record.storage_key, record)
    finally:
        del tensors
    return tuple(records[key] for key in sorted(records))


def alive_storage_keys(
    records: Iterable[WeakTensorRecord],
) -> set[StorageKey]:
    """Return keys whose representative tensor object remains alive."""

    return {record.storage_key for record in records if record.alive}
