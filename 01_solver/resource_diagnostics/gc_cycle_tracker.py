"""Pre-GC retired Tensor provenance and generation tracking for R5."""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
import weakref
from typing import Any, Mapping

import torch

from resource_diagnostics.gc_schedule_probe import generation_membership
from resource_diagnostics.referrer_graph import build_type_referrer_graph
from resource_diagnostics.retired_object_provenance import (
    safe_owner_description,
    tensor_scalar_metadata,
)
from resource_diagnostics.weakref_tracker import StorageKey, tensor_storage_key


def _named_tensors(value: Any) -> dict[StorageKey, tuple[str, torch.Tensor]]:
    found: dict[StorageKey, tuple[str, torch.Tensor]] = {}
    visited: set[int] = set()

    def visit(current: Any, path: str) -> None:
        identity = id(current)
        if identity in visited:
            return
        visited.add(identity)
        if torch.is_tensor(current):
            found.setdefault(tensor_storage_key(current), (path or "tensor", current))
        elif is_dataclass(current) and not isinstance(current, type):
            for field in fields(current):
                visit(getattr(current, field.name), f"{path}.{field.name}" if path else field.name)
        elif isinstance(current, dict):
            for key, item in current.items():
                visit(item, f"{path}.{key}" if path else str(key))
        elif isinstance(current, (tuple, list)):
            for index, item in enumerate(current):
                visit(item, f"{path}.{index}" if path else str(index))

    visit(value, "")
    return found


@dataclass
class _Record:
    reference: weakref.ReferenceType[torch.Tensor]
    object_id: int
    storage_key: StorageKey
    semantic_slot: str
    creation_step: int
    generation: int
    replacement_step: int
    retirement_step: int | None = None
    last_alive_step: int = 0


class GCCycleTracker:
    def __init__(self, *, minimum_old_age: int = 2, capture_provenance: bool = False) -> None:
        self.minimum_old_age = int(minimum_old_age)
        self.capture_provenance = bool(capture_provenance)
        self._records: list[_Record] = []
        self._first_seen: dict[StorageKey, int] = {}
        self._current_keys: set[StorageKey] = set()
        self._instance_rows: dict[tuple[int, str, int], dict[str, Any]] = {}
        self._graphs: dict[str, dict[str, Any]] = {}

    def register_current(self, *, step: int, named_values: Mapping[str, Any]) -> None:
        current: set[StorageKey] = set()
        for value in named_values.values():
            tensors = _named_tensors(value)
            try:
                for key in tensors:
                    current.add(key)
                    self._first_seen.setdefault(key, int(step))
            finally:
                del tensors
        self._current_keys = current

    def watch_replacement(
        self,
        *,
        generation: int,
        replacement_step: int,
        semantic_slot: str,
        value: Any,
    ) -> None:
        tensors = _named_tensors(value)
        try:
            for key, (path, tensor) in tensors.items():
                self._first_seen.setdefault(key, int(generation))
                slot = semantic_slot if path == "tensor" else f"{semantic_slot}.{path}"
                self._records.append(
                    _Record(
                        reference=weakref.ref(tensor),
                        object_id=id(tensor),
                        storage_key=key,
                        semantic_slot=slot,
                        creation_step=self._first_seen[key],
                        generation=int(generation),
                        replacement_step=int(replacement_step),
                        last_alive_step=int(generation),
                    )
                )
        finally:
            del tensors

    def observe(self, *, step: int) -> dict[str, Any]:
        alive_retired: list[_Record] = []
        for record in self._records:
            value = record.reference()
            if value is None:
                continue
            record.last_alive_step = int(step)
            if record.storage_key not in self._current_keys:
                if record.retirement_step is None:
                    record.retirement_step = int(step)
                if int(step) - record.generation >= self.minimum_old_age:
                    alive_retired.append(record)
        retired_keys = {record.storage_key for record in alive_retired}
        slot_keys: dict[str, set[StorageKey]] = {}
        for record in alive_retired:
            slot_keys.setdefault(record.semantic_slot, set()).add(record.storage_key)
        multigeneration = {slot: keys for slot, keys in slot_keys.items() if len(keys) >= 2}
        if self.capture_provenance and alive_retired:
            self._capture(alive_retired, step=int(step))
        return {
            "retired_old_survivor_count": len(retired_keys),
            "retired_old_survivor_bytes": int(sum(key[2] for key in retired_keys)),
            "same_slot_multigeneration_count": len(multigeneration),
            "maximum_retired_generations_in_one_slot": max((len(keys) for keys in slot_keys.values()), default=0),
            "retired_slot_count": len(slot_keys),
        }

    def prune(self, *, step: int, grace_steps: int = 5) -> None:
        self._records = [
            record for record in self._records
            if record.reference() is not None
            or int(step) - record.generation <= int(grace_steps)
        ]

    def _capture(self, records: list[_Record], *, step: int) -> None:
        for record in records:
            existing = self._instance_rows.get(
                (record.object_id, record.semantic_slot, record.generation)
            )
            if existing is not None:
                existing["last_alive_step"] = step
        records = [
            record for record in records
            if (record.object_id, record.semantic_slot, record.generation)
            not in self._instance_rows
        ]
        if not records:
            return
        values = [(record, record.reference()) for record in records]
        values = [(record, value) for record, value in values if value is not None]
        membership = generation_membership({id(value) for _, value in values})
        try:
            for record, value in values:
                key = (record.object_id, record.semantic_slot, record.generation)
                row = self._instance_rows.get(key)
                if row is None:
                    row = {
                        "semantic_slot": record.semantic_slot,
                        **tensor_scalar_metadata(value),
                        "creation_step": record.creation_step,
                        "replacement_step": record.replacement_step,
                        "retirement_step": record.retirement_step,
                        "last_alive_step": step,
                        "gc_generation": membership.get(id(value), -1),
                        **safe_owner_description(value),
                    }
                    self._instance_rows[key] = row
                    owner_type = str(row["python_owner_object_type"])
                    graph_key = f"{owner_type}:{record.semantic_slot}"
                    if graph_key not in self._graphs and len(self._graphs) < 20:
                        self._graphs[graph_key] = {
                            "representative": graph_key,
                            "captured_before_gc": True,
                            **build_type_referrer_graph(value, maximum_depth=4),
                        }
                else:
                    row["last_alive_step"] = step
        finally:
            del values

    @property
    def instance_rows(self) -> list[dict[str, Any]]:
        return sorted(
            self._instance_rows.values(),
            key=lambda row: (str(row["semantic_slot"]), int(row["creation_step"]), int(row["tensor_object_id"])),
        )

    @property
    def referrer_graphs(self) -> list[dict[str, Any]]:
        return [self._graphs[key] for key in sorted(self._graphs)]
