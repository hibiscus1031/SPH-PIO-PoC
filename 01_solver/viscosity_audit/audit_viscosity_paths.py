"""Probe the reachable DeltaSPH viscosity parameter path without modifying it.

This diagnostic intentionally exercises the exact installed diffSPH operator.
It does not run a convergence experiment and does not alter package files.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import inspect
import json
from pathlib import Path
import sys
from typing import Any

import torch


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOLVER_ROOT = PROJECT_ROOT / "01_solver"
if str(SOLVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SOLVER_ROOT))

from diffsph_adapter import TGVConfig, build_context  # noqa: E402


def _tensor_summary(value: torch.Tensor) -> dict[str, float]:
    detached = value.detach().cpu()
    return {
        "l2": float(torch.linalg.vector_norm(detached)),
        "linf": float(detached.abs().max()),
        "mean": float(detached.mean()),
    }


def run_probe(resolution: int = 16) -> dict[str, Any]:
    """Return evidence that config alpha is bypassed on the reachable path."""

    spec = TGVConfig(
        resolution=resolution,
        backend="cpu",
        total_time=5.0e-4,
        total_steps=1,
        shuffle_iterations=0,
        warmup_steps=0,
    )
    context = build_context(spec)

    # diffSPH has a sampling/particleShifting/deltaSPH circular dependency.
    # build_context intentionally follows the upstream example import order;
    # import these modules only after that sequence has completed.
    from diffSPH.modules import velocityDiffusion
    from diffSPH.neighborhood import SupportScheme

    particles = context.system.systemState
    from diffSPH.neighborhood import evaluateNeighborhood

    _, neighbors = evaluateNeighborhood(
        particles,
        context.config["domain"],
        context.config["kernel"],
        verletScale=context.config["neighborhood"]["verletScale"],
        mode=SupportScheme.SuperSymmetric,
        priorNeighborhood=None,
        computeHessian=context.config["neighborhood"]["computeHessian"],
        computeDkDh=context.config["neighborhood"]["computeDkDh"],
        only_j=context.config["neighborhood"]["only_j"],
    )
    fluid_neighborhood = neighbors.get("fluid")
    operator = velocityDiffusion.computeViscosity_deltaSPH_inviscid

    by_config: dict[str, torch.Tensor] = {}
    for alpha in (0.0, 0.01, 1.0):
        config = copy.deepcopy(context.config)
        config["diffusion"]["alpha"] = alpha
        by_config[f"{alpha:g}"] = operator(
            particles,
            config["kernel"],
            fluid_neighborhood,
            SupportScheme.Gather,
            config,
        ).detach()

    by_override: dict[str, torch.Tensor] = {}
    for alpha in (0.0, 0.01, 1.0):
        by_override[f"{alpha:g}"] = operator(
            particles,
            context.config["kernel"],
            fluid_neighborhood,
            SupportScheme.Gather,
            context.config,
            alphaOverride=alpha,
        ).detach()

    source_path = Path(inspect.getsourcefile(operator) or "")
    source_line = inspect.getsourcelines(operator)[1]
    source_bytes = source_path.read_bytes()

    baseline = by_config["0.01"]
    config_differences = {
        alpha: float((value - baseline).abs().max())
        for alpha, value in by_config.items()
    }
    override_differences = {
        alpha: float((value - by_override["0.01"]).abs().max())
        for alpha, value in by_override.items()
    }

    return {
        "probe": "reachable_delta_sph_viscosity_parameter_path",
        "resolution": resolution,
        "particle_count": resolution**2,
        "dtype": str(particles.positions.dtype),
        "device": str(particles.positions.device),
        "operator": operator.__name__,
        "operator_source": "src/diffSPH/modules/velocityDiffusion.py",
        "operator_source_start_line": source_line,
        "installed_source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "configured_alpha_max_abs_difference_from_0.01": config_differences,
        "configured_alpha_outputs_bitwise_equal": {
            alpha: bool(torch.equal(value, baseline))
            for alpha, value in by_config.items()
        },
        "alpha_override_max_abs_difference_from_0.01": override_differences,
        "alpha_override_output_summaries": {
            alpha: _tensor_summary(value)
            for alpha, value in by_override.items()
        },
        "alpha_override_zero_is_nonzero": bool(
            torch.count_nonzero(by_override["0"]) > 0
        ),
        "interpretation": {
            "config_alpha_reaches_operator": False,
            "alpha_override_reaches_operator": True,
            "zero_linear_alpha_eliminates_entire_operator": False,
            "reason_zero_override_remains_nonzero": (
                "compute_Pi retains its default quadratic coefficient C_q=2"
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resolution", type=int, default=16)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_probe(args.resolution)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
