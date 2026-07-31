"""Run the preregistered Stage 01C static requalification matrix."""

from __future__ import annotations

import argparse
import hashlib
import math
from pathlib import Path
import platform
import resource
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import torch  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOLVER_ROOT = PROJECT_ROOT / "01_solver"
if str(SOLVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SOLVER_ROOT))

from manufactured_fields.periodic import (  # noqa: E402
    scalar_field,
    scalar_gradient,
    scalar_laplacian,
    vector_divergence,
    vector_field,
    vector_laplacian,
)
from structure_preserving.conservative_pressure import (  # noqa: E402
    pressure_conservation_metrics,
)
from structure_preserving.conservative_viscosity import (  # noqa: E402
    conservative_viscosity_acceleration,
    stage01b_style_generic_acceleration,
    viscosity_conservation_metrics,
)
from structure_preserving.kernels import (  # noqa: E402
    divergence_from_vector_gradient,
    first_order_corrected_gradient,
    interpolate_from_edge_weights,
    linear_reproducing_edge_weights,
    moment_corrected_laplacian,
    moments_from_edge_weights,
    quadratic_weighted_least_squares,
    raw_edge_weights,
    raw_gradient,
    raw_kernel_moments,
    raw_laplacian,
    shepard_edge_weights,
    shepard_gradient,
    shepard_laplacian,
)
from structure_preserving.native_autograd_ops import (  # noqa: E402
    run_native_autograd_matrix,
)
from structure_preserving.neighborhood import (  # noqa: E402
    audit_periodic_neighborhood,
    build_periodic_neighborhood,
    periodic_cartesian_layout,
    tensor_sha256,
)
from structure_preserving.support_scaling import (  # noqa: E402
    StaticExperimentDesign,
    load_preregistered_design,
)


def _peak_rss_bytes() -> int:
    observed = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return observed if platform.system() == "Darwin" else observed * 1024


def _error_norms(
    numerical: torch.Tensor,
    exact: torch.Tensor,
) -> dict[str, float]:
    error = (numerical - exact).reshape(-1)
    return {
        "L1": float(error.abs().mean()),
        "L2": float(torch.sqrt(torch.mean(error.square()))),
        "Linf": float(error.abs().max()),
    }


def _moment_norms(moment: torch.Tensor, target: float) -> dict[str, float]:
    error = (moment - target).reshape(-1)
    return {
        "mean_abs": float(error.abs().mean()),
        "L2": float(torch.sqrt(torch.mean(error.square()))),
        "Linf": float(error.abs().max()),
    }


def _append_errors(
    rows: list[dict[str, Any]],
    metadata: dict[str, Any],
    *,
    candidate: str,
    operator: str,
    norms: dict[str, float],
) -> None:
    if operator == "Laplacian":
        variants = {
            "raw_sph": "raw_brookshaw_component_laplacian",
            "shepard_normalized": "nodewise_S0_scaled_brookshaw_laplacian",
            "first_order_gradient_matrix": (
                "isotropic_quadratic_response_laplacian"
            ),
            "quadratic_weighted_least_squares": (
                "local_quadratic_weighted_least_squares_laplacian"
            ),
        }
    elif operator in ("gradient", "divergence"):
        variants = {
            "raw_sph": "raw_difference_gradient",
            "shepard_normalized": "nodewise_S0_scaled_difference_gradient",
            "first_order_gradient_matrix": (
                "local_first_moment_inverse_gradient"
            ),
            "quadratic_weighted_least_squares": (
                "local_quadratic_weighted_least_squares_gradient"
            ),
        }
    elif operator == "viscous_acceleration":
        variants = {
            "conservative_pair_viscosity": (
                "symmetric_nonnegative_pair_Gamma"
            ),
            "stage01b_style_generic_viscosity": (
                "frozen_one_sided_generic_laplacian"
            ),
        }
    else:
        variants = {
            "raw_sph": "raw_kernel_weights",
            "shepard_normalized": "nodewise_S0_normalized_weights",
            "linear_reproducing_kernel": (
                "local_linear_reproducing_kernel_weights"
            ),
        }
    for norm, error in norms.items():
        rows.append(
            {
                **metadata,
                "candidate": candidate,
                "operator_variant": variants.get(candidate, candidate),
                "operator": operator,
                "norm": norm,
                "error": error,
            }
        )


def _case_metadata(
    *,
    family: str,
    resolution: int,
    jitter: float,
    seed: int,
    dtype: torch.dtype,
    dx: float,
    support_ratio: float,
    support: float,
    position_hash: str,
    position_reference_hash: str,
) -> dict[str, Any]:
    return {
        "support_family": family,
        "resolution": resolution,
        "particle_count": resolution**2,
        "layout": (
            "regular"
            if jitter == 0.0
            else f"jitter_{int(round(jitter * 100)):02d}"
        ),
        "jitter_fraction": jitter,
        "seed": seed,
        "dtype": str(dtype).removeprefix("torch."),
        "dx": dx,
        "support_ratio": support_ratio,
        "support": support,
        "position_state_sha256": position_hash,
        "position_reference_sha256": position_reference_hash,
    }


def _conservation_rows(
    metadata: dict[str, Any],
    *,
    positions: torch.Tensor,
    dx: float,
    neighborhood,
    experiment_scope: str,
) -> list[dict[str, Any]]:
    x = positions[:, 0]
    y = positions[:, 1]
    uniform_density = torch.ones(
        positions.shape[0],
        dtype=positions.dtype,
    )
    variable_density = (
        1.0 + 0.05 * torch.sin(2.0 * torch.pi * x)
    )
    pressure_cases = {
        "all_positive": (
            0.10
            + 0.03 * torch.sin(2.0 * torch.pi * x)
            - 0.02 * torch.cos(2.0 * torch.pi * y)
        ),
        "all_negative": (
            -0.10
            + 0.03 * torch.sin(2.0 * torch.pi * x)
            - 0.02 * torch.cos(2.0 * torch.pi * y)
        ),
        "mixed_sign": (
            0.05 * torch.sin(2.0 * torch.pi * x)
            - 0.03 * torch.cos(2.0 * torch.pi * y)
        ),
    }
    density_cases = {
        "uniform": uniform_density,
        "variable_05": variable_density,
    }
    mass = torch.full(
        (positions.shape[0],),
        dx**2,
        dtype=positions.dtype,
    )
    velocity = vector_field(positions)
    rows: list[dict[str, Any]] = []
    for density_name, density in density_cases.items():
        for pressure_name, pressure in pressure_cases.items():
            rows.append(
                {
                    **metadata,
                    "experiment_scope": experiment_scope,
                    "force_type": "conservative_pressure",
                    "density_case": density_name,
                    "field_case": pressure_name,
                    "minimum_pressure": float(pressure.min()),
                    "maximum_pressure": float(pressure.max()),
                    **pressure_conservation_metrics(
                        neighborhood,
                        mass=mass,
                        density=density,
                        pressure=pressure,
                    ),
                }
            )
        viscosity_metrics = viscosity_conservation_metrics(
            neighborhood,
            mass=mass,
            density=density,
            velocity=velocity,
            physical_viscosity=0.02,
        )
        conservative_acceleration = conservative_viscosity_acceleration(
            neighborhood,
            mass=mass,
            density=density,
            velocity=velocity,
            physical_viscosity=0.02,
        )
        stage01b_acceleration = stage01b_style_generic_acceleration(
            neighborhood,
            mass=mass,
            density=density,
            velocity=velocity,
            physical_viscosity=0.02,
        )
        stage01b_force = mass[:, None] * stage01b_acceleration
        stage01b_force_scale = torch.sum(
            torch.linalg.vector_norm(stage01b_force, dim=-1)
        )
        tiny = torch.finfo(positions.dtype).tiny
        rows.append(
            {
                **metadata,
                "experiment_scope": experiment_scope,
                "force_type": "conservative_viscosity",
                "density_case": density_name,
                "field_case": "manufactured_velocity",
                **viscosity_metrics,
                "stage01b_style_acceleration_difference_Linf": float(
                    (
                        conservative_acceleration
                        - stage01b_acceleration
                    )
                    .abs()
                    .max()
                ),
                "stage01b_style_relative_total_internal_force": float(
                    torch.linalg.vector_norm(
                        stage01b_force.sum(dim=0)
                    )
                    / (stage01b_force_scale + tiny)
                ),
            }
        )
    return rows


def compute_static_case(
    *,
    family: str,
    resolution: int,
    jitter: float,
    seed: int,
    support_ratio: float,
    dtype: torch.dtype,
    include_conservation: bool,
    experiment_scope: str,
    reference_positions: torch.Tensor | None = None,
    reference_position_hash: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    if reference_positions is None:
        positions, dx, position_hash = periodic_cartesian_layout(
            resolution,
            jitter_fraction=jitter,
            seed=seed,
            dtype=dtype,
        )
        position_reference_hash = position_hash
    else:
        if reference_positions.shape != (resolution**2, 2):
            raise ValueError("reference positions do not match resolution")
        positions = reference_positions.to(dtype=dtype).clone()
        dx = 2.0 / resolution
        position_hash = tensor_sha256(positions)
        if reference_position_hash is None:
            raise ValueError(
                "reference_position_hash is required with reference_positions"
            )
        position_reference_hash = reference_position_hash
    support = support_ratio * dx
    neighborhood = build_periodic_neighborhood(positions, support)
    audit = audit_periodic_neighborhood(positions, neighborhood)
    metadata = _case_metadata(
        family=family,
        resolution=resolution,
        jitter=jitter,
        seed=seed,
        dtype=dtype,
        dx=dx,
        support_ratio=support_ratio,
        support=support,
        position_hash=position_hash,
        position_reference_hash=position_reference_hash,
    )
    wide: dict[str, Any] = {**metadata, **audit}
    long_rows: list[dict[str, Any]] = []
    volume = dx**2
    scalar = scalar_field(positions)
    vector = vector_field(positions)
    exact_gradient = scalar_gradient(positions)
    exact_divergence = vector_divergence(positions)
    exact_laplacian = scalar_laplacian(positions)

    raw_moments = raw_kernel_moments(neighborhood, volume)
    shepard_weights = shepard_edge_weights(neighborhood, volume)
    shepard_moments = moments_from_edge_weights(
        neighborhood,
        shepard_weights,
    )
    reproducing_weights, reproducing_matrix = (
        linear_reproducing_edge_weights(neighborhood, volume)
    )
    reproducing_moments = moments_from_edge_weights(
        neighborhood,
        reproducing_weights,
    )
    moment_candidates = {
        "raw_sph": raw_moments,
        "shepard_normalized": shepard_moments,
        "linear_reproducing_kernel": reproducing_moments,
    }
    for candidate, moments in moment_candidates.items():
        s0 = _moment_norms(moments["s0"], 1.0)
        s1 = _moment_norms(moments["s1"], 0.0)
        for norm, value in s0.items():
            wide[f"{candidate}__kernel_S0__{norm}"] = value
        for norm in ("L2", "Linf"):
            wide[f"{candidate}__kernel_S1__{norm}"] = s1[norm]
        _append_errors(
            long_rows,
            metadata,
            candidate=candidate,
            operator="kernel_S0",
            norms=s0,
        )
        _append_errors(
            long_rows,
            metadata,
            candidate=candidate,
            operator="kernel_S1",
            norms={"L2": s1["L2"], "Linf": s1["Linf"]},
        )

    interpolation_weights = {
        "raw_sph": raw_edge_weights(neighborhood, volume),
        "shepard_normalized": shepard_weights,
        "linear_reproducing_kernel": reproducing_weights,
    }
    for candidate, weights in interpolation_weights.items():
        interpolation = interpolate_from_edge_weights(
            neighborhood,
            weights,
            scalar,
        )
        norms = _error_norms(interpolation, scalar)
        _append_errors(
            long_rows,
            metadata,
            candidate=candidate,
            operator="scalar_interpolation",
            norms=norms,
        )

    raw_scalar_gradient = raw_gradient(
        neighborhood,
        scalar,
        volume,
    )
    raw_vector_gradient = raw_gradient(
        neighborhood,
        vector,
        volume,
    )
    shepard_scalar_gradient = shepard_gradient(
        neighborhood,
        scalar,
        volume,
    )
    shepard_vector_gradient = shepard_gradient(
        neighborhood,
        vector,
        volume,
    )
    corrected_scalar_gradient, correction_matrix = (
        first_order_corrected_gradient(neighborhood, scalar, volume)
    )
    corrected_vector_gradient, _ = first_order_corrected_gradient(
        neighborhood,
        vector,
        volume,
    )
    wls_scalar_gradient, wls_scalar_laplacian, wls_matrix = (
        quadratic_weighted_least_squares(
            neighborhood,
            scalar,
            volume,
        )
    )
    wls_vector_gradient, _, _ = quadratic_weighted_least_squares(
        neighborhood,
        vector,
        volume,
    )
    gradients = {
        "raw_sph": raw_scalar_gradient,
        "shepard_normalized": shepard_scalar_gradient,
        "first_order_gradient_matrix": corrected_scalar_gradient,
        "quadratic_weighted_least_squares": wls_scalar_gradient,
    }
    vector_gradients = {
        "raw_sph": raw_vector_gradient,
        "shepard_normalized": shepard_vector_gradient,
        "first_order_gradient_matrix": corrected_vector_gradient,
        "quadratic_weighted_least_squares": wls_vector_gradient,
    }
    for candidate, numerical in gradients.items():
        norms = _error_norms(numerical, exact_gradient)
        _append_errors(
            long_rows,
            metadata,
            candidate=candidate,
            operator="gradient",
            norms=norms,
        )
        for norm, value in norms.items():
            wide[f"{candidate}__gradient__{norm}"] = value
    for candidate, numerical_gradient in vector_gradients.items():
        numerical = divergence_from_vector_gradient(numerical_gradient)
        norms = _error_norms(numerical, exact_divergence)
        _append_errors(
            long_rows,
            metadata,
            candidate=candidate,
            operator="divergence",
            norms=norms,
        )
        for norm, value in norms.items():
            wide[f"{candidate}__divergence__{norm}"] = value

    corrected_laplacian, laplacian_response = (
        moment_corrected_laplacian(neighborhood, scalar, volume)
    )
    laplacians = {
        "raw_sph": raw_laplacian(neighborhood, scalar, volume),
        "shepard_normalized": shepard_laplacian(
            neighborhood,
            scalar,
            volume,
        ),
        "first_order_gradient_matrix": corrected_laplacian,
        "quadratic_weighted_least_squares": wls_scalar_laplacian,
    }
    for candidate, numerical in laplacians.items():
        norms = _error_norms(numerical, exact_laplacian)
        _append_errors(
            long_rows,
            metadata,
            candidate=candidate,
            operator="Laplacian",
            norms=norms,
        )
        for norm, value in norms.items():
            wide[f"{candidate}__Laplacian__{norm}"] = value

    density = torch.ones(
        positions.shape[0],
        dtype=positions.dtype,
    )
    mass = torch.full_like(density, volume)
    conservative_viscosity = conservative_viscosity_acceleration(
        neighborhood,
        mass=mass,
        density=density,
        velocity=vector,
        physical_viscosity=0.02,
    )
    stage01b_viscosity = stage01b_style_generic_acceleration(
        neighborhood,
        mass=mass,
        density=density,
        velocity=vector,
        physical_viscosity=0.02,
    )
    exact_viscosity = 0.02 * vector_laplacian(positions)
    for candidate, numerical in {
        "conservative_pair_viscosity": conservative_viscosity,
        "stage01b_style_generic_viscosity": stage01b_viscosity,
    }.items():
        norms = _error_norms(numerical, exact_viscosity)
        _append_errors(
            long_rows,
            metadata,
            candidate=candidate,
            operator="viscous_acceleration",
            norms=norms,
        )
        for norm, value in norms.items():
            wide[f"{candidate}__viscous_acceleration__{norm}"] = value

    wide.update(
        {
            "reproducing_matrix_condition_maximum": float(
                torch.linalg.cond(reproducing_matrix).max()
            ),
            "gradient_matrix_condition_maximum": float(
                torch.linalg.cond(correction_matrix).max()
            ),
            "wls_matrix_condition_maximum": float(
                torch.linalg.cond(wls_matrix).max()
            ),
            "laplacian_calibration_response_minimum": float(
                laplacian_response.min()
            ),
            "peak_rss_bytes": _peak_rss_bytes(),
        }
    )
    conservation = (
        _conservation_rows(
            metadata,
            positions=positions,
            dx=dx,
            neighborhood=neighborhood,
            experiment_scope=experiment_scope,
        )
        if include_conservation
        else []
    )
    return wide, long_rows, conservation


def _stable_bootstrap_seed(base: int, key: tuple[Any, ...]) -> int:
    digest = hashlib.sha256(repr(key).encode("utf-8")).digest()
    return (base + int.from_bytes(digest[:4], "little")) % (2**32)


def _bootstrap_mean_interval(
    values: np.ndarray,
    *,
    resamples: int,
    seed: int,
) -> tuple[float, float]:
    generator = np.random.default_rng(seed)
    indices = generator.integers(
        0,
        len(values),
        size=(resamples, len(values)),
    )
    means = values[indices].mean(axis=1)
    return (
        float(np.quantile(means, 0.025)),
        float(np.quantile(means, 0.975)),
    )


def summarize_ensemble(
    metrics: pd.DataFrame,
    design: StaticExperimentDesign,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    group_columns = [
        "support_family",
        "resolution",
        "layout",
        "jitter_fraction",
        "dtype",
        "candidate",
        "operator_variant",
        "operator",
        "norm",
    ]
    summaries: list[dict[str, Any]] = []
    for key, group in metrics.groupby(group_columns, sort=True):
        values = group["error"].to_numpy(dtype=float)
        low, high = _bootstrap_mean_interval(
            values,
            resamples=design.bootstrap_resamples,
            seed=_stable_bootstrap_seed(design.bootstrap_seed, key),
        )
        summaries.append(
            {
                **dict(zip(group_columns, key)),
                "sample_count": len(values),
                "mean": float(values.mean()),
                "sample_standard_deviation": float(
                    values.std(ddof=1) if len(values) > 1 else 0.0
                ),
                "median": float(np.median(values)),
                "bootstrap_mean_CI95_low": low,
                "bootstrap_mean_CI95_high": high,
                "minimum": float(values.min()),
                "maximum": float(values.max()),
            }
        )
    summary = pd.DataFrame(summaries)

    slope_columns = [
        "support_family",
        "layout",
        "jitter_fraction",
        "dtype",
        "candidate",
        "operator_variant",
        "operator",
        "norm",
    ]
    slopes: list[dict[str, Any]] = []
    tiny = np.finfo(float).tiny
    for key, group in summary.groupby(slope_columns, sort=True):
        ordered = group.sort_values("resolution")
        if len(ordered) != len(design.resolutions):
            continue
        log_dx = np.log(design.domain_length / ordered["resolution"].to_numpy())
        mean_values = np.maximum(ordered["mean"].to_numpy(), tiny)
        median_values = np.maximum(ordered["median"].to_numpy(), tiny)
        mean_slope = float(np.polyfit(log_dx, np.log(mean_values), 1)[0])
        median_slope = float(np.polyfit(log_dx, np.log(median_values), 1)[0])
        slopes.append(
            {
                **dict(zip(slope_columns, key)),
                "mean_log_error_log_dx_slope": mean_slope,
                "median_log_error_log_dx_slope": median_slope,
                "mean_endpoint_ratio_64_over_16": float(
                    mean_values[-1] / mean_values[0]
                ),
                "median_endpoint_ratio_64_over_16": float(
                    median_values[-1] / median_values[0]
                ),
            }
        )
    slope_frame = pd.DataFrame(slopes)

    rebound_columns = [
        "support_family",
        "layout",
        "jitter_fraction",
        "dtype",
        "candidate",
        "operator_variant",
        "operator",
        "norm",
    ]
    rebounds: list[dict[str, Any]] = []
    for key, group in metrics.groupby(rebound_columns, sort=True):
        coarse = group[group["resolution"] == 48][["seed", "error"]]
        fine = group[group["resolution"] == 64][["seed", "error"]]
        paired = coarse.merge(fine, on="seed", suffixes=("_48", "_64"))
        if len(paired) != len(design.seeds):
            continue
        differences = (
            paired["error_64"].to_numpy() - paired["error_48"].to_numpy()
        )
        low, high = _bootstrap_mean_interval(
            differences,
            resamples=design.bootstrap_resamples,
            seed=_stable_bootstrap_seed(
                design.bootstrap_seed,
                (*key, "rebound"),
            ),
        )
        rebounds.append(
            {
                **dict(zip(rebound_columns, key)),
                "paired_seed_count": len(differences),
                "mean_error_64_minus_48": float(differences.mean()),
                "median_error_64_minus_48": float(np.median(differences)),
                "bootstrap_mean_difference_CI95_low": low,
                "bootstrap_mean_difference_CI95_high": high,
                "systematic_finest_rebound": bool(low > 0.0),
            }
        )
    return summary, slope_frame, pd.DataFrame(rebounds)


def summarize_support(per_seed: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    grouped = (
        per_seed.groupby(
            [
                "support_family",
                "resolution",
                "layout",
                "jitter_fraction",
            ],
            as_index=False,
        )
        .agg(
            dx=("dx", "first"),
            support_ratio=("support_ratio", "first"),
            support=("support", "first"),
            ensemble_neighbor_count_mean=("neighbor_count_mean", "mean"),
            ensemble_neighbor_count_std=("neighbor_count_mean", "std"),
            mean_particle_neighbor_std=("neighbor_count_std", "mean"),
            minimum_particle_neighbor_count=("neighbor_count_min", "min"),
            maximum_particle_neighbor_count=("neighbor_count_max", "max"),
            maximum_duplicate_edges=("duplicate_edge_count", "max"),
            maximum_strict_omissions=(
                "omitted_strict_support_edge_count",
                "max",
            ),
        )
    )
    checks: list[dict[str, Any]] = []
    for key, group in grouped.groupby(
        ["support_family", "layout", "jitter_fraction"],
        sort=True,
    ):
        ordered = group.sort_values("resolution")
        supports = ordered["support"].to_numpy()
        neighbors = ordered["ensemble_neighbor_count_mean"].to_numpy()
        checks.append(
            {
                "support_family": key[0],
                "layout": key[1],
                "jitter_fraction": key[2],
                "support_strictly_decreases": bool(
                    np.all(np.diff(supports) < 0.0)
                ),
                "ensemble_neighbor_mean_strictly_increases": bool(
                    np.all(np.diff(neighbors) > 0.0)
                ),
                "neighbor_endpoint_ratio_64_over_16": float(
                    neighbors[-1] / neighbors[0]
                ),
            }
        )
    return grouped, pd.DataFrame(checks)


def _plot_results(
    *,
    ensemble: pd.DataFrame,
    support: pd.DataFrame,
    precision: pd.DataFrame,
    conservation: pd.DataFrame,
    autograd: pd.DataFrame,
    directories: dict[str, Path],
) -> None:
    for directory in directories.values():
        (directory / "figures").mkdir(parents=True, exist_ok=True)

    focus = ensemble[
        (ensemble["support_family"] == "increasing_neighbor")
        & (ensemble["layout"] == "jitter_10")
        & (ensemble["norm"] == "L2")
        & (
            ensemble["operator"].isin(
                ["kernel_S0", "gradient", "divergence", "Laplacian"]
            )
        )
        & (
            ensemble["candidate"].isin(
                ["raw_sph", "quadratic_weighted_least_squares"]
            )
        )
    ]
    figure, axes = plt.subplots(2, 2, figsize=(11, 8))
    for axis, operator in zip(
        axes.reshape(-1),
        ["kernel_S0", "gradient", "divergence", "Laplacian"],
    ):
        subset = focus[focus["operator"] == operator]
        for candidate, group in subset.groupby("candidate"):
            axis.plot(
                group["resolution"],
                group["mean"],
                "o-",
                label=candidate,
            )
            axis.fill_between(
                group["resolution"],
                group["bootstrap_mean_CI95_low"],
                group["bootstrap_mean_CI95_high"],
                alpha=0.18,
            )
        axis.set_title(operator)
        axis.set_yscale("log")
        axis.grid(alpha=0.25)
        axis.set_xlabel("particles per axis")
        if not subset.empty:
            axis.legend(fontsize=8)
    axes[0, 0].set_ylabel("ensemble mean L2 error")
    axes[1, 0].set_ylabel("ensemble mean L2 error")
    figure.tight_layout()
    figure.savefig(
        directories["disorder"] / "figures" / "ensemble_error_trends.png",
        dpi=180,
    )
    plt.close(figure)

    figure, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    for family, group in support.groupby("support_family"):
        regular = group[group["layout"] == "regular"]
        axes[0].plot(
            regular["resolution"],
            regular["support"],
            "o-",
            label=family,
        )
        axes[1].plot(
            regular["resolution"],
            regular["ensemble_neighbor_count_mean"],
            "o-",
            label=family,
        )
    axes[0].set_title("Physical compact support")
    axes[0].set_ylabel("H")
    axes[1].set_title("Mean neighbor count")
    for axis in axes:
        axis.set_xlabel("particles per axis")
        axis.grid(alpha=0.25)
        axis.legend()
    figure.tight_layout()
    figure.savefig(
        directories["support"] / "figures" / "support_scaling.png",
        dpi=180,
    )
    plt.close(figure)

    selected_precision = precision[
        (precision["operator"].isin(["kernel_S0", "Laplacian"]))
        & (precision["norm"] == "L2")
        & (
            precision["candidate"].isin(
                ["raw_sph", "quadratic_weighted_least_squares"]
            )
        )
    ]
    if not selected_precision.empty:
        figure, axis = plt.subplots(
            figsize=(10, 5.5),
            layout="constrained",
        )
        labels = (
            selected_precision["support_family"].replace(
                {
                    "constant_neighbor": "constant",
                    "increasing_neighbor": "increasing",
                }
            )
            + "\nN"
            + selected_precision["resolution"].astype(str)
            + " "
            + selected_precision["layout"]
            + "\n"
            + selected_precision["operator"]
        )
        x = np.arange(len(labels))
        axis.bar(
            x - 0.18,
            selected_precision["float32_error"],
            width=0.36,
            label="float32",
        )
        axis.bar(
            x + 0.18,
            selected_precision["float64_error"],
            width=0.36,
            label="float64",
        )
        axis.set_yscale("log")
        axis.set_xticks(x, labels, rotation=70, ha="right")
        axis.set_ylabel("error")
        axis.grid(alpha=0.2, axis="y")
        axis.legend()
        figure.savefig(
            directories["operators"]
            / "figures"
            / "precision_isolation.png",
            dpi=180,
        )
        plt.close(figure)

    representative = conservation[
        (conservation["layout"] == "jitter_10")
        & (conservation["resolution"] == 64)
        & (conservation["support_family"] == "increasing_neighbor")
        & (conservation["density_case"] == "variable_05")
        & (conservation["dtype"] == "float64")
        & (conservation["experiment_scope"] == "disorder_statistics")
    ]
    if not representative.empty:
        figure, axis = plt.subplots(
            figsize=(7.5, 3.8),
            layout="constrained",
        )
        plotted = (
            representative.groupby(
                ["force_type", "field_case"],
                as_index=False,
            )["relative_total_internal_force"]
            .max()
        )
        labels = (
            plotted["force_type"].str.replace(
                "conservative_",
                "",
                regex=False,
            )
            + " / "
            + plotted["field_case"].str.replace(
                "manufactured_velocity",
                "manufactured",
                regex=False,
            )
        )
        axis.barh(
            labels,
            plotted["relative_total_internal_force"],
        )
        axis.set_xscale("log")
        axis.set_xlabel("relative total internal-force residual")
        axis.grid(alpha=0.2, axis="x")
        figure.savefig(
            directories["operators"]
            / "figures"
            / "conservation_residuals.png",
            dpi=180,
        )
        plt.close(figure)

    figure, axis = plt.subplots(figsize=(8, 4.5))
    for parameter, group in autograd.groupby("parameter"):
        axis.plot(
            group["steps"],
            group["gradient_norm"],
            "o-",
            label=parameter,
        )
    axis.set_yscale("log")
    axis.set_xlabel("rollout steps")
    axis.set_ylabel("AD gradient norm")
    axis.grid(alpha=0.25)
    axis.legend(fontsize=8)
    figure.tight_layout()
    figure.savefig(
        directories["autograd"] / "figures" / "gradient_norms.png",
        dpi=180,
    )
    plt.close(figure)


def run(output_root: Path = PROJECT_ROOT / "06_experiments") -> None:
    design, record = load_preregistered_design()
    directories = {
        "disorder": output_root / "stage_01c_disorder_statistics",
        "support": output_root / "stage_01c_support_scaling",
        "operators": output_root / "stage_01c_operator_candidates",
        "autograd": output_root / "stage_01c_autograd",
    }
    for directory in directories.values():
        (directory / "results").mkdir(parents=True, exist_ok=True)

    per_seed_rows: list[dict[str, Any]] = []
    operator_rows: list[dict[str, Any]] = []
    conservation_rows: list[dict[str, Any]] = []
    total = (
        len(design.support_ratios)
        * len(design.resolutions)
        * len(design.jitter_fractions)
        * len(design.seeds)
    )
    completed = 0
    for family in design.support_ratios:
        for resolution in design.resolutions:
            ratio = design.support_ratio(family, resolution)
            for jitter in design.jitter_fractions:
                for seed in design.seeds:
                    wide, long, conservation = compute_static_case(
                        family=family,
                        resolution=resolution,
                        jitter=jitter,
                        seed=seed,
                        support_ratio=ratio,
                        dtype=torch.float64,
                        include_conservation=True,
                        experiment_scope="disorder_statistics",
                    )
                    per_seed_rows.append(wide)
                    operator_rows.extend(long)
                    conservation_rows.extend(conservation)
                    completed += 1
                    if completed % 10 == 0 or completed == total:
                        print(
                            f"static configurations: {completed}/{total}; "
                            f"peak_rss={_peak_rss_bytes()}",
                            flush=True,
                        )
                    if (
                        _peak_rss_bytes()
                        > record["stopping"]["maximum_static_peak_rss_bytes"]
                    ):
                        raise MemoryError(
                            "preregistered static peak-RSS stop line exceeded"
                        )

    per_seed = pd.DataFrame(per_seed_rows)
    operator_metrics = pd.DataFrame(operator_rows)
    conservation = pd.DataFrame(conservation_rows)
    ensemble, slopes, rebounds = summarize_ensemble(
        operator_metrics,
        design,
    )
    support, support_checks = summarize_support(per_seed)

    precision_wide: list[dict[str, Any]] = []
    precision_long: list[dict[str, Any]] = []
    precision_conservation: list[dict[str, Any]] = []
    dtype_map = {"float32": torch.float32, "float64": torch.float64}
    for case in record["precision_isolation"]["cases"]:
        jitter = (
            0.0
            if case["layout"] == "regular"
            else float(case["layout"].removeprefix("jitter_")) / 100.0
        )
        reference_positions, _, reference_position_hash = (
            periodic_cartesian_layout(
                int(case["resolution"]),
                jitter_fraction=jitter,
                seed=int(case["seed"]),
                dtype=torch.float64,
            )
        )
        for family in design.support_ratios:
            ratio = design.support_ratio(family, int(case["resolution"]))
            for dtype_name, dtype in dtype_map.items():
                wide, long, rows = compute_static_case(
                    family=family,
                    resolution=int(case["resolution"]),
                    jitter=jitter,
                    seed=int(case["seed"]),
                    support_ratio=ratio,
                    dtype=dtype,
                    include_conservation=True,
                    experiment_scope="precision_isolation",
                    reference_positions=reference_positions,
                    reference_position_hash=reference_position_hash,
                )
                precision_wide.append(wide)
                precision_long.extend(long)
                precision_conservation.extend(rows)
                print(
                    "precision case: "
                    f"{family}/{case['layout']}/"
                    f"N{case['resolution']}/{dtype_name}",
                    flush=True,
                )
    precision_wide_frame = pd.DataFrame(precision_wide)
    precision_long_frame = pd.DataFrame(precision_long)
    join_columns = [
        "support_family",
        "resolution",
        "layout",
        "jitter_fraction",
        "seed",
        "candidate",
        "operator_variant",
        "operator",
        "norm",
    ]
    precision32 = precision_long_frame[
        precision_long_frame["dtype"] == "float32"
    ][join_columns + ["error"]].rename(columns={"error": "float32_error"})
    precision64 = precision_long_frame[
        precision_long_frame["dtype"] == "float64"
    ][join_columns + ["error"]].rename(columns={"error": "float64_error"})
    precision_comparison = precision32.merge(precision64, on=join_columns)
    precision_comparison["absolute_error_difference"] = (
        precision_comparison["float32_error"]
        - precision_comparison["float64_error"]
    ).abs()
    precision_comparison["relative_error_difference"] = (
        precision_comparison["absolute_error_difference"]
        / np.maximum(
            np.maximum(
                precision_comparison["float32_error"],
                precision_comparison["float64_error"],
            ),
            np.finfo(float).tiny,
        )
    )
    conservation = pd.concat(
        [conservation, pd.DataFrame(precision_conservation)],
        ignore_index=True,
    )
    autograd = pd.DataFrame(run_native_autograd_matrix())

    per_seed.to_csv(
        directories["disorder"] / "results" / "per_seed_metrics.csv",
        index=False,
    )
    ensemble.to_csv(
        directories["disorder"] / "results" / "ensemble_summary.csv",
        index=False,
    )
    slopes.to_csv(
        directories["disorder"] / "results" / "ensemble_slopes.csv",
        index=False,
    )
    rebounds.to_csv(
        directories["disorder"] / "results" / "finest_rebound_audit.csv",
        index=False,
    )
    support.to_csv(
        directories["support"] / "results" / "support_scaling.csv",
        index=False,
    )
    support_checks.to_csv(
        directories["support"] / "results" / "support_family_checks.csv",
        index=False,
    )
    operator_metrics.to_csv(
        directories["operators"]
        / "results"
        / "operator_candidate_metrics.csv",
        index=False,
    )
    conservation.to_csv(
        directories["operators"] / "results" / "conservation_metrics.csv",
        index=False,
    )
    precision_wide_frame.to_csv(
        directories["operators"] / "results" / "precision_isolation.csv",
        index=False,
    )
    precision_comparison.to_csv(
        directories["operators"]
        / "results"
        / "precision_comparison.csv",
        index=False,
    )
    autograd.to_csv(
        directories["autograd"] / "results" / "native_autograd_fd.csv",
        index=False,
    )
    _plot_results(
        ensemble=ensemble,
        support=support,
        precision=precision_comparison,
        conservation=conservation,
        autograd=autograd,
        directories=directories,
    )
    print(
        {
            "per_seed_rows": len(per_seed),
            "operator_rows": len(operator_metrics),
            "ensemble_rows": len(ensemble),
            "conservation_rows": len(conservation),
            "autograd_rows": len(autograd),
            "peak_rss_bytes": _peak_rss_bytes(),
        },
        flush=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-root",
        type=Path,
        default=PROJECT_ROOT / "06_experiments",
    )
    args = parser.parse_args()
    run(args.output_root.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
