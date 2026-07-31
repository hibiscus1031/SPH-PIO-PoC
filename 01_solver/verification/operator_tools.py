"""Shared deterministic layouts and diffSPH operator-verification helpers."""

from __future__ import annotations

import hashlib
from typing import Any

import torch

from diffsph_adapter import wrap_periodic_positions
from verification.fixed_physics_tgv import (
    FixedPhysicsTGVConfig,
    build_fixed_physics_context,
)


LAYOUT_SEED = 20260801


def error_norms(
    numerical: torch.Tensor,
    exact: torch.Tensor,
) -> dict[str, float]:
    if numerical.shape != exact.shape:
        raise ValueError(
            f"shape mismatch: numerical={numerical.shape}, exact={exact.shape}"
        )
    error = (numerical - exact).reshape(-1)
    return {
        "l1": float(error.abs().mean().detach().cpu()),
        "l2": float(
            torch.sqrt(torch.mean(error.square())).detach().cpu()
        ),
        "linf": float(error.abs().max().detach().cpu()),
    }


def tensor_sha256(value: torch.Tensor) -> str:
    array = value.detach().contiguous().cpu().numpy()
    return hashlib.sha256(array.tobytes()).hexdigest()


def build_layout(
    resolution: int,
    jitter_fraction: float,
    *,
    seed: int = LAYOUT_SEED,
) -> tuple[Any, str]:
    if jitter_fraction not in (0.0, 0.05, 0.10):
        raise ValueError("jitter_fraction must be 0, 0.05, or 0.10")
    spec = FixedPhysicsTGVConfig(
        resolution=resolution,
        total_time=1.0e-3,
        total_steps=1,
        target_dt=1.0e-3,
        shuffle_iterations=0,
        shifting_active=False,
        run_id=f"operators-jitter-{jitter_fraction:.2f}",
    )
    context = build_fixed_physics_context(spec)
    state = context.system.systemState
    if jitter_fraction:
        generator = torch.Generator(device="cpu")
        generator.manual_seed(seed + int(jitter_fraction * 100))
        perturbation = (
            2.0
            * torch.rand(
                state.positions.shape,
                generator=generator,
                device="cpu",
                dtype=state.positions.dtype,
            )
            - 1.0
        )
        perturbation = perturbation.to(state.positions.device)
        dx = spec.domain_length / resolution
        positions = state.positions + jitter_fraction * dx * perturbation
        state.positions = wrap_periodic_positions(
            positions,
            context.config["domain"].min,
            context.config["domain"].max,
        )
    state.densities = torch.full_like(state.densities, spec.initial_density)
    return context, tensor_sha256(state.positions)


def evaluate_fluid_neighborhood(context: Any):
    from diffSPH.neighborhood import SupportScheme, evaluateNeighborhood

    _, neighbors = evaluateNeighborhood(
        context.system.systemState,
        context.config["domain"],
        context.config["kernel"],
        verletScale=context.config["neighborhood"]["verletScale"],
        mode=SupportScheme.SuperSymmetric,
        priorNeighborhood=None,
        useCheckpoint=False,
        computeHessian=False,
        computeDkDh=False,
        only_j=context.config["neighborhood"]["only_j"],
    )
    return neighbors.get("fluid")


def apply_gradient(
    context: Any,
    neighborhood: Any,
    scalar: torch.Tensor,
) -> torch.Tensor:
    from diffSPH.enums import GradientMode, Operation
    from diffSPH.neighborhood import SupportScheme
    from diffSPH.operations import SPHOperation

    return SPHOperation(
        context.system.systemState,
        quantity=scalar,
        kernel=context.config["kernel"],
        neighborhood=neighborhood[0],
        kernelValues=neighborhood[1],
        operation=Operation.Gradient,
        supportScheme=SupportScheme.Symmetric,
        gradientMode=GradientMode.Difference,
    )


def apply_divergence(
    context: Any,
    neighborhood: Any,
    vector: torch.Tensor,
) -> torch.Tensor:
    from diffSPH.enums import DivergenceMode, GradientMode, Operation
    from diffSPH.neighborhood import SupportScheme
    from diffSPH.operations import SPHOperation

    return SPHOperation(
        context.system.systemState,
        quantity=vector,
        kernel=context.config["kernel"],
        neighborhood=neighborhood[0],
        kernelValues=neighborhood[1],
        operation=Operation.Divergence,
        supportScheme=SupportScheme.Symmetric,
        gradientMode=GradientMode.Difference,
        divergenceMode=DivergenceMode.div,
    )


def apply_laplacian(
    context: Any,
    neighborhood: Any,
    quantity: torch.Tensor,
) -> torch.Tensor:
    from diffSPH.enums import GradientMode, LaplacianMode, Operation
    from diffSPH.neighborhood import SupportScheme
    from diffSPH.operations import SPHOperation

    return SPHOperation(
        context.system.systemState,
        quantity=quantity,
        kernel=context.config["kernel"],
        neighborhood=neighborhood[0],
        kernelValues=neighborhood[1],
        operation=Operation.Laplacian,
        supportScheme=SupportScheme.Symmetric,
        gradientMode=GradientMode.Difference,
        laplacianMode=LaplacianMode.default,
        positiveDivergence=False,
    )


def kernel_moments(
    context: Any,
    neighborhood: Any,
) -> dict[str, torch.Tensor]:
    from diffSPH.neighborhood import SupportScheme, evalKernel

    state = context.system.systemState
    sparse, precomputed = neighborhood
    i, j = sparse.row.to(torch.int64), sparse.col.to(torch.int64)
    weights = state.masses[j] / state.densities[j]
    kernel_values = evalKernel(
        precomputed,
        SupportScheme.Symmetric,
        combined=True,
    )
    edge_weight = weights * kernel_values

    s0 = torch.zeros(
        state.positions.shape[0],
        dtype=state.positions.dtype,
        device=state.positions.device,
    )
    s0.index_add_(0, i, edge_weight)
    # precomputed.x_ij is x_i - x_j after minimum-image wrapping.
    displacement_j_minus_i = -precomputed.x_ij
    s1 = torch.zeros_like(state.positions)
    s1.index_add_(
        0,
        i,
        edge_weight[:, None] * displacement_j_minus_i,
    )
    return {"s0": s0, "s1": s1}


def neighborhood_audit(
    context: Any,
    neighborhood: Any,
) -> dict[str, int | float]:
    sparse, precomputed = neighborhood
    state = context.system.systemState
    i = sparse.row.to(torch.int64)
    j = sparse.col.to(torch.int64)
    count = state.positions.shape[0]
    keys = i * count + j
    reverse_keys = j * count + i
    unique_keys, key_counts = torch.unique(keys, return_counts=True)
    reciprocal = torch.isin(reverse_keys, unique_keys)

    out_of_bounds = (
        (i < 0) | (i >= count) | (j < 0) | (j >= count)
    )
    self_edges = i == j
    nonself = ~self_edges

    manual = state.positions[i] - state.positions[j]
    extent = context.config["domain"].max - context.config["domain"].min
    periodic = context.config["domain"].periodic
    for axis in range(state.positions.shape[1]):
        if bool(periodic[axis]):
            manual[:, axis] = torch.remainder(
                manual[:, axis] + 0.5 * extent[axis],
                extent[axis],
            ) - 0.5 * extent[axis]
    distance_difference = (manual - precomputed.x_ij).abs().max()

    positions = state.positions
    pair_delta = positions[:, None, :] - positions[None, :, :]
    for axis in range(state.positions.shape[1]):
        if bool(periodic[axis]):
            pair_delta[:, :, axis] = torch.remainder(
                pair_delta[:, :, axis] + 0.5 * extent[axis],
                extent[axis],
            ) - 0.5 * extent[axis]
    pair_distance = torch.linalg.vector_norm(pair_delta, dim=-1)
    support = torch.maximum(
        state.supports[:, None],
        state.supports[None, :],
    )
    expected_inclusive = pair_distance <= support * (1.0 + 2.0e-6)
    expected_strict = pair_distance < support * (1.0 - 2.0e-6)
    inclusive_pairs = torch.nonzero(expected_inclusive, as_tuple=False)
    strict_pairs = torch.nonzero(expected_strict, as_tuple=False)
    inclusive_keys = inclusive_pairs[:, 0] * count + inclusive_pairs[:, 1]
    strict_keys = strict_pairs[:, 0] * count + strict_pairs[:, 1]
    missing_inclusive = ~torch.isin(inclusive_keys, unique_keys)
    missing_strict = ~torch.isin(strict_keys, unique_keys)
    unexpected = ~torch.isin(unique_keys, inclusive_keys)

    return {
        "edge_count": int(keys.numel()),
        "unique_edge_count": int(unique_keys.numel()),
        "duplicate_edge_count": int((key_counts - 1).clamp_min(0).sum()),
        "self_edge_count": int(self_edges.sum()),
        "missing_self_edge_count": int(
            count - torch.unique(i[self_edges]).numel()
        ),
        "nonreciprocal_nonself_edge_count": int(
            (~reciprocal[nonself]).sum()
        ),
        "out_of_bounds_edge_count": int(out_of_bounds.sum()),
        "minimum_image_linf": float(distance_difference.detach().cpu()),
        "omitted_strict_interior_edge_count": int(missing_strict.sum()),
        "omitted_inclusive_cutoff_edge_count": int(missing_inclusive.sum()),
        "unexpected_edge_count": int(unexpected.sum()),
    }


def viscous_conservation_audit(
    context: Any,
    neighborhood: Any,
    velocity: torch.Tensor,
    *,
    nu: float = 0.02,
    density_perturbation: float = 0.0,
) -> dict[str, float]:
    """Quantify edge antisymmetry and global balances for the B-path operator."""

    from diffSPH.neighborhood import SupportScheme, evalKernelGradient

    state = context.system.systemState
    state.velocities = velocity
    if density_perturbation:
        state.densities = 1.0 + density_perturbation * torch.sin(
            2.0 * torch.pi * state.positions[:, 0]
        )
    else:
        state.densities = torch.ones_like(state.densities)

    sparse, precomputed = neighborhood
    i = sparse.row.to(torch.int64)
    j = sparse.col.to(torch.int64)
    grad_w = evalKernelGradient(
        precomputed,
        SupportScheme.Symmetric,
        combined=True,
    )
    r_eps = precomputed.r_ij + 1.0e-8 * state.supports[i]
    radial = torch.einsum("nd,nd->n", precomputed.x_ij, grad_w)
    scalar = (
        -2.0
        * nu
        * (state.masses[j] / state.densities[j])
        * radial
        / r_eps.square()
    )
    edge_acceleration = scalar[:, None] * (velocity[j] - velocity[i])
    edge_force = state.masses[i, None] * edge_acceleration

    count = state.positions.shape[0]
    keys = i * count + j
    order = torch.argsort(keys)
    sorted_keys = keys[order]
    reverse_keys = j * count + i
    reverse_position = torch.searchsorted(sorted_keys, reverse_keys)
    reverse_exists = (
        (reverse_position < sorted_keys.numel())
        & (
            sorted_keys[
                reverse_position.clamp_max(sorted_keys.numel() - 1)
            ]
            == reverse_keys
        )
    )
    if not bool(reverse_exists.all()):
        raise RuntimeError("viscous edge audit requires reciprocal neighbors")
    reverse_edge = order[reverse_position]
    pair_residual = edge_force + edge_force[reverse_edge]
    unordered = i < j
    pair_residual_unordered = pair_residual[unordered]

    acceleration = torch.zeros_like(velocity)
    acceleration.index_add_(0, i, edge_acceleration)
    total_force = torch.sum(state.masses[:, None] * acceleration, dim=0)
    force_scale = torch.sum(torch.linalg.vector_norm(edge_force, dim=-1))
    torque = torch.sum(
        state.masses
        * (
            state.positions[:, 0] * acceleration[:, 1]
            - state.positions[:, 1] * acceleration[:, 0]
        )
    )
    power = torch.sum(
        state.masses
        * torch.einsum("nd,nd->n", velocity, acceleration)
    )
    eps = torch.finfo(state.positions.dtype).eps
    return {
        "density_perturbation": density_perturbation,
        "pair_force_residual_l2": float(
            torch.sqrt(torch.mean(pair_residual_unordered.square()))
            .detach()
            .cpu()
        ),
        "pair_force_residual_linf": float(
            pair_residual_unordered.abs().max().detach().cpu()
        ),
        "total_internal_force": float(
            torch.linalg.vector_norm(total_force).detach().cpu()
        ),
        "characteristic_normalized_internal_force": float(
            (
                torch.linalg.vector_norm(total_force)
                / (force_scale + eps)
            )
            .detach()
            .cpu()
        ),
        "total_internal_torque": float(torque.detach().cpu()),
        "viscous_power": float(power.detach().cpu()),
    }


def pressure_conservation_audit(
    context: Any,
    neighborhood: Any,
    *,
    density_offset: float,
    density_amplitude: float,
) -> dict[str, float]:
    """Evaluate total internal force for the configured pressure operator."""

    from diffSPH.modules.eos import computeEOS_WC
    from diffSPH.modules.pressureForce import computePressureForce
    from diffSPH.neighborhood import (
        SupportScheme,
        evalKernelGradient,
    )

    state = context.system.systemState
    state.densities = (
        density_offset
        + density_amplitude
        * torch.sin(2.0 * torch.pi * state.positions[:, 0])
    )
    state.pressures = computeEOS_WC(state, context.config)
    acceleration = computePressureForce(
        state,
        context.config["kernel"],
        neighborhood,
        SupportScheme.Symmetric,
        context.config,
    )
    total_force = torch.sum(state.masses[:, None] * acceleration, dim=0)
    acceleration_scale = torch.sum(
        state.masses * torch.linalg.vector_norm(acceleration, dim=-1)
    )
    eps = torch.finfo(state.positions.dtype).eps

    sparse, precomputed = neighborhood
    i = sparse.row.to(torch.int64)
    j = sparse.col.to(torch.int64)
    p_i = state.pressures[i]
    p_j = state.pressures[j]
    p_ij = torch.where(p_i >= 0.0, p_j + p_i, p_j - p_i)
    grad_w = evalKernelGradient(
        precomputed,
        SupportScheme.Symmetric,
        combined=True,
    )
    edge_acceleration = -(
        (state.masses[j] / state.densities[j]) * p_ij
    )[:, None] * grad_w / state.densities[i, None]
    edge_force = state.masses[i, None] * edge_acceleration
    count = state.positions.shape[0]
    keys = i * count + j
    order = torch.argsort(keys)
    sorted_keys = keys[order]
    reverse_keys = j * count + i
    reverse_position = torch.searchsorted(sorted_keys, reverse_keys)
    reverse_edge = order[reverse_position]
    pair_residual = edge_force + edge_force[reverse_edge]
    pair_residual = pair_residual[i < j]
    return {
        "density_offset": density_offset,
        "density_amplitude": density_amplitude,
        "minimum_pressure": float(state.pressures.min().detach().cpu()),
        "maximum_pressure": float(state.pressures.max().detach().cpu()),
        "total_internal_force": float(
            torch.linalg.vector_norm(total_force).detach().cpu()
        ),
        "characteristic_normalized_internal_force": float(
            (
                torch.linalg.vector_norm(total_force)
                / (acceleration_scale + eps)
            )
            .detach()
            .cpu()
        ),
        "pair_force_residual_l2": float(
            torch.sqrt(torch.mean(pair_residual.square())).detach().cpu()
        ),
        "pair_force_residual_linf": float(
            pair_residual.abs().max().detach().cpu()
        ),
    }
