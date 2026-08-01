from __future__ import annotations

from resource_diagnostics.lifetime_gate_fixtures import run_lifetime_fixture


def test_replaced_state_dies_within_two_steps() -> None:
    result = run_lifetime_fixture("B", steps=8)
    assert result["peak_old_survivor_storage_count"] == 0
    assert result["peak_same_slot_multigeneration_count"] == 0
    assert result["classified_correctly"] is True
