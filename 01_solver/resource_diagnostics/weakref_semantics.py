"""Generation-aware weakref semantic gate for Stage 01D-R4."""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
import gc
from typing import Any, Mapping
import weakref

import torch

from resource_diagnostics.current_vs_retired_storage import (
    CurrentStorageManifest,
    build_current_storage_manifest,
    reference_semantic_class,
    storage_key_text,
)
from resource_diagnostics.weakref_tracker import StorageKey, tensor_storage_key


def _named_storage_tensors(value: Any) -> dict[StorageKey, tuple[str, torch.Tensor]]:
    """Return one non-retained semantic path per storage in a bounded container."""

    found: dict[StorageKey, tuple[str, torch.Tensor]] = {}
    visited: set[int] = set()

    def visit(current: Any, path: str) -> None:
        identity = id(current)
        if identity in visited:
            return
        visited.add(identity)
        if torch.is_tensor(current):
            found.setdefault(tensor_storage_key(current), (path or "tensor", current))
            return
        if is_dataclass(current) and not isinstance(current, type):
            for field in fields(current):
                child = f"{path}.{field.name}" if path else field.name
                visit(getattr(current, field.name), child)
            return
        if isinstance(current, dict):
            for name, item in current.items():
                child = f"{path}.{name}" if path else str(name)
                visit(item, child)
            return
        if isinstance(current, (tuple, list)):
            for index, item in enumerate(current):
                child = f"{path}.{index}" if path else str(index)
                visit(item, child)

    visit(value, "")
    return found


@dataclass
class SemanticWeakReference:
    reference: weakref.ReferenceType[torch.Tensor]
    object_id: int
    storage_key: StorageKey
    semantic_slot: str
    generation: int
    creation_step: int
    first_observed_step: int
    last_observed_step: int


class WeakrefSemanticGate:
    """Classify old weakrefs by current storage membership, never age alone."""

    def __init__(self, *, minimum_old_age: int = 2) -> None:
        if minimum_old_age < 2:
            raise ValueError("minimum_old_age must be at least two")
        self.minimum_old_age = int(minimum_old_age)
        self._records: list[SemanticWeakReference] = []
        self._first_storage_step: dict[StorageKey, int] = {}
        self._last_storage_step: dict[StorageKey, int] = {}
        self._manifest = build_current_storage_manifest({})

    def register_current(self, *, step: int, named_values: Mapping[str, Any]) -> None:
        self._manifest = build_current_storage_manifest(named_values)
        for key in self._manifest.storage_keys:
            self._first_storage_step.setdefault(key, int(step))
            self._last_storage_step[key] = int(step)

    def watch(self, *, generation: int, semantic_slot: str, value: Any) -> None:
        if not semantic_slot:
            raise ValueError("semantic_slot must be nonempty")
        tensors = _named_storage_tensors(value)
        try:
            for key, (path, tensor) in tensors.items():
                self._first_storage_step.setdefault(key, int(generation))
                self._last_storage_step[key] = int(generation)
                slot = str(semantic_slot)
                if path != "tensor":
                    slot = f"{slot}.{path}"
                self._records.append(
                    SemanticWeakReference(
                        reference=weakref.ref(tensor),
                        object_id=id(tensor),
                        storage_key=key,
                        semantic_slot=slot,
                        generation=int(generation),
                        creation_step=self._first_storage_step[key],
                        first_observed_step=int(generation),
                        last_observed_step=int(generation),
                    )
                )
        finally:
            del tensors

    def observe(
        self,
        *,
        current_step: int,
        current_storage_keys: set[StorageKey] | None = None,
        collect: bool,
    ) -> dict[str, Any]:
        if collect:
            gc.collect()
        if current_storage_keys is not None:
            slots = {
                key: self._manifest.slots_by_storage.get(key, ("current_solver_value",))
                for key in current_storage_keys
            }
            self._manifest = CurrentStorageManifest(
                storage_keys=frozenset(current_storage_keys),
                object_ids=self._manifest.object_ids,
                slots_by_storage=slots,
            )
        for record in self._records:
            if record.reference() is not None:
                record.last_observed_step = int(current_step)
                self._last_storage_step[record.storage_key] = int(current_step)
        rows = self.audit_rows(current_step=current_step, include_referrers=False)
        retired_records = [
            record
            for record in self._records
            if record.reference() is not None
            and int(current_step) - record.generation >= self.minimum_old_age
            and reference_semantic_class(record.storage_key, self._manifest)
            == "retired_reference"
        ]
        retired_keys = {
            record.storage_key for record in retired_records
        }
        slot_storages: dict[str, set[StorageKey]] = {}
        for record in retired_records:
            slot_storages.setdefault(record.semantic_slot, set()).add(record.storage_key)
        multigeneration_slots = {
            slot for slot, keys in slot_storages.items() if len(keys) >= 2
        }
        return {
            "step": int(current_step),
            "age2_alive_tensor_reference_count": len(rows),
            "current_persistent_reference_count": sum(
                row["semantic_class"] == "current_persistent_reference" for row in rows
            ),
            "retired_reference_count": sum(
                row["semantic_class"] == "retired_reference" for row in rows
            ),
            "old_survivor_storage_count": len(retired_keys),
            "old_survivor_bytes": int(sum(key[2] for key in retired_keys)),
            "same_slot_multigeneration_count": len(multigeneration_slots),
            "same_slot_multigeneration_slots": sorted(multigeneration_slots),
            "retention_signal": bool(retired_keys or multigeneration_slots),
        }

    def audit_rows(
        self,
        *,
        current_step: int,
        include_referrers: bool,
        fixed_edge_storage_keys: set[StorageKey] | None = None,
    ) -> list[dict[str, Any]]:
        fixed = set() if fixed_edge_storage_keys is None else fixed_edge_storage_keys
        alive = [
            record
            for record in self._records
            if record.reference() is not None
            and int(current_step) - record.generation == self.minimum_old_age
        ]
        rows: list[dict[str, Any]] = []
        for record in alive:
            value = record.reference()
            semantic_class = reference_semantic_class(record.storage_key, self._manifest)
            same_slot_records = [
                item
                for item in self._records
                if item.semantic_slot == record.semantic_slot
                and item.reference() is not None
            ]
            same_slot_keys = {item.storage_key for item in same_slot_records}
            referrer_types: list[str] = []
            if include_referrers and value is not None:
                referrers = gc.get_referrers(value)
                try:
                    referrer_types = sorted({type(item).__name__ for item in referrers})
                finally:
                    del referrers
            rows.append(
                {
                    "semantic_slot": record.semantic_slot,
                    "object_id": record.object_id,
                    "storage_key": storage_key_text(record.storage_key),
                    "creation_step": record.creation_step,
                    "first_observed_step": record.first_observed_step,
                    "last_observed_step": record.last_observed_step,
                    "age": int(current_step) - record.generation,
                    "belongs_to_fixed_initial_edge_index": record.storage_key in fixed,
                    "still_read_by_current_solver": record.storage_key in self._manifest.storage_keys,
                    "has_same_slot_update_object": len(same_slot_records) >= 2,
                    "has_different_storage_generation": len(same_slot_keys) >= 2,
                    "is_current_working_set": semantic_class == "current_persistent_reference",
                    "is_retired_reference": semantic_class == "retired_reference",
                    "is_old_survivor": semantic_class == "retired_reference",
                    "direct_referrer_type_names": referrer_types,
                    "semantic_class": semantic_class,
                }
            )
        rows.sort(key=lambda row: (row["semantic_slot"], row["storage_key"], row["object_id"]))
        return rows

    @property
    def manifest(self) -> CurrentStorageManifest:
        return self._manifest
