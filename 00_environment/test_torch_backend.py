#!/usr/bin/env python3
"""Minimal CPU/MPS capability checks for SPH-PIO-PoC.

Each check emits PASS, FAIL, or SKIP.  Failures retain their full traceback so
the stage report is evidence-based rather than inferred from hardware specs.
"""

from __future__ import annotations

import platform
import traceback
from typing import Callable

import torch


def emit(status: str, name: str, detail: str = "") -> None:
    print(f"{status:<4} | {name}" + (f" | {detail}" if detail else ""), flush=True)


def run(name: str, fn: Callable[[], str], *, device: str | None = None) -> None:
    label = f"{name} [{device}]" if device else name
    if device == "mps" and not torch.backends.mps.is_available():
        emit("SKIP", label, "MPS unavailable")
        return
    try:
        detail = fn()
        emit("PASS", label, detail)
    except Exception:
        emit("FAIL", label)
        print(traceback.format_exc(), flush=True)


def sync(device: str) -> None:
    if device == "mps":
        torch.mps.synchronize()


def basic_ops(device: str) -> str:
    x = torch.tensor([1.0, 2.0, 3.0], device=device)
    y = torch.tensor([3.0, 2.0, 1.0], device=device)
    got = ((x + y) - y) * 2
    assert torch.equal(got.cpu(), torch.tensor([2.0, 4.0, 6.0]))
    sync(device)
    return "add/sub/mul correct"


def autograd(device: str) -> str:
    x = torch.tensor([1.0, -2.0, 3.0], device=device, requires_grad=True)
    loss = (x.square() * 0.5).sum()
    loss.backward()
    assert torch.allclose(x.grad.cpu(), torch.tensor([1.0, -2.0, 3.0]))
    sync(device)
    return "gradient correct"


def linear(device: str) -> str:
    torch.manual_seed(7)
    model = torch.nn.Linear(16, 8, device=device)
    x = torch.randn(12, 16, device=device)
    loss = model(x).square().mean()
    loss.backward()
    assert model.weight.grad is not None and torch.isfinite(model.weight.grad).all()
    sync(device)
    return "forward/backward finite"


def attention(device: str) -> str:
    torch.manual_seed(8)
    module = torch.nn.MultiheadAttention(32, 4, batch_first=True, device=device)
    x = torch.randn(3, 12, 32, device=device, requires_grad=True)
    out, weights = module(x, x, x, need_weights=True)
    (out.square().mean() + weights.mean()).backward()
    assert x.grad is not None and torch.isfinite(x.grad).all()
    sync(device)
    return "forward/backward finite"


def indexed_ops(device: str) -> str:
    values = torch.arange(24, dtype=torch.float32, device=device).reshape(6, 4)
    idx = torch.tensor([5, 2, 2, 0], dtype=torch.long, device=device)
    selected = torch.index_select(values, 0, idx)
    target = torch.tensor([0, 1, 1, 2], device=device)
    acc = torch.zeros(3, 4, device=device).index_add_(0, target, selected)
    scattered = torch.zeros(3, 4, device=device).scatter_add_(0, target[:, None].expand_as(selected), selected)
    assert selected.shape == (4, 4) and torch.equal(acc, scattered) and torch.isfinite(acc).all()
    sync(device)
    return "scatter_add/index_select/index_add correct"


def distance_topk(device: str) -> str:
    torch.manual_seed(9)
    points = torch.randn(64, 3, device=device)
    distances = torch.cdist(points, points)
    vals, inds = torch.topk(distances, 5, dim=1, largest=False)
    assert vals.shape == (64, 5) and inds.shape == (64, 5) and torch.isfinite(vals).all()
    sync(device)
    return "cdist/topk correct"


def consistency() -> str:
    torch.manual_seed(10)
    x_cpu = torch.randn(64, 32, dtype=torch.float32)
    y_cpu = torch.randn(32, 16, dtype=torch.float32)
    cpu = (x_cpu @ y_cpu).relu()
    mps = (x_cpu.to("mps") @ y_cpu.to("mps")).relu().cpu()
    max_error = (cpu - mps).abs().max().item()
    assert torch.allclose(cpu, mps, rtol=1e-4, atol=1e-5), f"max_abs_error={max_error:.3e}"
    torch.mps.synchronize()
    return f"max_abs_error={max_error:.3e}"


def mps_memory() -> str:
    if not hasattr(torch, "mps"):
        return "torch.mps namespace absent"
    fields = []
    for attr in ("current_allocated_memory", "driver_allocated_memory", "recommended_max_memory"):
        fn = getattr(torch.mps, attr, None)
        if callable(fn):
            fields.append(f"{attr}={fn()}")
    if not fields:
        return "no MPS memory accounting API in this torch version"
    return ", ".join(fields)


def main() -> None:
    print("SPH-PIO-PoC PyTorch backend test")
    print(f"python_platform={platform.platform()}")
    run("torch.__version__", lambda: torch.__version__)
    run("torch.backends.mps.is_built", lambda: str(torch.backends.mps.is_built()))
    run("torch.backends.mps.is_available", lambda: str(torch.backends.mps.is_available()))
    run("torch.mps.device_count", lambda: str(torch.mps.device_count()) if hasattr(torch.mps, "device_count") else "API unsupported")

    for device in ("cpu", "mps"):
        run("basic tensor arithmetic", lambda d=device: basic_ops(d), device=device)
        run("automatic differentiation", lambda d=device: autograd(d), device=device)
        run("Linear", lambda d=device: linear(d), device=device)
        run("MultiheadAttention", lambda d=device: attention(d), device=device)
        run("scatter/index_add/index_select", lambda d=device: indexed_ops(d), device=device)
        run("pairwise distance and topk", lambda d=device: distance_topk(d), device=device)

    run("float32 CPU/MPS consistency", consistency, device="mps")
    run("MPS memory accounting", mps_memory, device="mps")


if __name__ == "__main__":
    main()
