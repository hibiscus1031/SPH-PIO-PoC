"""Scalar-only Python GC schedule observations for Stage 01D-R5."""

from __future__ import annotations

import gc
import time
from typing import Any


def gc_scalar_snapshot() -> dict[str, Any]:
    stats = gc.get_stats()
    return {
        "gc_count_generation_0": int(gc.get_count()[0]),
        "gc_count_generation_1": int(gc.get_count()[1]),
        "gc_count_generation_2": int(gc.get_count()[2]),
        "gc_collections_generation_0": int(stats[0]["collections"]),
        "gc_collections_generation_1": int(stats[1]["collections"]),
        "gc_collections_generation_2": int(stats[2]["collections"]),
        "gc_collected_generation_0": int(stats[0]["collected"]),
        "gc_collected_generation_1": int(stats[1]["collected"]),
        "gc_collected_generation_2": int(stats[2]["collected"]),
    }


def timed_collect() -> dict[str, int | float]:
    started = time.perf_counter()
    collected = int(gc.collect())
    return {
        "manual_gc_collected_objects": collected,
        "manual_gc_wall_seconds": time.perf_counter() - started,
    }


def generation_membership(object_ids: set[int]) -> dict[int, int]:
    """Map requested tracked object IDs to a CPython GC generation."""

    remaining = set(object_ids)
    membership: dict[int, int] = {}
    for generation in (0, 1, 2):
        objects = gc.get_objects(generation)
        try:
            for value in objects:
                identity = id(value)
                if identity in remaining:
                    membership[identity] = generation
                    remaining.remove(identity)
            if objects:
                del value
        finally:
            del objects
        if not remaining:
            break
    return membership
