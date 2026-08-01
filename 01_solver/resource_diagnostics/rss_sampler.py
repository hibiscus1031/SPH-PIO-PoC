"""Current-process memory sampling without importing PyTorch.

The module is deliberately standard-library-only so a worker can capture a
``process_start`` sample before importing NumPy, PyTorch, or the SPH solver.
Darwin's ``ru_maxrss`` is retained under an explicitly named peak field and is
never substituted for current RSS from ``libproc`` (or the ``ps`` fallback).
"""

from __future__ import annotations

import ctypes
import gc
import os
import re
import resource
import subprocess
import sys
import time
import tracemalloc
from collections.abc import Callable
from typing import Any, Mapping


MEMORY_SAMPLE_SCHEMA_VERSION = "sph-pio-poc.stage01dr.memory-sample.v1"
_DARWIN_PROC_PIDINFO: Any | None = None


class _ProcTaskInfo(ctypes.Structure):
    _fields_ = [
        ("virtual_size", ctypes.c_uint64),
        ("resident_size", ctypes.c_uint64),
        ("total_user", ctypes.c_uint64),
        ("total_system", ctypes.c_uint64),
        ("threads_user", ctypes.c_uint64),
        ("threads_system", ctypes.c_uint64),
        ("policy", ctypes.c_int32),
        ("faults", ctypes.c_int32),
        ("pageins", ctypes.c_int32),
        ("cow_faults", ctypes.c_int32),
        ("messages_sent", ctypes.c_int32),
        ("messages_received", ctypes.c_int32),
        ("syscalls_mach", ctypes.c_int32),
        ("syscalls_unix", ctypes.c_int32),
        ("context_switches", ctypes.c_int32),
        ("thread_count", ctypes.c_int32),
        ("running_thread_count", ctypes.c_int32),
        ("priority", ctypes.c_int32),
    ]


def _darwin_task_info(pid: int) -> dict[str, int] | None:
    """Read byte-accurate task memory and fault counters through libproc."""

    if sys.platform != "darwin":
        return None
    global _DARWIN_PROC_PIDINFO
    if _DARWIN_PROC_PIDINFO is None:
        library = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
        function = library.proc_pidinfo
        function.argtypes = (
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint64,
            ctypes.c_void_p,
            ctypes.c_int,
        )
        function.restype = ctypes.c_int
        _DARWIN_PROC_PIDINFO = function
    function = _DARWIN_PROC_PIDINFO
    info = _ProcTaskInfo()
    returned = int(
        function(
            int(pid),
            4,  # PROC_PIDTASKINFO
            0,
            ctypes.byref(info),
            ctypes.sizeof(info),
        )
    )
    if returned != ctypes.sizeof(info):
        return None
    return {
        "current_rss_bytes": int(info.resident_size),
        "current_vms_bytes": int(info.virtual_size),
        "process_faults": int(info.faults),
        "process_pageins": int(info.pageins),
        "process_cow_faults": int(info.cow_faults),
    }


def _finite_float(value: Any) -> float | None:
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None
    return converted if converted == converted else None


def current_process_memory_bytes(pid: int | None = None) -> tuple[int, int]:
    """Return current RSS and VMS, preferring Darwin ``libproc``."""

    resolved_pid = os.getpid() if pid is None else int(pid)
    if resolved_pid <= 0:
        raise ValueError("pid must be positive")
    task_info = _darwin_task_info(resolved_pid)
    if task_info is not None:
        return (
            task_info["current_rss_bytes"],
            task_info["current_vms_bytes"],
        )
    output = subprocess.check_output(
        (
            "/bin/ps",
            "-o",
            "rss=",
            "-o",
            "vsz=",
            "-p",
            str(resolved_pid),
        ),
        text=True,
    ).strip()
    fields = output.split()
    if len(fields) != 2:
        raise RuntimeError(f"cannot parse ps RSS/VMS output: {output!r}")
    rss_kib, vms_kib = (int(value) for value in fields)
    if rss_kib < 0 or vms_kib < 0:
        raise RuntimeError("ps returned a negative process-memory value")
    return rss_kib * 1024, vms_kib * 1024


def peak_rss_bytes() -> int:
    """Return process peak RSS with platform-specific unit normalization."""

    raw = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if raw < 0:
        raise RuntimeError("getrusage returned a negative peak RSS")
    return raw if sys.platform == "darwin" else raw * 1024


def system_memory_free_percent() -> float:
    """Return macOS system-wide free-memory percentage."""

    output = subprocess.check_output(
        ("/usr/bin/memory_pressure", "-Q"),
        text=True,
        stderr=subprocess.STDOUT,
    )
    match = re.search(
        r"System-wide memory free percentage:\s*([0-9.]+)%",
        output,
    )
    if match is None:
        raise RuntimeError("cannot parse memory_pressure -Q output")
    value = float(match.group(1))
    if not 0.0 <= value <= 100.0:
        raise RuntimeError("system free-memory percentage is out of range")
    return value


class MemorySampler:
    """Collect JSON-scalar process-memory observations in acquisition order."""

    def __init__(
        self,
        *,
        run_id: str,
        particle_count: int,
        row_sink: Callable[[Mapping[str, Any]], None] | None = None,
        retain_rows: bool = True,
    ) -> None:
        if not run_id:
            raise ValueError("run_id must be nonempty")
        if particle_count < 0:
            raise ValueError("particle_count must be nonnegative")
        if not tracemalloc.is_tracing():
            tracemalloc.start()
        self.run_id = str(run_id)
        self.particle_count = int(particle_count)
        self.started_at = time.perf_counter()
        self.row_sink = row_sink
        self.retain_rows = bool(retain_rows)
        self.rows: list[dict[str, Any]] = []
        self.sample_count = 0
        self.latest_row: dict[str, Any] | None = None
        self.low_system_memory_sample_streak = 0

    def sample(
        self,
        *,
        phase: str,
        step: int | None,
        edge_count: int | None,
        step_wall_seconds: float | None = None,
        tensor_inventory: Mapping[str, Any] | None = None,
        retention: Mapping[str, Any] | None = None,
        include_system_pressure: bool = False,
        note: str = "",
    ) -> dict[str, Any]:
        """Append one measurement; current and peak RSS stay distinct."""

        pid = os.getpid()
        task_info = _darwin_task_info(pid)
        if task_info is None:
            rss_bytes, vms_bytes = current_process_memory_bytes(pid)
        else:
            rss_bytes = task_info["current_rss_bytes"]
            vms_bytes = task_info["current_vms_bytes"]
        usage = resource.getrusage(resource.RUSAGE_SELF)
        traced_current, traced_peak = tracemalloc.get_traced_memory()
        inventory = {} if tensor_inventory is None else dict(tensor_inventory)
        gc_count = inventory.get("gc_tracked_object_count")
        if gc_count is None:
            objects = gc.get_objects()
            gc_count = len(objects)
            del objects
        row: dict[str, Any] = {
            "schema_version": MEMORY_SAMPLE_SCHEMA_VERSION,
            "run_id": self.run_id,
            "pid": pid,
            "sample_index": self.sample_count,
            "phase": str(phase),
            "step": None if step is None else int(step),
            "elapsed_seconds": time.perf_counter() - self.started_at,
            "current_rss_bytes": int(rss_bytes),
            "current_vms_bytes": int(vms_bytes),
            "peak_rss_bytes": int(peak_rss_bytes()),
            "minor_page_faults": int(getattr(usage, "ru_minflt", 0)),
            "major_page_faults": int(getattr(usage, "ru_majflt", 0)),
            "process_faults": (
                None if task_info is None else task_info["process_faults"]
            ),
            "process_pageins": (
                None if task_info is None else task_info["process_pageins"]
            ),
            "process_cow_faults": (
                None if task_info is None else task_info["process_cow_faults"]
            ),
            "tracemalloc_current_bytes": int(traced_current),
            "tracemalloc_peak_bytes": int(traced_peak),
            "tracemalloc_internal_bytes": int(
                tracemalloc.get_tracemalloc_memory()
            ),
            "gc_tracked_object_count": int(gc_count),
            "live_tensor_count": inventory.get("live_tensor_count"),
            "live_tensor_logical_bytes": inventory.get(
                "live_tensor_logical_bytes"
            ),
            "live_tensor_unique_storage_bytes": inventory.get(
                "live_tensor_unique_storage_bytes"
            ),
            "live_tensor_requires_grad_count": inventory.get(
                "live_tensor_requires_grad_count"
            ),
            "live_tensor_grad_fn_count": inventory.get(
                "live_tensor_grad_fn_count"
            ),
            "tensor_inventory_error_count": inventory.get(
                "tensor_inventory_error_count"
            ),
            "particle_count": self.particle_count,
            "edge_count": None if edge_count is None else int(edge_count),
            "step_wall_seconds": _finite_float(step_wall_seconds),
            "system_memory_free_percent": (
                system_memory_free_percent()
                if include_system_pressure
                else None
            ),
            "note": str(note),
        }
        if retention is not None:
            for key, value in retention.items():
                row[f"retention_{key}"] = value
        if self.row_sink is not None:
            self.row_sink(row)
        if self.retain_rows:
            self.rows.append(row)
        self.latest_row = row
        self.sample_count += 1
        return row


def process_exists(pid: int) -> bool:
    """Return whether ``pid`` is still visible to the operating system."""

    completed = subprocess.run(
        ("/bin/ps", "-p", str(int(pid)), "-o", "pid="),
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.returncode == 0 and bool(completed.stdout.strip())
