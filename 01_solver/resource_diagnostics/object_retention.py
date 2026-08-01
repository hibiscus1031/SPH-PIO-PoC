"""Weak-reference probes for bounded solver-object lifetime checks."""

from __future__ import annotations

from collections import defaultdict
import gc
import weakref
from typing import Any


class RetentionTracker:
    """Track object liveness without extending the objects' lifetimes."""

    def __init__(self) -> None:
        self._references: dict[str, list[weakref.ReferenceType[Any]]] = (
            defaultdict(list)
        )

    def watch(self, label: str, value: Any) -> None:
        if not label:
            raise ValueError("retention label must be nonempty")
        self._references[str(label)].append(weakref.ref(value))

    def snapshot(self, *, collect: bool = True) -> dict[str, int]:
        if collect:
            gc.collect()
        result: dict[str, int] = {}
        alive_total = 0
        watched_total = 0
        for label in sorted(self._references):
            refs = self._references[label]
            alive = sum(reference() is not None for reference in refs)
            result[f"{label}_watched"] = len(refs)
            result[f"{label}_alive"] = alive
            watched_total += len(refs)
            alive_total += alive
        result["watched_total"] = watched_total
        result["alive_total"] = alive_total
        return result

    def clear_dead(self) -> None:
        for label, refs in tuple(self._references.items()):
            retained = [reference for reference in refs if reference() is not None]
            if retained:
                self._references[label] = retained
            else:
                del self._references[label]
