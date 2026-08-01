"""Current-working-set versus retired-storage semantics for Stage 01D-R4."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from resource_diagnostics.weakref_tracker import (
    StorageKey,
    tensor_storage_key,
    walk_tensors,
)


@dataclass(frozen=True)
class CurrentStorageManifest:
    """Scalar-only identity of tensors the solver may still read."""

    storage_keys: frozenset[StorageKey]
    object_ids: frozenset[int]
    slots_by_storage: Mapping[StorageKey, tuple[str, ...]]


def build_current_storage_manifest(
    named_values: Mapping[str, Any],
) -> CurrentStorageManifest:
    slots: dict[StorageKey, set[str]] = {}
    object_ids: set[int] = set()
    for slot, value in named_values.items():
        tensors = walk_tensors(value)
        try:
            for tensor in tensors:
                key = tensor_storage_key(tensor)
                slots.setdefault(key, set()).add(str(slot))
                object_ids.add(id(tensor))
        finally:
            del tensors
    return CurrentStorageManifest(
        storage_keys=frozenset(slots),
        object_ids=frozenset(object_ids),
        slots_by_storage={
            key: tuple(sorted(names)) for key, names in sorted(slots.items())
        },
    )


def reference_semantic_class(
    storage_key: StorageKey,
    manifest: CurrentStorageManifest,
) -> str:
    """Classify a live storage without retaining its tensor object."""

    if storage_key in manifest.storage_keys:
        return "current_persistent_reference"
    return "retired_reference"


def storage_key_text(storage_key: StorageKey) -> str:
    device, pointer, nbytes = storage_key
    return f"{device}:{pointer}:{nbytes}"
