"""SPH-independent lifetime fixtures for the Stage 01D-R4 semantic gate."""

from __future__ import annotations

import gc
from typing import Any

import torch

from resource_diagnostics.weakref_semantics import WeakrefSemanticGate


def _tensor(step: int) -> torch.Tensor:
    return torch.tensor([float(step), float(step + 1)], dtype=torch.float64)


def run_lifetime_fixture(name: str, *, steps: int = 100) -> dict[str, Any]:
    if steps < 4:
        raise ValueError("fixtures require at least four logical steps")
    gate = WeakrefSemanticGate()
    peak_old = 0
    peak_same_slot = 0
    peak_current = 0
    final: dict[str, Any]
    history: list[torch.Tensor] = []
    previous: torch.Tensor | None = None
    current = _tensor(0)
    gate.register_current(step=0, named_values={"fixture.current": current})
    gate.watch(generation=0, semantic_slot="fixture.current", value=current)
    for step in range(1, steps + 1):
        if name == "A":
            current.add_(1.0)
            gate.register_current(step=step, named_values={"fixture.current": current})
        elif name == "B":
            retired = current
            gate.watch(generation=step - 1, semantic_slot="fixture.current", value=retired)
            current = _tensor(step)
            del retired
            gate.register_current(step=step, named_values={"fixture.current": current})
        elif name == "C":
            retired = current
            gate.watch(generation=step - 1, semantic_slot="fixture.current", value=retired)
            history.append(retired)
            current = _tensor(step)
            gate.register_current(step=step, named_values={"fixture.current": current})
            del retired
        elif name == "D":
            retired = previous
            previous = current
            current = _tensor(step)
            gate.register_current(
                step=step,
                named_values={
                    "pipeline.current": current,
                    "pipeline.previous": previous,
                },
            )
            gate.watch(
                generation=step - 1,
                semantic_slot="pipeline.previous",
                value=previous,
            )
            del retired
        else:
            raise ValueError(f"unknown fixture {name!r}")
        gc.collect()
        final = gate.observe(current_step=step, collect=False)
        peak_old = max(peak_old, int(final["old_survivor_storage_count"]))
        peak_same_slot = max(
            peak_same_slot, int(final["same_slot_multigeneration_count"])
        )
        peak_current = max(
            peak_current, int(final["current_persistent_reference_count"])
        )
    expected_retention = name == "C"
    classified_correctly = bool(
        (expected_retention and peak_old > 0 and peak_same_slot > 0)
        or (not expected_retention and peak_old == 0 and peak_same_slot == 0)
    )
    if name == "A":
        classified_correctly = bool(classified_correctly and peak_current > 0)
    return {
        "fixture": name,
        "steps": int(steps),
        "expected_retention": expected_retention,
        "peak_current_persistent_reference_count": peak_current,
        "peak_old_survivor_storage_count": peak_old,
        "peak_same_slot_multigeneration_count": peak_same_slot,
        "final_retention_signal": bool(final["retention_signal"]),
        "classified_correctly": classified_correctly,
    }
