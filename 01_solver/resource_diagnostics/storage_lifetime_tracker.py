"""Generation-aware weakref and old-storage lifetime accounting."""

from __future__ import annotations

from dataclasses import dataclass
import gc
from typing import Any, Iterable
import weakref

from resource_diagnostics.weakref_tracker import (
    StorageKey,
    WeakTensorRecord,
    weak_tensor_records,
)


@dataclass(frozen=True)
class LifetimeCohort:
    generation: int
    semantic_slot: str
    object_reference: weakref.ReferenceType[Any] | None
    tensors: tuple[WeakTensorRecord, ...]


class StorageLifetimeTracker:
    """Track former-step objects while retaining only weak references."""

    def __init__(self, *, maximum_age: int = 4) -> None:
        if maximum_age < 2:
            raise ValueError("maximum_age must be at least two steps")
        self.maximum_age = int(maximum_age)
        self._cohorts: list[LifetimeCohort] = []

    def watch(self, *, generation: int, semantic_slot: str, value: Any) -> None:
        if not semantic_slot:
            raise ValueError("semantic_slot must be nonempty")
        try:
            object_reference: weakref.ReferenceType[Any] | None = weakref.ref(value)
        except TypeError:
            object_reference = None
        self._cohorts.append(
            LifetimeCohort(
                generation=int(generation),
                semantic_slot=str(semantic_slot),
                object_reference=object_reference,
                tensors=weak_tensor_records(value),
            )
        )

    def observe(
        self,
        *,
        current_step: int,
        current_storage_keys: set[StorageKey],
        collect: bool,
    ) -> dict[str, Any]:
        if collect:
            gc.collect()
        alive_by_age = {0: 0, 1: 0, 2: 0}
        old_keys: set[StorageKey] = set()
        old_slots: set[str] = set()
        simultaneous_slot_generations: dict[str, set[int]] = {}
        watched = 0
        alive_tensor_objects = 0
        for cohort in self._cohorts:
            age = int(current_step) - cohort.generation
            alive_records = [record for record in cohort.tensors if record.alive]
            watched += len(cohort.tensors)
            alive_tensor_objects += len(alive_records)
            if age in alive_by_age:
                alive_by_age[age] += len(alive_records)
            if age >= 2:
                for record in alive_records:
                    if record.storage_key not in current_storage_keys:
                        old_keys.add(record.storage_key)
                        old_slots.add(cohort.semantic_slot)
                        simultaneous_slot_generations.setdefault(
                            cohort.semantic_slot, set()
                        ).add(cohort.generation)
        repeated_history_slots = sum(
            len(generations) > 1
            for generations in simultaneous_slot_generations.values()
        )
        return {
            "step": int(current_step),
            "gc_collected": bool(collect),
            "watched_tensor_reference_count": int(watched),
            "alive_tensor_reference_count": int(alive_tensor_objects),
            "age0_alive_tensor_reference_count": int(alive_by_age[0]),
            "age1_alive_tensor_reference_count": int(alive_by_age[1]),
            "age2_alive_tensor_reference_count": int(alive_by_age[2]),
            "old_survivor_storage_count": len(old_keys),
            "old_survivor_bytes": int(sum(key[2] for key in old_keys)),
            "old_survivor_slot_count": len(old_slots),
            "same_slot_multiple_generation_count": int(repeated_history_slots),
            "old_survivor_storage_keys": old_keys,
        }

    def prune(self, *, current_step: int) -> None:
        retained: list[LifetimeCohort] = []
        for cohort in self._cohorts:
            alive = any(record.alive for record in cohort.tensors)
            if alive or int(current_step) - cohort.generation <= self.maximum_age:
                retained.append(cohort)
        self._cohorts = retained

    def surviving_tensor_objects(
        self,
        *,
        current_step: int,
        current_storage_keys: set[StorageKey],
        minimum_age: int = 2,
    ) -> list[tuple[str, int, Any]]:
        """Temporarily materialize confirmed survivors for sparse referrer audit."""

        survivors: list[tuple[str, int, Any]] = []
        seen: set[StorageKey] = set()
        for cohort in self._cohorts:
            if int(current_step) - cohort.generation < int(minimum_age):
                continue
            for record in cohort.tensors:
                value = record.reference()
                if (
                    value is not None
                    and record.storage_key not in current_storage_keys
                    and record.storage_key not in seen
                ):
                    seen.add(record.storage_key)
                    survivors.append(
                        (cohort.semantic_slot, cohort.generation, value)
                    )
        return survivors

    @property
    def cohort_count(self) -> int:
        return len(self._cohorts)


def storage_keys(values: Iterable[Any]) -> set[StorageKey]:
    """Return explicit current storage keys without retaining input tensors."""

    keys: set[StorageKey] = set()
    for value in values:
        for record in weak_tensor_records(value):
            if record.alive:
                keys.add(record.storage_key)
    return keys
