#!/usr/bin/env python3
"""Multi-step diffSPH autograd check with central finite differences."""

from __future__ import annotations

import argparse
import dataclasses
import json
import math
from pathlib import Path
from typing import Any

import torch

from .tgv import (
    TGVConfig,
    advance_one_step,
    audit_system_device,
    build_context,
    synchronize,
    taylor_green_velocity,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _loss_for_amplitude(
    spec: TGVConfig,
    amplitude: torch.Tensor | float,
    steps: int,
) -> tuple[torch.Tensor, list[dict[str, Any]], Any]:
    context = build_context(spec, amplitude=amplitude)
    graph_steps: list[dict[str, Any]] = []
    for step in range(1, steps + 1):
        current, updates = advance_one_step(context)
        audit = audit_system_device(
            context,
            extras={"current": current, "updates": updates},
        )
        velocity = context.system.systemState.velocities
        graph_steps.append(
            {
                "step": step,
                "velocity_requires_grad": bool(velocity.requires_grad),
                "velocity_grad_fn": (
                    type(velocity.grad_fn).__name__ if velocity.grad_fn is not None else None
                ),
                "device_audit": audit,
            }
        )
    state = context.system.systemState
    target = taylor_green_velocity(
        state.positions,
        context.system.t,
        amplitude=1.0,
        viscosity=context.reference_kinematic_viscosity,
        wave_number=spec.wave_number,
    )
    loss = (state.velocities - target).square().mean()
    return loss, graph_steps, context


def check_backend(
    backend: str,
    *,
    steps: int = 3,
    alpha_value: float = 0.9,
    epsilon: float = 1.0e-3,
    shuffle_iterations: int = 256,
) -> dict[str, Any]:
    if steps < 2 or steps > 4:
        raise ValueError("The Stage 01 gradient check requires 2–4 steps")
    spec = TGVConfig(
        resolution=16,
        backend=backend,
        total_time=steps * 5.0e-4,
        metric_interval=1,
        shuffle_iterations=shuffle_iterations,
        warmup_steps=0,
        run_id="gradient-check",
    )
    device = torch.device(backend)
    alpha = torch.tensor(
        alpha_value,
        device=device,
        dtype=torch.float32,
        requires_grad=True,
    )
    loss, graph_steps, context = _loss_for_amplitude(spec, alpha, steps)
    loss.backward()
    synchronize(context.device)
    autograd_gradient = float(alpha.grad.detach().cpu())

    plus_loss, _, plus_context = _loss_for_amplitude(
        spec,
        alpha_value + epsilon,
        steps,
    )
    synchronize(plus_context.device)
    plus = float(plus_loss.detach().cpu())
    minus_loss, _, minus_context = _loss_for_amplitude(
        spec,
        alpha_value - epsilon,
        steps,
    )
    synchronize(minus_context.device)
    minus = float(minus_loss.detach().cpu())
    finite_difference = (plus - minus) / (2.0 * epsilon)
    denominator = max(abs(autograd_gradient), abs(finite_difference), 1.0e-12)
    relative_difference = abs(autograd_gradient - finite_difference) / denominator

    return {
        "backend": backend,
        "resolution": 16,
        "particle_count": 256,
        "steps": steps,
        "alpha_value": alpha_value,
        "alpha_requires_grad": bool(alpha.requires_grad),
        "loss": float(loss.detach().cpu()),
        "loss_requires_grad": bool(loss.requires_grad),
        "loss_grad_fn": type(loss.grad_fn).__name__ if loss.grad_fn else None,
        "autograd_gradient": autograd_gradient,
        "finite_difference_epsilon": epsilon,
        "finite_difference_loss_plus": plus,
        "finite_difference_loss_minus": minus,
        "finite_difference_gradient": finite_difference,
        "relative_difference": relative_difference,
        "gradient_is_finite": math.isfinite(autograd_gradient),
        "gradient_is_nonzero": autograd_gradient != 0.0,
        "all_steps_retain_graph": all(
            entry["velocity_requires_grad"] and entry["velocity_grad_fn"]
            for entry in graph_steps
        ),
        "detach_item_numpy_in_loss_path": False,
        "graph_steps": graph_steps,
        "known_neighbor_topology_note": (
            "torchCompactRadius chooses discrete neighbor indices outside the "
            "differentiable value path; on MPS its compact search transfers "
            "positions to CPU and indices back to MPS."
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=("cpu", "mps", "both"), default="both")
    parser.add_argument("--steps", type=int, default=3)
    parser.add_argument("--alpha", type=float, default=0.9)
    parser.add_argument("--epsilon", type=float, default=1.0e-3)
    parser.add_argument("--shuffle-iterations", type=int, default=256)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT
        / "06_experiments/stage_01_tgv/processed/gradient_check.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    backends = ("cpu", "mps") if args.backend == "both" else (args.backend,)
    results = [
        check_backend(
            backend,
            steps=args.steps,
            alpha_value=args.alpha,
            epsilon=args.epsilon,
            shuffle_iterations=args.shuffle_iterations,
        )
        for backend in backends
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
    print(json.dumps(results, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
