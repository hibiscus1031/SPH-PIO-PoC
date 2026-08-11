"""CPU-float64 parameter, timing, memory, graph and live-tensor audit."""

from __future__ import annotations

from dataclasses import replace
import gc
import os
from pathlib import Path
import time

import psutil
import torch

from baseline_d0.state import DynamicParticleState, eos_pressure
from contracts.model_factory import create_model, parameter_count
from graph_rebuild.graph import build_reciprocal_graph, graph_memory_bytes
from rk2_core.solver import DynamicHybridRK2Solver
from temporal_history.history import TemporalHistoryState


def _tensor_bytes(value: torch.Tensor) -> int:
    return value.numel() * value.element_size()


def history_memory_bytes(history: TemporalHistoryState | None) -> int:
    if history is None:
        return 0
    return sum(_tensor_bytes(value) for value in (history.accepted_tokens, history.accepted_hidden, history.accepted_times, history.material_labels))


def _live_tensor_count() -> int:
    count = 0
    for item in gc.get_objects():
        try:
            if torch.is_tensor(item):
                count += 1
        except Exception:
            continue
    return count


def regular_state(resolution: int) -> DynamicParticleState:
    axis = -1.0 + (torch.arange(resolution, dtype=torch.float64) + 0.5) * (2.0 / resolution)
    xx, yy = torch.meshgrid(axis, axis, indexing="ij")
    x = torch.stack((xx.reshape(-1), yy.reshape(-1)), dim=-1)
    velocity = torch.stack((0.01 * torch.sin(torch.pi * x[:, 1]), -0.01 * torch.sin(torch.pi * x[:, 0])), dim=-1)
    density = torch.ones(resolution**2, dtype=torch.float64)
    mass = torch.full_like(density, 4.0 / (resolution**2))
    support = torch.full_like(density, 2.6 * 2.0 / resolution)
    return DynamicParticleState(x, velocity, density, eos_pressure(density), mass, support, x.clone(), 0.0, 0)


def run_resource_audit(required_states: dict[int, DynamicParticleState], source_root: Path) -> dict[str, object]:
    process = psutil.Process(os.getpid())
    rss_start = process.memory_info().rss
    rows: list[dict[str, object]] = []
    peak_observed = rss_start
    for resolution in (8, 12, 16):
        base = required_states[resolution]
        for arm in ("D0", "D1", "D2", "D3"):
            model = create_model(arm, zero_head=(arm != "D0"))
            solver = DynamicHybridRK2Solver(
                arm=arm,
                family_id="DR3_OBLIQUE_SHEAR_A",
                dt=0.000390625,
                model=model,
                correction_enabled=arm != "D0",
                zero_head=arm != "D0",
            )
            with torch.no_grad():
                history = solver.initialize_history(base)
                graph = build_reciprocal_graph(base)
                before = time.perf_counter()
                if model is not None:
                    from tokenization.tokens import build_node_token
                    token = build_node_token(base, graph)
                    kwargs: dict[str, object] = {"stage": "start"}
                    if arm in {"D2", "D3"}:
                        kwargs["history"] = history
                    model.evaluate(token, base, graph, **kwargs)
                forward_seconds = time.perf_counter() - before
                before = time.perf_counter()
                state_after, history_after, record = solver.step(base, history)
                step_seconds = time.perf_counter() - before
            peak_observed = max(peak_observed, process.memory_info().rss)
            edge_count = record.start_graph.edge_count
            rows.append(
                {
                    "resolution": resolution,
                    "particle_count": resolution**2,
                    "arm": arm,
                    "parameter_count": parameter_count(model),
                    "forward_time_seconds": forward_seconds,
                    "rk2_step_time_seconds": step_seconds,
                    "history_memory_bytes": history_memory_bytes(history_after),
                    "graph_memory_bytes": graph_memory_bytes(record.start_graph),
                    "edge_count": edge_count,
                    "edge_shaped_intermediate_upper_bytes": edge_count * (100 + 32 + 2) * 8,
                    "graph_rebuild_count": solver.accounting.graph_rebuild_count,
                    "accepted_graph_materialization_count": solver.accounting.accepted_graph_materialization_count,
                    "finite_completion": bool(torch.isfinite(state_after.velocity).all()),
                }
            )

    audit_state = regular_state(32)
    audit_rows = []
    for zero_head in (True, False):
        model = create_model("D3", zero_head=zero_head)
        solver = DynamicHybridRK2Solver(
            arm="D3",
            family_id="DR3_OBLIQUE_SHEAR_A",
            dt=0.000390625,
            model=model,
            correction_enabled=True,
            zero_head=zero_head,
        )
        with torch.no_grad():
            history = solver.initialize_history(audit_state)
            before = time.perf_counter()
            final, history, record = solver.step(audit_state, history)
            elapsed = time.perf_counter() - before
        peak_observed = max(peak_observed, process.memory_info().rss)
        audit_rows.append(
            {
                "mode": "zero_head" if zero_head else "fixed_random_weight",
                "particle_count": 1024,
                "edge_count": record.start_graph.edge_count,
                "elapsed_seconds": elapsed,
                "graph_memory_bytes": graph_memory_bytes(record.start_graph),
                "history_memory_bytes": history_memory_bytes(history),
                "finite_completion": bool(torch.isfinite(final.velocity).all()),
                "reference_performance_metric_computed": False,
            }
        )

    model = create_model("D3", zero_head=True)
    solver = DynamicHybridRK2Solver(
        arm="D3",
        family_id="DR3_OBLIQUE_SHEAR_A",
        dt=0.000390625,
        model=model,
        correction_enabled=True,
        zero_head=True,
    )
    state = required_states[8]
    with torch.no_grad():
        history = solver.initialize_history(state)
        live_counts = []
        rss_counts = []
        for _ in range(8):
            state, history, _ = solver.step(state, history)
            gc.collect()
            live_counts.append(_live_tensor_count())
            rss_counts.append(process.memory_info().rss)
            peak_observed = max(peak_observed, rss_counts[-1])
    monotonic_retention = all(right > left for left, right in zip(live_counts, live_counts[1:])) and live_counts[-1] > live_counts[0]
    source_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in source_root.rglob("*.py")
        if path.resolve() != Path(__file__).resolve()
    )
    dense_patterns = ("torch.cdist(", "torch.ones((particle_count, particle_count", "torch.zeros((particle_count, particle_count", "torch.empty((particle_count, particle_count")
    stage03c_dense_pattern = any(pattern in source_text for pattern in dense_patterns)
    peak_delta = peak_observed - rss_start
    gates = {
        "parameter_count_le_150000": all(row["parameter_count"] <= 150000 for row in rows),
        "peak_rss_delta_le_1_5_GiB": peak_delta <= 1610612736,
        "finite_completion": all(row["finite_completion"] for row in rows) and all(row["finite_completion"] for row in audit_rows),
        "no_monotonic_live_tensor_retention": not monotonic_retention,
        "no_dense_N_by_N_allocation_in_stage03c": not stage03c_dense_pattern,
        "empirical_local_memory_form": all(row["graph_memory_bytes"] < 64 * 1024 * 1024 and row["history_memory_bytes"] < 64 * 1024 * 1024 for row in rows + audit_rows),
    }
    return {
        "formal_device": "cpu",
        "formal_dtype": "float64",
        "rows": rows,
        "audit_only_N32": audit_rows,
        "rss_start_bytes": rss_start,
        "peak_rss_observed_bytes": peak_observed,
        "peak_rss_delta_bytes": peak_delta,
        "repeated_8_step_rss_bytes": rss_counts,
        "repeated_8_step_live_tensor_counts": live_counts,
        "dense_pattern_scan_patterns": list(dense_patterns),
        "dense_pattern_found": stage03c_dense_pattern,
        "gates": gates,
        "pass": all(gates.values()),
        "MPS_used_for_hard_gate": False,
    }
