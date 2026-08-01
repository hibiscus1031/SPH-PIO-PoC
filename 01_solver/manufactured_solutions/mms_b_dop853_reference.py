"""Independent SciPy DOP853 particle trajectory reference for MMS-B."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from scipy.integrate import solve_ivp
import torch

from manufactured_solutions.governing_equations import MMSParameters, PARAMETERS
from manufactured_solutions.mms_b_deforming_vortex import velocity


def parameter_hash(parameters: MMSParameters = PARAMETERS) -> str:
    encoded = json.dumps(asdict(parameters), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def integrate_reference(
    initial_positions: torch.Tensor,
    sample_times: tuple[float, ...] | list[float],
    *,
    rtol: float = 1.0e-12,
    atol: float = 1.0e-14,
    max_step: float = 1.25e-3,
    parameters: MMSParameters = PARAMETERS,
) -> np.ndarray:
    """Integrate continuous unwrapped coordinates; wrap only inside the RHS."""

    if initial_positions.dtype != torch.float64 or initial_positions.device.type != "cpu":
        raise ValueError("initial_positions must use float64 on CPU")
    times = np.asarray(sample_times, dtype=np.float64)
    if times.ndim != 1 or len(times) == 0 or times[0] != 0.0 or np.any(np.diff(times) <= 0.0):
        raise ValueError("sample_times must start at zero and increase strictly")
    shape = tuple(initial_positions.shape)
    initial = initial_positions.detach().numpy().reshape(-1).copy()
    minimum = parameters.domain_minimum
    extent = parameters.domain_maximum - parameters.domain_minimum

    def rhs(time: float, flattened: np.ndarray) -> np.ndarray:
        unwrapped = flattened.reshape(shape)
        wrapped = np.remainder(unwrapped - minimum, extent) + minimum
        tensor = torch.from_numpy(wrapped)
        with torch.no_grad():
            result = velocity(tensor, time, parameters)
        return result.numpy().reshape(-1)

    solution = solve_ivp(
        rhs,
        (0.0, float(times[-1])),
        initial,
        method="DOP853",
        t_eval=times,
        rtol=rtol,
        atol=atol,
        max_step=max_step,
    )
    if not solution.success:
        raise RuntimeError(solution.message)
    result = solution.y.T.reshape((len(times),) + shape)
    if not np.isfinite(result).all():
        raise FloatingPointError("nonfinite DOP853 reference")
    result[0] = initial_positions.detach().numpy()
    return result


def sensitivity_bundle(
    initial_positions: torch.Tensor,
    sample_times: tuple[float, ...] | list[float],
    *,
    max_step: float = 1.25e-3,
    parameters: MMSParameters = PARAMETERS,
) -> dict[str, Any]:
    baseline = integrate_reference(
        initial_positions, sample_times, rtol=1e-12, atol=1e-14,
        max_step=max_step, parameters=parameters,
    )
    tighter = integrate_reference(
        initial_positions, sample_times, rtol=1e-13, atol=1e-15,
        max_step=max_step, parameters=parameters,
    )
    half_step = integrate_reference(
        initial_positions, sample_times, rtol=1e-12, atol=1e-14,
        max_step=0.5 * max_step, parameters=parameters,
    )
    return {
        "baseline": baseline,
        "tighter": tighter,
        "half_max_step": half_step,
        "baseline_tighter_linf": float(np.max(np.abs(baseline - tighter))),
        "baseline_half_max_step_linf": float(np.max(np.abs(baseline - half_step))),
        "parameter_sha256": parameter_hash(parameters),
        "integrator": "scipy.integrate.solve_ivp:DOP853",
        "baseline_rtol": 1e-12,
        "baseline_atol": 1e-14,
        "tighter_rtol": 1e-13,
        "tighter_atol": 1e-15,
        "maximum_step": max_step,
        "half_maximum_step": 0.5 * max_step,
    }


def save_reference(path: Path, bundle: dict[str, Any], *, code_commit: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        baseline=bundle["baseline"],
        tighter=bundle["tighter"],
        half_max_step=bundle["half_max_step"],
        parameter_sha256=np.asarray(bundle["parameter_sha256"]),
        integrator=np.asarray(bundle["integrator"]),
        baseline_rtol=np.asarray(bundle["baseline_rtol"]),
        baseline_atol=np.asarray(bundle["baseline_atol"]),
        tighter_rtol=np.asarray(bundle["tighter_rtol"]),
        tighter_atol=np.asarray(bundle["tighter_atol"]),
        maximum_step=np.asarray(bundle["maximum_step"]),
        half_maximum_step=np.asarray(bundle["half_maximum_step"]),
        baseline_tighter_linf=np.asarray(bundle["baseline_tighter_linf"]),
        baseline_half_max_step_linf=np.asarray(bundle["baseline_half_max_step_linf"]),
        code_commit=np.asarray(code_commit),
    )
