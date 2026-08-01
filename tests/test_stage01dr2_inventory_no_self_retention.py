from __future__ import annotations

from resource_diagnostics.inventory_self_test import run_inventory_self_test


def test_repeated_inventory_does_not_retain_its_own_tensor_objects() -> None:
    rows: list[dict[str, object]] = []
    summary = run_inventory_self_test(iterations=20, row_sink=rows.append)
    assert len(rows) == 20
    assert summary["inventory_self_retention_pass"] is True
    assert summary["view_and_base_deduplication_pass"] is True
    assert summary["storage_key_contract_pass"] is True
    assert summary["lightweight_tensor_count_delta"] == 0
    assert summary["lightweight_unique_storage_bytes_delta"] == 0
