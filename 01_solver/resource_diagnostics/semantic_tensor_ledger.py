"""Semantic, storage-deduplicated live-tensor ledger for Stage 01D-R2."""

from __future__ import annotations

from dataclasses import dataclass
import gc
from typing import Any, Iterable, Mapping
import warnings
import weakref

import torch

from resource_diagnostics.weakref_tracker import StorageKey, tensor_storage_key


SEMANTIC_CATEGORIES = (
    "current_state",
    "current_neighborhood",
    "current_density_EOS",
    "current_pressure_force",
    "current_viscosity_force",
    "RK2_midpoint",
    "diagnostics_temporary",
    "archive_checkpoint",
    "memory_monitor_temporary",
    "unknown",
)

_CATEGORY_PRECEDENCE = {name: index for index, name in enumerate(SEMANTIC_CATEGORIES)}


@dataclass
class _Registration:
    reference: weakref.ReferenceType[torch.Tensor]
    category: str
    slot: str
    generation: int
    current: bool


class SemanticTensorLedger:
    """Attach explicit semantics without keeping project tensors alive."""

    def __init__(self) -> None:
        self._registrations: dict[int, _Registration] = {}

    def register(
        self,
        value: torch.Tensor,
        *,
        category: str,
        slot: str,
        generation: int,
        current: bool = True,
    ) -> None:
        if category not in SEMANTIC_CATEGORIES or category == "unknown":
            raise ValueError(f"invalid explicit tensor category: {category!r}")
        if not torch.is_tensor(value):
            raise TypeError("semantic ledger values must be tensors")
        if not slot:
            raise ValueError("semantic slot must be nonempty")
        object_id = id(value)

        def remove(reference: weakref.ReferenceType[torch.Tensor]) -> None:
            existing = self._registrations.get(object_id)
            if existing is not None and existing.reference is reference:
                self._registrations.pop(object_id, None)

        self._registrations[object_id] = _Registration(
            reference=weakref.ref(value, remove),
            category=category,
            slot=str(slot),
            generation=int(generation),
            current=bool(current),
        )

    def register_many(
        self,
        values: Mapping[str, torch.Tensor],
        *,
        category: str,
        generation: int,
        current: bool = True,
    ) -> None:
        for slot, value in values.items():
            self.register(
                value,
                category=category,
                slot=slot,
                generation=generation,
                current=current,
            )

    def mark_noncurrent(self, values: Iterable[torch.Tensor]) -> None:
        for value in values:
            registration = self._registrations.get(id(value))
            if registration is not None and registration.reference() is value:
                registration.current = False

    def prune_dead(self) -> None:
        for object_id, registration in tuple(self._registrations.items()):
            if registration.reference() is None:
                self._registrations.pop(object_id, None)

    def snapshot(
        self,
        *,
        step: int,
        old_survivor_storage_keys: set[StorageKey] | None = None,
    ) -> dict[str, Any]:
        """Return scalar rows and deduplicated semantic byte totals.

        The temporary ``gc.get_objects`` list is destroyed before returning.
        No tensor is present in the returned structure.
        """

        old_keys = set() if old_survivor_storage_keys is None else set(old_survivor_storage_keys)
        objects = gc.get_objects()
        rows: list[dict[str, Any]] = []
        storage_rows: dict[StorageKey, dict[str, Any]] = {}
        error_count = 0
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for obj in objects:
                try:
                    if not isinstance(obj, torch.Tensor):
                        continue
                    key = tensor_storage_key(obj)
                    registration = self._registrations.get(id(obj))
                    if registration is not None and registration.reference() is obj:
                        category = registration.category
                        slot = registration.slot
                        generation = registration.generation
                        current = registration.current
                    else:
                        category = "unknown"
                        slot = "unregistered"
                        generation = -1
                        current = False
                    base = getattr(obj, "_base", None)
                    row = {
                        "step": int(step),
                        "python_object_id": int(id(obj)),
                        "storage_data_ptr": int(key[1]),
                        "storage_nbytes": int(key[2]),
                        "shape": "x".join(str(int(item)) for item in obj.shape),
                        "stride": "x".join(str(int(item)) for item in obj.stride()),
                        "dtype": str(obj.dtype),
                        "device": str(obj.device),
                        "requires_grad": bool(obj.requires_grad),
                        "has_grad_fn": bool(obj.grad_fn is not None),
                        "is_view": bool(base is not None),
                        "base_storage_id": f"{key[0]}:{key[1]}:{key[2]}",
                        "semantic_category": category,
                        "semantic_slot": slot,
                        "generation": int(generation),
                        "is_current_registration": bool(current),
                        "is_old_survivor_storage": bool(key in old_keys),
                    }
                    rows.append(row)
                    incumbent = storage_rows.get(key)
                    if incumbent is None or _CATEGORY_PRECEDENCE[category] < _CATEGORY_PRECEDENCE[incumbent["semantic_category"]]:
                        storage_rows[key] = row
                    del base
                except Exception:
                    error_count += 1
        if objects:
            del obj
        del objects
        rows.sort(key=lambda row: (row["storage_data_ptr"], row["python_object_id"]))

        category_bytes = {category: 0 for category in SEMANTIC_CATEGORIES}
        for row in storage_rows.values():
            category_bytes[row["semantic_category"]] += int(row["storage_nbytes"])
        current_state_bytes = category_bytes["current_state"]
        current_edge_bytes = category_bytes["current_neighborhood"]
        force_categories = (
            "current_density_EOS",
            "current_pressure_force",
            "current_viscosity_force",
            "RK2_midpoint",
            "diagnostics_temporary",
        )
        current_force_bytes = sum(category_bytes[name] for name in force_categories)
        monitor_bytes = category_bytes["memory_monitor_temporary"]
        unknown_bytes = category_bytes["unknown"]
        old_survivor_bytes = sum(key[2] for key in old_keys if key in storage_rows)
        summary = {
            "step": int(step),
            "live_tensor_count": len(rows),
            "live_unique_storage_count": len(storage_rows),
            "live_total_bytes": int(sum(key[2] for key in storage_rows)),
            "current_state_bytes": int(current_state_bytes),
            "current_edge_dependent_bytes": int(current_edge_bytes),
            "current_force_workspace_bytes": int(current_force_bytes),
            "monitor_bytes": int(monitor_bytes),
            "unknown_live_bytes": int(unknown_bytes),
            "old_survivor_bytes": int(old_survivor_bytes),
            "old_survivor_storage_count": int(sum(key in storage_rows for key in old_keys)),
            "inventory_error_count": int(error_count),
            **{f"semantic_{name}_bytes": int(value) for name, value in category_bytes.items()},
        }
        return {"summary": summary, "tensors": rows}


def explicit_storage_totals(values: Iterable[torch.Tensor]) -> dict[str, int]:
    """Count logical tensors and unique storages for an explicit fixture."""

    tensors = tuple(values)
    storages = {tensor_storage_key(value) for value in tensors}
    return {
        "tensor_count": len(tensors),
        "logical_bytes": int(sum(value.numel() * value.element_size() for value in tensors)),
        "unique_storage_count": len(storages),
        "unique_storage_bytes": int(sum(key[2] for key in storages)),
    }
