"""Generate Stage 01B V1 operator-verification CSV files and figures."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
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
)
from verification.integrator_ode import integrator_order_study  # noqa: E402
from verification.operator_tools import (  # noqa: E402
    LAYOUT_SEED,
    apply_divergence,
    apply_gradient,
    apply_laplacian,
    build_layout,
    error_norms,
    evaluate_fluid_neighborhood,
    kernel_moments,
    neighborhood_audit,
    pressure_conservation_audit,
    viscous_conservation_audit,
)


RESOLUTIONS = (16, 24, 32)
JITTERS = (0.0, 0.05, 0.10)
LAYOUT_NAMES = {0.0: "regular", 0.05: "jitter_05", 0.10: "jitter_10"}


def _append_operator_rows(
    rows: list[dict[str, object]],
    *,
    resolution: int,
    jitter: float,
    operator: str,
    values: dict[str, float],
) -> None:
    for norm, value in values.items():
        rows.append(
            {
                "resolution": resolution,
                "particle_count": resolution**2,
                "layout": LAYOUT_NAMES[jitter],
                "jitter_fraction": jitter,
                "operator": operator,
                "norm": norm,
                "error": value,
            }
        )


def _add_observed_orders(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.sort_values(["layout", "operator", "norm", "resolution"])
    frame["observed_order_from_previous"] = math.nan
    for _, indices in frame.groupby(["layout", "operator", "norm"]).groups.items():
        ordered = list(indices)
        for previous, current in zip(ordered, ordered[1:]):
            e0 = float(frame.loc[previous, "error"])
            e1 = float(frame.loc[current, "error"])
            n0 = float(frame.loc[previous, "resolution"])
            n1 = float(frame.loc[current, "resolution"])
            frame.loc[current, "observed_order_from_previous"] = (
                math.log(e0 / e1) / math.log(n1 / n0)
            )
    return frame


def collect_operator_data():
    layout_rows: list[dict[str, object]] = []
    kernel_rows: list[dict[str, object]] = []
    neighbor_rows: list[dict[str, object]] = []
    operator_rows: list[dict[str, object]] = []

    for jitter in JITTERS:
        for resolution in RESOLUTIONS:
            context, state_hash = build_layout(resolution, jitter)
            neighborhood = evaluate_fluid_neighborhood(context)
            state = context.system.systemState
            positions = state.positions

            layout_rows.append(
                {
                    "resolution": resolution,
                    "particle_count": resolution**2,
                    "layout": LAYOUT_NAMES[jitter],
                    "jitter_fraction": jitter,
                    "seed": LAYOUT_SEED + int(jitter * 100),
                    "position_state_sha256": state_hash,
                    "dx": context.spec.domain_length / resolution,
                    "support": float(state.supports[0]),
                    "verlet_scale": context.config["neighborhood"]["verletScale"],
                }
            )

            moments = kernel_moments(context, neighborhood)
            s0 = error_norms(moments["s0"], torch.ones_like(moments["s0"]))
            s1 = {
                "l2": float(
                    torch.sqrt(torch.mean(moments["s1"].square()))
                    .detach()
                    .cpu()
                ),
                "linf": float(moments["s1"].abs().max().detach().cpu()),
            }
            kernel_rows.append(
                {
                    "resolution": resolution,
                    "particle_count": resolution**2,
                    "layout": LAYOUT_NAMES[jitter],
                    "jitter_fraction": jitter,
                    "s0_mean_abs": s0["l1"],
                    "s0_l2": s0["l2"],
                    "s0_linf": s0["linf"],
                    "s1_l2": s1["l2"],
                    "s1_linf": s1["linf"],
                }
            )

            neighbor_rows.append(
                {
                    "resolution": resolution,
                    "particle_count": resolution**2,
                    "layout": LAYOUT_NAMES[jitter],
                    "jitter_fraction": jitter,
                    **neighborhood_audit(context, neighborhood),
                }
            )

            _append_operator_rows(
                operator_rows,
                resolution=resolution,
                jitter=jitter,
                operator="generic_sph_gradient",
                values=error_norms(
                    apply_gradient(
                        context,
                        neighborhood,
                        scalar_field(positions),
                    ),
                    scalar_gradient(positions),
                ),
            )
            _append_operator_rows(
                operator_rows,
                resolution=resolution,
                jitter=jitter,
                operator="generic_sph_divergence",
                values=error_norms(
                    apply_divergence(
                        context,
                        neighborhood,
                        vector_field(positions),
                    ),
                    vector_divergence(positions),
                ),
            )
            _append_operator_rows(
                operator_rows,
                resolution=resolution,
                jitter=jitter,
                operator="physical_nu_generic_laplacian",
                values=error_norms(
                    apply_laplacian(
                        context,
                        neighborhood,
                        scalar_field(positions),
                    ),
                    scalar_laplacian(positions),
                ),
            )

    return (
        pd.DataFrame(layout_rows),
        pd.DataFrame(kernel_rows),
        pd.DataFrame(neighbor_rows),
        _add_observed_orders(pd.DataFrame(operator_rows)),
    )


def collect_conservation_data() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for jitter in JITTERS:
        for resolution in RESOLUTIONS:
            for density_perturbation in (0.0, 0.05):
                context, _ = build_layout(resolution, jitter)
                neighborhood = evaluate_fluid_neighborhood(context)
                audit = viscous_conservation_audit(
                    context,
                    neighborhood,
                    vector_field(context.system.systemState.positions),
                    density_perturbation=density_perturbation,
                )
                rows.append(
                    {
                        "resolution": resolution,
                        "particle_count": resolution**2,
                        "layout": LAYOUT_NAMES[jitter],
                        "jitter_fraction": jitter,
                        "force_type": "physical_nu_laplacian",
                        "state_case": (
                            "uniform_density"
                            if density_perturbation == 0.0
                            else "density_perturbation_05"
                        ),
                        **audit,
                    }
                )

            for density_offset, state_case in (
                (1.01, "all_positive_pressure"),
                (1.0, "mixed_sign_pressure"),
            ):
                context, _ = build_layout(resolution, jitter)
                neighborhood = evaluate_fluid_neighborhood(context)
                audit = pressure_conservation_audit(
                    context,
                    neighborhood,
                    density_offset=density_offset,
                    density_amplitude=0.005,
                )
                rows.append(
                    {
                        "resolution": resolution,
                        "particle_count": resolution**2,
                        "layout": LAYOUT_NAMES[jitter],
                        "jitter_fraction": jitter,
                        "force_type": "Antuono_pressure",
                        "state_case": state_case,
                        **audit,
                    }
                )
    return pd.DataFrame(rows)


def collect_upstream_default_diagnostic() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for jitter in JITTERS:
        for verlet_scale in (1.4, 1.0):
            context, _ = build_layout(16, jitter)
            context.config["neighborhood"]["verletScale"] = verlet_scale
            neighborhood = evaluate_fluid_neighborhood(context)
            moments = kernel_moments(context, neighborhood)
            s0 = error_norms(moments["s0"], torch.ones_like(moments["s0"]))
            positions = context.system.systemState.positions
            laplacian = error_norms(
                apply_laplacian(
                    context,
                    neighborhood,
                    scalar_field(positions),
                ),
                scalar_laplacian(positions),
            )
            rows.append(
                {
                    "resolution": 16,
                    "layout": LAYOUT_NAMES[jitter],
                    "jitter_fraction": jitter,
                    "verlet_scale": verlet_scale,
                    **neighborhood_audit(context, neighborhood),
                    "s0_l2": s0["l2"],
                    "manufactured_laplacian_l2": laplacian["l2"],
                }
            )
    return pd.DataFrame(rows)


def _save_plots(
    figures: Path,
    kernel: pd.DataFrame,
    operators: pd.DataFrame,
    conservation: pd.DataFrame,
    integrator: pd.DataFrame,
) -> None:
    figures.mkdir(parents=True, exist_ok=True)

    figure, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    for layout, group in kernel.groupby("layout"):
        axes[0].plot(group["resolution"], group["s0_l2"], "o-", label=layout)
        axes[1].plot(group["resolution"], group["s1_l2"], "o-", label=layout)
    axes[0].set_title("Zeroth kernel moment")
    axes[0].set_ylabel("L2 error")
    axes[1].set_title("First kernel moment")
    for axis in axes:
        axis.set_xlabel("particles per axis")
        axis.set_yscale("log")
        axis.grid(alpha=0.25)
        axis.legend()
    figure.tight_layout()
    figure.savefig(figures / "kernel_moment_errors.png", dpi=180)
    plt.close(figure)

    figure, axes = plt.subplots(1, 3, figsize=(14, 4.2), sharex=True)
    for axis, operator in zip(
        axes,
        (
            "generic_sph_gradient",
            "generic_sph_divergence",
            "physical_nu_generic_laplacian",
        ),
    ):
        subset = operators[
            (operators["operator"] == operator)
            & (operators["norm"] == "l2")
        ]
        for layout, group in subset.groupby("layout"):
            axis.plot(group["resolution"], group["error"], "o-", label=layout)
        axis.set_title(operator.replace("_", " "))
        axis.set_xlabel("particles per axis")
        axis.set_yscale("log")
        axis.grid(alpha=0.25)
    axes[0].set_ylabel("L2 error")
    axes[-1].legend()
    figure.tight_layout()
    figure.savefig(figures / "manufactured_operator_errors.png", dpi=180)
    plt.close(figure)

    figure, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    cases = (
        ("physical_nu_laplacian", "density_perturbation_05"),
        ("Antuono_pressure", "mixed_sign_pressure"),
    )
    for axis, (force_type, state_case) in zip(axes, cases):
        subset = conservation[
            (conservation["force_type"] == force_type)
            & (conservation["state_case"] == state_case)
        ]
        for layout, group in subset.groupby("layout"):
            axis.plot(
                group["resolution"],
                group["characteristic_normalized_internal_force"],
                "o-",
                label=layout,
            )
        axis.set_title(f"{force_type}: {state_case}")
        axis.set_xlabel("particles per axis")
        axis.set_yscale("log")
        axis.grid(alpha=0.25)
    axes[0].set_ylabel("normalized internal-force residual")
    axes[-1].legend()
    figure.tight_layout()
    figure.savefig(figures / "conservation_residuals.png", dpi=180)
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(5.5, 4.2))
    axis.loglog(
        integrator["dt"],
        integrator["absolute_error"],
        "o-",
        label="diffSPH symplecticEuler interface",
    )
    axis.set_xlabel("dt")
    axis.set_ylabel("absolute error")
    axis.grid(alpha=0.25, which="both")
    axis.legend()
    figure.tight_layout()
    figure.savefig(figures / "integrator_order.png", dpi=180)
    plt.close(figure)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=(
            PROJECT_ROOT
            / "06_experiments"
            / "stage_01b_operator_verification"
        ),
    )
    args = parser.parse_args()
    output = args.output_directory.resolve()
    results = output / "results"
    figures = output / "figures"
    results.mkdir(parents=True, exist_ok=True)

    layouts, kernel, neighbors, operators = collect_operator_data()
    conservation = collect_conservation_data()
    upstream = collect_upstream_default_diagnostic()
    integrator = pd.DataFrame(integrator_order_study())

    layouts.to_csv(results / "layout_hashes.csv", index=False)
    kernel.to_csv(results / "kernel_moment_metrics.csv", index=False)
    neighbors.to_csv(results / "neighborhood_audit.csv", index=False)
    operators.to_csv(
        results / "manufactured_operator_metrics.csv",
        index=False,
    )
    conservation.to_csv(results / "conservation_audit.csv", index=False)
    upstream.to_csv(
        results / "upstream_default_neighbor_diagnostic.csv",
        index=False,
    )
    integrator.to_csv(results / "integrator_order.csv", index=False)
    _save_plots(figures, kernel, operators, conservation, integrator)

    print(f"wrote {len(layouts)} layout rows")
    print(f"wrote {len(operators)} manufactured-operator rows")
    print(f"wrote {len(conservation)} conservation rows")
    print(f"output={output.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
