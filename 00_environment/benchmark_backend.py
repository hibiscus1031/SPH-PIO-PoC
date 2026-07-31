#!/usr/bin/env python3
"""Warm-up and repeated CPU/MPS microbenchmarks for the Stage 00 audit."""

from __future__ import annotations

import csv
import statistics
import sys
import time
from pathlib import Path

import torch


WARMUP = 3
REPEATS = 8


def sync(device: str) -> None:
    if device == "mps":
        torch.mps.synchronize()


def measure(device: str, operation: str, forward, backward) -> list[dict[str, object]]:
    for _ in range(WARMUP):
        backward(forward())
        sync(device)
    forward_times, backward_times = [], []
    for _ in range(REPEATS):
        sync(device)
        start = time.perf_counter()
        output = forward()
        sync(device)
        forward_times.append((time.perf_counter() - start) * 1000)
        start = time.perf_counter()
        backward(output)
        sync(device)
        backward_times.append((time.perf_counter() - start) * 1000)
    return [
        {"device": device, "operation": operation, "phase": "forward", "warmup_runs": WARMUP, "measured_runs": REPEATS, "mean_ms": statistics.mean(forward_times), "median_ms": statistics.median(forward_times), "min_ms": min(forward_times), "max_ms": max(forward_times)},
        {"device": device, "operation": operation, "phase": "backward", "warmup_runs": WARMUP, "measured_runs": REPEATS, "mean_ms": statistics.mean(backward_times), "median_ms": statistics.median(backward_times), "min_ms": min(backward_times), "max_ms": max(backward_times)},
    ]


def benchmark_device(device: str) -> list[dict[str, object]]:
    torch.manual_seed(42)
    rows: list[dict[str, object]] = []
    a = torch.randn(1024, 1024, device=device, requires_grad=True)
    b = torch.randn(1024, 1024, device=device, requires_grad=True)
    rows += measure(device, "matmul_1024x1024", lambda: a @ b, lambda y: (y.square().mean()).backward())

    features = torch.randn(1024, 32, device=device, requires_grad=True)
    neighbor_index = torch.randint(0, 1024, (1024, 32), device=device)
    rows += measure(device, "neighbor_aggregate_N1024_K32_C32", lambda: features[neighbor_index].mean(dim=1), lambda y: (y.square().mean()).backward())

    attention = torch.nn.MultiheadAttention(64, 4, batch_first=True, device=device)
    query = torch.randn(8, 64, 64, device=device, requires_grad=True)
    rows += measure(device, "multihead_attention_B8_L64_E64_H4", lambda: attention(query, query, query, need_weights=False)[0], lambda y: (y.square().mean()).backward())
    return rows


def main() -> None:
    out = Path(sys.argv[1])
    devices = ["cpu"] + (["mps"] if torch.backends.mps.is_available() else [])
    rows: list[dict[str, object]] = []
    for device in devices:
        try:
            rows += benchmark_device(device)
        except Exception as exc:
            rows.append({"device": device, "operation": "benchmark_setup", "phase": "FAIL", "warmup_runs": WARMUP, "measured_runs": REPEATS, "mean_ms": "", "median_ms": "", "min_ms": "", "max_ms": repr(exc)})
            print(f"FAIL [{device}]: {exc}", file=sys.stderr)
    fields = ["device", "operation", "phase", "warmup_runs", "measured_runs", "mean_ms", "median_ms", "min_ms", "max_ms"]
    with out.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()
