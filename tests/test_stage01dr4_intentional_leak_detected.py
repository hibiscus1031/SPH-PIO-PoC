from __future__ import annotations

from resource_diagnostics.lifetime_gate_fixtures import run_lifetime_fixture


def test_intentional_history_leak_has_old_survivors() -> None:
    result = run_lifetime_fixture("C", steps=8)
    assert result["peak_old_survivor_storage_count"] > 0
    assert result["final_retention_signal"] is True
