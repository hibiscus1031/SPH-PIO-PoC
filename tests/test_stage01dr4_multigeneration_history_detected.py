from __future__ import annotations

from resource_diagnostics.lifetime_gate_fixtures import run_lifetime_fixture


def test_same_slot_multigeneration_history_is_detected() -> None:
    result = run_lifetime_fixture("C", steps=8)
    assert result["peak_same_slot_multigeneration_count"] > 0
    assert result["classified_correctly"] is True
