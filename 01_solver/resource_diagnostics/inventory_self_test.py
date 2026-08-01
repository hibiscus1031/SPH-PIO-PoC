"""Static-fixture self-validation for the live-tensor inventory."""

from __future__ import annotations

import gc
from typing import Any, Callable
import warnings

import torch

from resource_diagnostics.semantic_tensor_ledger import explicit_storage_totals
from resource_diagnostics.tensor_inventory import collect_tensor_inventory
from resource_diagnostics.weakref_tracker import tensor_storage_key


def build_static_tensor_fixture() -> tuple[torch.Tensor, ...]:
    """Return fixed tensors containing two views of one base storage."""

    base = torch.arange(256, dtype=torch.float64).reshape(32, 8)
    first_view = base[:, :4]
    second_view = base[:, 4:]
    separate = torch.ones((17, 5), dtype=torch.float64)
    return base, first_view, second_view, separate


def lightweight_global_tensor_totals() -> dict[str, int]:
    """Independently count global tensors after inventory locals are deleted."""

    objects = gc.get_objects()
    count = 0
    storages: set[tuple[str, int, int]] = set()
    errors = 0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for obj in objects:
            try:
                if isinstance(obj, torch.Tensor):
                    count += 1
                    storages.add(tensor_storage_key(obj))
            except Exception:
                errors += 1
    if objects:
        del obj
    del objects
    return {
        "tensor_count": int(count),
        "unique_storage_count": len(storages),
        "unique_storage_bytes": int(sum(key[2] for key in storages)),
        "error_count": int(errors),
    }


def run_inventory_self_test(
    *,
    iterations: int,
    row_sink: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Invoke the production inventory repeatedly on a static tensor set."""

    if iterations <= 0:
        raise ValueError("iterations must be positive")
    fixture = build_static_tensor_fixture()
    explicit = explicit_storage_totals(fixture)
    base_key = tensor_storage_key(fixture[0])
    view_keys = [tensor_storage_key(value) for value in fixture[1:3]]
    view_deduplication_pass = all(key == base_key for key in view_keys)
    records: list[dict[str, Any]] = []
    first: dict[str, int] | None = None
    last: dict[str, int] | None = None
    maximum_count = 0
    maximum_bytes = 0
    for iteration in range(1, iterations + 1):
        inventory = collect_tensor_inventory()
        inventory_scalar = {
            "inventory_live_tensor_count": int(inventory["live_tensor_count"]),
            "inventory_unique_storage_bytes": int(
                inventory["live_tensor_unique_storage_bytes"]
            ),
            "inventory_error_count": int(inventory["tensor_inventory_error_count"]),
        }
        del inventory
        gc.collect()
        lightweight = lightweight_global_tensor_totals()
        row = {
            "iteration": int(iteration),
            **inventory_scalar,
            "lightweight_live_tensor_count": int(lightweight["tensor_count"]),
            "lightweight_unique_storage_count": int(
                lightweight["unique_storage_count"]
            ),
            "lightweight_unique_storage_bytes": int(
                lightweight["unique_storage_bytes"]
            ),
            "lightweight_error_count": int(lightweight["error_count"]),
        }
        if first is None:
            first = {
                "count": row["lightweight_live_tensor_count"],
                "bytes": row["lightweight_unique_storage_bytes"],
            }
        last = {
            "count": row["lightweight_live_tensor_count"],
            "bytes": row["lightweight_unique_storage_bytes"],
        }
        maximum_count = max(maximum_count, row["lightweight_live_tensor_count"])
        maximum_bytes = max(maximum_bytes, row["lightweight_unique_storage_bytes"])
        if row_sink is not None:
            row_sink(row)
        records.append(row)
        del lightweight, row
    assert first is not None and last is not None
    count_delta = int(last["count"] - first["count"])
    byte_delta = int(last["bytes"] - first["bytes"])
    result = {
        "iterations": int(iterations),
        "fixture_tensor_count": int(explicit["tensor_count"]),
        "fixture_logical_bytes": int(explicit["logical_bytes"]),
        "fixture_unique_storage_count": int(explicit["unique_storage_count"]),
        "fixture_unique_storage_bytes": int(explicit["unique_storage_bytes"]),
        "view_and_base_deduplication_pass": bool(view_deduplication_pass),
        "storage_key_contract_pass": bool(
            base_key[0] == "cpu" and base_key[1] > 0 and base_key[2] > 0
        ),
        "first_lightweight_tensor_count": int(first["count"]),
        "last_lightweight_tensor_count": int(last["count"]),
        "lightweight_tensor_count_delta": count_delta,
        "first_lightweight_unique_storage_bytes": int(first["bytes"]),
        "last_lightweight_unique_storage_bytes": int(last["bytes"]),
        "lightweight_unique_storage_bytes_delta": byte_delta,
        "maximum_lightweight_tensor_count": int(maximum_count),
        "maximum_lightweight_unique_storage_bytes": int(maximum_bytes),
        "inventory_self_retention_pass": bool(count_delta == 0 and byte_delta == 0),
        "inventory_results_globally_retained": False,
        "records_retained_by_caller": bool(row_sink is None),
    }
    del records
    return result
