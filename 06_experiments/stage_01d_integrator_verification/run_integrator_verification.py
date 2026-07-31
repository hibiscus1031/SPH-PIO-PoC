"""Run independent scalar and coupled-ODE order studies for Stage 01D."""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
from pathlib import Path
import subprocess
import sys
from typing import Callable

import torch


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOLVER_ROOT = PROJECT_ROOT / "01_solver"
if str(SOLVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SOLVER_ROOT))

from dynamic_solver.integrator import integrate_fixed_steps  # noqa: E402


TIME_STEPS = (0.1, 0.05, 0.025, 0.0125)
FINAL_TIME = 1.0
PREREGISTRATION_PATH = (
    PROJECT_ROOT
    / "06_experiments"
    / "stage_01d_fixed_physics_tgv"
    / "configs"
    / "preregistered_primary_tgv.yml"
)


def scalar_decay_rhs(
    time: torch.Tensor,
    state: torch.Tensor,
    decay_rate: float,
) -> torch.Tensor:
    del time
    return -decay_rate * state


def coupled_damped_oscillator_rhs(
    time: torch.Tensor,
    state: torch.Tensor,
) -> torch.Tensor:
    del time
    y0, y1 = state.unbind()
    return torch.stack(
        (
            y1,
            -2.0 * y0 - 0.4 * y1,
        )
    )


def coupled_damped_oscillator_exact(
    time: float,
    *,
    dtype: torch.dtype,
    device: torch.device,
) -> torch.Tensor:
    """Exact solution for y0'=y1, y1'=-2*y0-0.4*y1, y(0)=[1,0]."""

    damped_frequency = 1.4
    angle = damped_frequency * time
    envelope = math.exp(-0.2 * time)
    return torch.tensor(
        [
            envelope
            * (
                math.cos(angle)
                + (1.0 / 7.0) * math.sin(angle)
            ),
            -(10.0 / 7.0) * envelope * math.sin(angle),
        ],
        dtype=dtype,
        device=device,
    )


def _order_study(
    *,
    problem: str,
    initial: torch.Tensor,
    rhs: Callable[..., torch.Tensor],
    rhs_args: tuple[float, ...],
    exact: torch.Tensor,
) -> list[dict[str, float | str]]:
    rows: list[dict[str, float | str]] = []
    previous_error: float | None = None
    for dt in TIME_STEPS:
        steps = int(round(FINAL_TIME / dt))
        if not math.isclose(
            steps * dt,
            FINAL_TIME,
            rel_tol=0.0,
            abs_tol=1.0e-14,
        ):
            raise ValueError("final time must be an integer multiple of dt")
        numerical = integrate_fixed_steps(
            rhs,
            initial,
            dt=dt,
            steps=steps,
            args=rhs_args,
        )
        error = float(torch.linalg.vector_norm(numerical - exact))
        observed_order = (
            math.log(previous_error / error, 2.0)
            if previous_error is not None
            else ""
        )
        flattened = numerical.reshape(-1)
        exact_flattened = exact.reshape(-1)
        rows.append(
            {
                "problem": problem,
                "method": "explicit_midpoint_rk2",
                "dt": dt,
                "steps": steps,
                "numerical_0": float(flattened[0]),
                "numerical_1": (
                    float(flattened[1])
                    if flattened.numel() > 1
                    else ""
                ),
                "exact_0": float(exact_flattened[0]),
                "exact_1": (
                    float(exact_flattened[1])
                    if exact_flattened.numel() > 1
                    else ""
                ),
                "error_L2": error,
                "observed_order": observed_order,
            }
        )
        previous_error = error
    return rows


def run_verification() -> list[dict[str, float | str]]:
    dtype = torch.float64
    decay_rate = 1.3
    scalar_initial = torch.tensor(1.0, dtype=dtype)
    scalar_exact = torch.tensor(
        math.exp(-decay_rate * FINAL_TIME),
        dtype=dtype,
    )
    rows = _order_study(
        problem="scalar_decay",
        initial=scalar_initial,
        rhs=scalar_decay_rhs,
        rhs_args=(decay_rate,),
        exact=scalar_exact,
    )

    coupled_initial = torch.tensor([1.0, 0.0], dtype=dtype)
    coupled_reference = coupled_damped_oscillator_exact(
        FINAL_TIME,
        dtype=dtype,
        device=coupled_initial.device,
    )
    rows.extend(
        _order_study(
            problem="coupled_damped_oscillator",
            initial=coupled_initial,
            rhs=coupled_damped_oscillator_rhs,
            rhs_args=(),
            exact=coupled_reference,
        )
    )
    git_hash = subprocess.check_output(
        ("git", "rev-parse", "HEAD"),
        cwd=PROJECT_ROOT,
        text=True,
    ).strip()
    config_hash = hashlib.sha256(
        PREREGISTRATION_PATH.read_bytes()
    ).hexdigest()
    for row in rows:
        row["git_hash"] = git_hash
        row["config_sha256"] = config_hash
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional CSV path; omit to print CSV to stdout only.",
    )
    args = parser.parse_args()
    rows = run_verification()
    fieldnames = list(rows[0])
    if args.output is None:
        writer = csv.DictWriter(
            sys.stdout,
            fieldnames=fieldnames,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    else:
        if args.output.exists():
            raise FileExistsError(
                f"refusing to overwrite integrator evidence: {args.output}"
            )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_name(args.output.name + ".tmp")
        with temporary.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=fieldnames,
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerows(rows)
        temporary.replace(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
