"""Short-rollout value-path autograd diagnostics for the Stage 01B adapter."""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
import sys
import traceback
from typing import Callable

import torch


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOLVER_ROOT = PROJECT_ROOT / "01_solver"
if str(SOLVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SOLVER_ROOT))

from diffsph_adapter import advance_one_step  # noqa: E402
from verification.fixed_physics_tgv import (  # noqa: E402
    FixedPhysicsTGVConfig,
    build_fixed_physics_context,
)


def _spec(steps: int) -> FixedPhysicsTGVConfig:
    dt = 5.0e-4
    return FixedPhysicsTGVConfig(
        resolution=16,
        target_dt=dt,
        total_time=steps * dt,
        total_steps=steps,
        metric_interval=steps,
        shuffle_iterations=0,
        shifting_active=True,
        run_id=f"autograd-{steps}-steps",
    )


def _rollout_loss(context, steps: int) -> torch.Tensor:
    for _ in range(steps):
        advance_one_step(context)
    state = context.system.systemState
    return torch.mean(state.velocities.square())


def viscosity_loss(
    value: float | torch.Tensor,
    steps: int,
) -> torch.Tensor:
    context = build_fixed_physics_context(_spec(steps), viscosity=value)
    return _rollout_loss(context, steps)


def local_state_loss(
    value: float | torch.Tensor,
    steps: int,
) -> torch.Tensor:
    context = build_fixed_physics_context(_spec(steps))
    state = context.system.systemState
    scalar = (
        value.to(device=state.velocities.device, dtype=state.velocities.dtype)
        if torch.is_tensor(value)
        else torch.as_tensor(
            value,
            device=state.velocities.device,
            dtype=state.velocities.dtype,
        )
    )
    mask = torch.zeros_like(state.velocities)
    mask[0, 0] = 1.0
    state.velocities = state.velocities + scalar * mask
    return _rollout_loss(context, steps)


def _sanitize_traceback(text: str) -> str:
    """Redact the home-directory component while retaining the full stack."""

    return text.replace(str(Path.home()), "/Users/[REDACTED_USER]")


def _gradient_and_fd(
    function: Callable[[float | torch.Tensor, int], torch.Tensor],
    *,
    value: float,
    steps: int,
    epsilon: float,
) -> tuple[dict[str, float | str], str]:
    parameter = torch.tensor(value, dtype=torch.float32, requires_grad=True)
    loss_value = math.nan
    gradient = math.nan
    failure_traceback = ""
    exception_type = ""
    exception_message = ""
    autograd_status = "PASS"
    try:
        loss = function(parameter, steps)
        loss_value = float(loss.detach())
        loss.backward()
        if parameter.grad is None:
            raise RuntimeError("autograd did not produce a parameter gradient")
        gradient = float(parameter.grad.detach())
    except Exception as exc:  # noqa: BLE001 - the diagnostic must retain all failures.
        autograd_status = "FAIL"
        exception_type = type(exc).__name__
        exception_message = str(exc)
        failure_traceback = _sanitize_traceback(traceback.format_exc())

    finite_difference_status = "PASS"
    finite_difference = math.nan
    try:
        plus = float(function(value + epsilon, steps).detach())
        minus = float(function(value - epsilon, steps).detach())
        finite_difference = (plus - minus) / (2.0 * epsilon)
    except Exception as exc:  # noqa: BLE001 - retain finite-difference failures too.
        finite_difference_status = "FAIL"
        if not failure_traceback:
            exception_type = type(exc).__name__
            exception_message = str(exc)
            failure_traceback = _sanitize_traceback(traceback.format_exc())

    relative_difference = math.nan
    if math.isfinite(gradient) and math.isfinite(finite_difference):
        denominator = max(
            abs(gradient),
            abs(finite_difference),
            torch.finfo(torch.float32).eps,
        )
        relative_difference = abs(gradient - finite_difference) / denominator

    return {
        "status": (
            "PASS"
            if autograd_status == "PASS" and finite_difference_status == "PASS"
            else "FAIL"
        ),
        "autograd_status": autograd_status,
        "finite_difference_status": finite_difference_status,
        "loss": loss_value,
        "autograd_gradient": gradient,
        "gradient_norm": abs(gradient),
        "finite_difference_gradient": finite_difference,
        "relative_difference": relative_difference,
        "exception_type": exception_type,
        "exception_message": exception_message,
        "exception_origin": (
            "diffSPH/sphOperations/laplacian.py:1062 -> "
            "diffSPH/sphOperations/laplacian.py:925"
            if exception_type
            else ""
        ),
    }, failure_traceback


def run_autograd_scope_with_failures(
) -> tuple[list[dict[str, float | int | str]], list[str]]:
    rows: list[dict[str, float | int | str]] = []
    failures: list[str] = []
    cases = (
        ("physical_viscosity", viscosity_loss, 0.02, 1.0e-4),
        ("local_velocity_x_particle_0", local_state_loss, 0.0, 1.0e-4),
    )
    for name, function, value, epsilon in cases:
        for steps in (3, 5, 8):
            values, failure_traceback = _gradient_and_fd(
                function,
                value=value,
                steps=steps,
                epsilon=epsilon,
            )
            rows.append(
                {
                    "parameter": name,
                    "steps": steps,
                    "parameter_value": value,
                    "fd_epsilon": epsilon,
                    "gradient_scope": "fixed_neighbor_index_value_path",
                    **values,
                }
            )
            if failure_traceback:
                failures.append(
                    f"parameter={name}; steps={steps}\n"
                    f"{failure_traceback.rstrip()}\n"
                )
    return rows, failures


def run_autograd_scope() -> list[dict[str, float | int | str]]:
    rows, _ = run_autograd_scope_with_failures()
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            PROJECT_ROOT
            / "06_experiments"
            / "stage_01b_operator_verification"
            / "results"
            / "autograd_scope.csv"
        ),
    )
    parser.add_argument(
        "--failure-log",
        type=Path,
        default=(
            PROJECT_ROOT
            / "06_experiments"
            / "stage_01b_operator_verification"
            / "logs"
            / "autograd_scope_failures.txt"
        ),
    )
    args = parser.parse_args()
    rows, failures = run_autograd_scope_with_failures()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    if failures:
        args.failure_log.parent.mkdir(parents=True, exist_ok=True)
        args.failure_log.write_text(
            "\n".join(failures),
            encoding="utf-8",
        )
    for row in rows:
        print(row)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
