"""Fixed-topology, one-step autograd plumbing only (no finite differences)."""

from __future__ import annotations

from dataclasses import replace
import hashlib

import torch
from torch import nn

from baseline_d0.state import DynamicParticleState, eos_pressure
from rk2_core.solver import DynamicHybridRK2Solver
from temporal_history.history import TemporalHistoryState


def _gradient_hash(value: torch.Tensor) -> str:
    array = value.detach().contiguous().cpu().numpy()
    return "sha256:" + hashlib.sha256(str(value.dtype).encode("ascii") + array.tobytes()).hexdigest()


def _run_once(
    *,
    arm: str,
    model: nn.Module,
    family_id: str,
    dt: float,
    base_state: DynamicParticleState,
) -> dict[str, torch.Tensor | bool]:
    velocity = base_state.velocity.detach().clone().requires_grad_(True)
    density = base_state.density.detach().clone().requires_grad_(True)
    state = replace(base_state, velocity=velocity, density=density, pressure=eos_pressure(density))
    solver = DynamicHybridRK2Solver(
        arm=arm,
        family_id=family_id,
        dt=dt,
        model=model,
        correction_enabled=True,
        zero_head=False,
    )
    initialized = solver.initialize_history(state) if arm in {"D2", "D3"} else None
    history: TemporalHistoryState | None = initialized
    extra_name: str | None = None
    extra_leaf: torch.Tensor | None = None
    if arm == "D2":
        assert initialized is not None
        extra_name = "initial_hidden"
        extra_leaf = initialized.accepted_hidden.detach().clone().requires_grad_(True)
        history = replace(initialized, accepted_hidden=extra_leaf)
    elif arm == "D3":
        assert initialized is not None
        extra_name = "historical_token"
        extra_leaf = initialized.accepted_tokens.detach().clone().requires_grad_(True)
        history = replace(initialized, accepted_tokens=extra_leaf)
    accepted, _, record = solver.step(state, history)
    particle_weight = torch.linspace(0.7, 1.3, accepted.particle_count, dtype=torch.float64)
    vector_weight = torch.stack((particle_weight, particle_weight.flip(0)), dim=-1)
    objective = (
        (accepted.velocity * vector_weight).sum()
        + 0.31 * (accepted.x_unwrapped * vector_weight.flip(1)).sum()
        + 0.17 * (accepted.density * particle_weight.square()).sum()
    )
    parameter = model.pair_head.output.weight
    names = ["parameter", "initial_velocity", "initial_density"]
    leaves: list[torch.Tensor] = [parameter, velocity, density]
    if extra_leaf is not None and extra_name is not None:
        names.append(extra_name)
        leaves.append(extra_leaf)
    if arm == "D3":
        names.append("attention_logit_parameter")
        leaves.append(model.temporal.layers[0].self_attn.in_proj_weight)
    gradients = torch.autograd.grad(objective, leaves, allow_unused=True, retain_graph=False, create_graph=False)
    result: dict[str, torch.Tensor | bool] = {
        name: torch.zeros(1, dtype=torch.float64) if gradient is None else gradient.detach().clone()
        for name, gradient in zip(names, gradients)
    }
    result["edge_indices_require_grad"] = bool(record.start_graph.row.requires_grad or record.start_graph.col.requires_grad)
    return result


def audit_one_step_autograd(
    *,
    arm: str,
    model: nn.Module,
    family_id: str,
    dt: float,
    state: DynamicParticleState,
) -> dict[str, object]:
    first = _run_once(arm=arm, model=model, family_id=family_id, dt=dt, base_state=state)
    second = _run_once(arm=arm, model=model, family_id=family_id, dt=dt, base_state=state)
    checks: dict[str, dict[str, object]] = {}
    for name, value in first.items():
        if name == "edge_indices_require_grad":
            continue
        assert torch.is_tensor(value)
        repeated = second[name]
        assert torch.is_tensor(repeated)
        norm = float(torch.linalg.vector_norm(value.reshape(-1)))
        checks[name] = {
            "finite": bool(torch.isfinite(value).all()),
            "nonzero": norm > 1.0e-18,
            "norm": norm,
            "deterministic_repeat": torch.equal(value, repeated),
            "gradient_hash": _gradient_hash(value),
        }
    gates = {
        "all_gradients_finite": all(item["finite"] for item in checks.values()),
        "all_expected_gradients_nonzero": all(item["nonzero"] for item in checks.values()),
        "repeat_deterministic": all(item["deterministic_repeat"] for item in checks.values()),
        "no_edge_index_gradient": not bool(first["edge_indices_require_grad"]),
        "one_step_only": True,
        "finite_difference_executed": False,
        "optimizer_object_created": False,
        "parameter_updated": False,
    }
    return {
        "arm": arm,
        "family_id": family_id,
        "particle_count": state.particle_count,
        "checks": checks,
        "gates": gates,
        "pass": all(value if key not in {"finite_difference_executed", "optimizer_object_created", "parameter_updated"} else not value for key, value in gates.items()),
    }

