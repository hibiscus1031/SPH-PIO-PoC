"""Backend-aware wall-clock timing helpers for Stage 01 experiments.

MPS kernels execute asynchronously, so synchronization is performed immediately
before and after every measured region.  Timings are ordinary Python values by
design; no simulation tensor is detached or converted by this module.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import asdict, dataclass
import math
from time import perf_counter
from typing import Any, TypeVar

import torch
from torch import Tensor


T = TypeVar("T")


def _as_device(device: torch.device | str | Tensor | None) -> torch.device:
    if isinstance(device, Tensor):
        return device.device
    if device is None:
        return torch.device("cpu")
    return torch.device(device)


def synchronize_device(device: torch.device | str | Tensor | None) -> None:
    """Synchronize a supported backend before a wall-clock boundary.

    CPU operations need no explicit synchronization.  An unavailable MPS
    backend raises rather than silently falling back to CPU.  CUDA is
    intentionally rejected because NVIDIA backends are out of scope for this
    Apple-Silicon project.
    """

    normalized = _as_device(device)
    if normalized.type == "cpu":
        return
    if normalized.type == "mps":
        if not torch.backends.mps.is_available():
            raise RuntimeError("MPS synchronization requested but MPS is unavailable")
        torch.mps.synchronize()
        return
    if normalized.type == "cuda":
        raise ValueError("CUDA/NVIDIA backends are out of scope for SPH-PIO-PoC")
    raise ValueError(f"unsupported timing backend: {normalized.type!r}")


@dataclass(frozen=True)
class RuntimeSummary:
    """Serializable descriptive statistics for measured step durations."""

    count: int
    total_seconds: float
    mean_seconds: float
    min_seconds: float
    max_seconds: float
    std_seconds: float

    def as_dict(self) -> dict[str, int | float]:
        """Return a shallow dictionary suitable for a CSV row."""

        return asdict(self)


class RuntimeTracker:
    """Record synchronized per-step wall-clock durations.

    Use ``start``/``stop`` directly or ``with tracker.measure():``.  A tracker
    is deliberately not re-entrant: nested measurements would make per-step
    accounting ambiguous.
    """

    def __init__(self, device: torch.device | str | Tensor | None = None) -> None:
        self.device = _as_device(device)
        self._durations: list[float] = []
        self._started_at: float | None = None

    @property
    def durations(self) -> tuple[float, ...]:
        """Return an immutable snapshot of recorded seconds."""

        return tuple(self._durations)

    def start(self) -> None:
        """Start one synchronized measurement."""

        if self._started_at is not None:
            raise RuntimeError("RuntimeTracker is already measuring")
        synchronize_device(self.device)
        self._started_at = perf_counter()

    def stop(self) -> float:
        """Stop, record, and return the current measurement in seconds."""

        if self._started_at is None:
            raise RuntimeError("RuntimeTracker.stop() called before start()")
        synchronize_device(self.device)
        duration = perf_counter() - self._started_at
        self._started_at = None
        self.record(duration)
        return duration

    def record(self, duration_seconds: float) -> None:
        """Append an externally measured finite, non-negative duration."""

        duration = float(duration_seconds)
        if not math.isfinite(duration) or duration < 0:
            raise ValueError(
                "duration_seconds must be finite and non-negative; "
                f"got {duration_seconds!r}"
            )
        self._durations.append(duration)

    @contextmanager
    def measure(self) -> Iterator["RuntimeTracker"]:
        """Context manager that records one duration even if the body fails."""

        self.start()
        try:
            yield self
        finally:
            self.stop()

    def reset(self) -> None:
        """Discard recorded values when no measurement is active."""

        if self._started_at is not None:
            raise RuntimeError("cannot reset an active RuntimeTracker")
        self._durations.clear()

    def summary(self) -> RuntimeSummary:
        """Return descriptive statistics, or raise if nothing was recorded."""

        if not self._durations:
            raise ValueError("no runtime measurements have been recorded")
        values = torch.tensor(self._durations, dtype=torch.float64)
        return RuntimeSummary(
            count=len(self._durations),
            total_seconds=float(values.sum()),
            mean_seconds=float(values.mean()),
            min_seconds=float(values.amin()),
            max_seconds=float(values.amax()),
            std_seconds=float(values.std(unbiased=False)),
        )


def time_callable(
    function: Callable[[], T],
    *,
    device: torch.device | str | Tensor | None = None,
    warmup: int = 0,
    repeats: int = 1,
) -> tuple[T, RuntimeSummary]:
    """Warm up and repeatedly time a zero-argument callable.

    The callable runs with the caller's existing autograd mode.  Consequently
    it can represent a forward pass, a backward pass, or a complete step.
    """

    if warmup < 0:
        raise ValueError("warmup must be non-negative")
    if repeats <= 0:
        raise ValueError("repeats must be positive")
    for _ in range(warmup):
        result = function()
    synchronize_device(device)

    tracker = RuntimeTracker(device)
    for _ in range(repeats):
        with tracker.measure():
            result = function()
    return result, tracker.summary()


def device_memory_bytes(
    device: torch.device | str | Tensor | None,
) -> Mapping[str, int | None]:
    """Return available PyTorch memory counters without third-party tools.

    CPU allocation is not exposed through a comparable PyTorch API, so its
    values are ``None``.  Missing MPS APIs are also reported as ``None`` rather
    than fabricated or inferred.
    """

    normalized = _as_device(device)
    if normalized.type == "cpu":
        return {
            "current_allocated_bytes": None,
            "driver_allocated_bytes": None,
            "recommended_max_bytes": None,
        }
    if normalized.type != "mps":
        if normalized.type == "cuda":
            raise ValueError("CUDA/NVIDIA backends are out of scope for SPH-PIO-PoC")
        raise ValueError(f"unsupported memory backend: {normalized.type!r}")
    if not torch.backends.mps.is_available():
        raise RuntimeError("MPS memory requested but MPS is unavailable")

    def _optional_counter(name: str) -> int | None:
        counter = getattr(torch.mps, name, None)
        return int(counter()) if callable(counter) else None

    return {
        "current_allocated_bytes": _optional_counter("current_allocated_memory"),
        "driver_allocated_bytes": _optional_counter("driver_allocated_memory"),
        "recommended_max_bytes": _optional_counter("recommended_max_memory"),
    }


__all__ = [
    "RuntimeSummary",
    "RuntimeTracker",
    "device_memory_bytes",
    "synchronize_device",
    "time_callable",
]
