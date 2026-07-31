"""Apply the preregistered Stage 01C candidate and gate rules."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOLVER_ROOT = PROJECT_ROOT / "01_solver"
if str(SOLVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SOLVER_ROOT))

from structure_preserving.support_scaling import (  # noqa: E402
    load_preregistered_design,
)


TARGET_OPERATORS = ("kernel_S0", "gradient", "divergence", "Laplacian")
REQUIRED_LAYOUTS = ("regular", "jitter_05", "jitter_10")


def _read_results(
    experiment_root: Path,
) -> dict[str, pd.DataFrame]:
    disorder = experiment_root / "stage_01c_disorder_statistics" / "results"
    support = experiment_root / "stage_01c_support_scaling" / "results"
    operators = experiment_root / "stage_01c_operator_candidates" / "results"
    autograd = experiment_root / "stage_01c_autograd" / "results"
    return {
        "per_seed": pd.read_csv(disorder / "per_seed_metrics.csv"),
        "ensemble": pd.read_csv(disorder / "ensemble_summary.csv"),
        "slopes": pd.read_csv(disorder / "ensemble_slopes.csv"),
        "rebounds": pd.read_csv(disorder / "finest_rebound_audit.csv"),
        "support": pd.read_csv(support / "support_family_checks.csv"),
        "operators": pd.read_csv(
            operators / "operator_candidate_metrics.csv"
        ),
        "conservation": pd.read_csv(
            operators / "conservation_metrics.csv"
        ),
        "autograd": pd.read_csv(autograd / "native_autograd_fd.csv"),
    }


def select_candidates(
    frames: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    slopes = frames["slopes"]
    rebounds = frames["rebounds"]
    ensemble = frames["ensemble"]
    metrics = frames["operators"]
    rows: list[dict[str, Any]] = []
    for operator in TARGET_OPERATORS:
        available = slopes[
            (slopes["support_family"] == "increasing_neighbor")
            & (slopes["operator"] == operator)
            & (slopes["norm"] == "L2")
        ]
        for candidate in sorted(available["candidate"].unique()):
            candidate_slopes = available[
                available["candidate"] == candidate
            ]
            candidate_rebounds = rebounds[
                (rebounds["support_family"] == "increasing_neighbor")
                & (rebounds["operator"] == operator)
                & (rebounds["candidate"] == candidate)
                & (rebounds["norm"] == "L2")
            ]
            full_metrics = metrics[
                (metrics["operator"] == operator)
                & (metrics["candidate"] == candidate)
            ]
            l2_metrics = full_metrics[full_metrics["norm"] == "L2"]
            layouts_complete = (
                set(candidate_slopes["layout"]) == set(REQUIRED_LAYOUTS)
                and set(candidate_rebounds["layout"]) == set(REQUIRED_LAYOUTS)
                and len(l2_metrics) == 300
            )
            endpoint_pass = bool(
                layouts_complete
                and (
                    candidate_slopes[
                        "mean_endpoint_ratio_64_over_16"
                    ]
                    < 1.0
                ).all()
            )
            slope_pass = bool(
                layouts_complete
                and (
                    candidate_slopes[
                        "mean_log_error_log_dx_slope"
                    ]
                    > 0.0
                ).all()
            )
            rebound_pass = bool(
                layouts_complete
                and (~candidate_rebounds["systematic_finest_rebound"]).all()
            )
            finite_pass = bool(
                len(full_metrics) > 0
                and np.isfinite(full_metrics["error"].to_numpy()).all()
            )
            finest = ensemble[
                (ensemble["support_family"] == "increasing_neighbor")
                & (ensemble["resolution"] == 64)
                & (ensemble["layout"].isin(("jitter_05", "jitter_10")))
                & (ensemble["operator"] == operator)
                & (ensemble["candidate"] == candidate)
                & (ensemble["norm"] == "L2")
            ]["mean"].to_numpy(dtype=float)
            geometric_mean = (
                float(np.exp(np.log(finest).mean()))
                if len(finest) == 2 and np.all(finest > 0.0)
                else float("inf")
            )
            variants = full_metrics["operator_variant"].unique()
            rows.append(
                {
                    "operator": operator,
                    "candidate": candidate,
                    "operator_variant": (
                        variants[0] if len(variants) == 1 else "MIXED"
                    ),
                    "all_errors_finite": finite_pass,
                    "all_required_layouts_complete": layouts_complete,
                    "all_endpoint_ratios_below_one": endpoint_pass,
                    "all_ensemble_slopes_positive": slope_pass,
                    "no_systematic_N64_rebound": rebound_pass,
                    "eligible": bool(
                        finite_pass
                        and endpoint_pass
                        and slope_pass
                        and rebound_pass
                    ),
                    "finest_jitter_L2_geometric_mean": geometric_mean,
                    "selected": False,
                }
            )
    selection = pd.DataFrame(rows)
    for operator in TARGET_OPERATORS:
        eligible = selection[
            (selection["operator"] == operator) & selection["eligible"]
        ]
        if not eligible.empty:
            selected_index = eligible[
                "finest_jitter_L2_geometric_mean"
            ].idxmin()
            selection.loc[selected_index, "selected"] = True
    return selection


def evaluate_gates(
    frames: dict[str, pd.DataFrame],
    selection: pd.DataFrame,
    record: dict[str, Any],
) -> tuple[pd.DataFrame, str]:
    evidence: list[dict[str, Any]] = []

    def add(
        gate: str,
        check: str,
        passed: bool,
        observed: Any,
        threshold: str,
        source: str,
    ) -> None:
        evidence.append(
            {
                "gate": gate,
                "check": check,
                "passed": bool(passed),
                "observed": observed,
                "threshold": threshold,
                "source": source,
            }
        )

    per_seed = frames["per_seed"]
    topology_columns = (
        "duplicate_edge_count",
        "missing_self_edge_count",
        "omitted_strict_support_edge_count",
        "nonreciprocal_nonself_edge_count",
        "out_of_bounds_edge_count",
        "unexpected_edge_count",
    )
    for column in topology_columns:
        maximum = float(per_seed[column].max())
        add(
            "C1",
            column,
            maximum == 0.0,
            maximum,
            "0",
            "per_seed_metrics.csv",
        )
    minimum_image = float(per_seed["minimum_image_linf"].max())
    minimum_image_tolerance = (
        64.0 * np.finfo(np.float64).eps * 2.0
    )
    add(
        "C1",
        "minimum_image_linf",
        minimum_image <= minimum_image_tolerance,
        minimum_image,
        f"<= {minimum_image_tolerance:.17g}",
        "per_seed_metrics.csv",
    )
    add(
        "C1",
        "preregistered_static_case_count",
        len(per_seed) == 300,
        len(per_seed),
        "300",
        "per_seed_metrics.csv",
    )

    selected = selection[selection["selected"]]
    add(
        "C2",
        "eligible_selected_operator_count",
        set(selected["operator"]) == set(TARGET_OPERATORS),
        len(selected),
        "4, one for each preregistered principal operator",
        "candidate_selection.csv",
    )
    support = frames["support"]
    increasing = support[support["support_family"] == "increasing_neighbor"]
    add(
        "C2",
        "increasing_family_support_and_neighbors",
        bool(
            len(increasing) == 3
            and increasing["support_strictly_decreases"].all()
            and increasing[
                "ensemble_neighbor_mean_strictly_increases"
            ].all()
        ),
        (
            f"{len(increasing)} layouts; "
            f"neighbor endpoint ratios "
            f"{increasing['neighbor_endpoint_ratio_64_over_16'].min():.6g}"
            f"–{increasing['neighbor_endpoint_ratio_64_over_16'].max():.6g}"
        ),
        "H strictly decreases and ensemble neighbor mean strictly increases",
        "support_family_checks.csv",
    )

    conservation = frames["conservation"]
    c3_thresholds = record["qualification_thresholds"]["C3"]
    for dtype, threshold_key in (
        ("float64", "float64_relative_pair_and_total_force_tolerance"),
        ("float32", "float32_relative_pair_and_total_force_tolerance"),
    ):
        tolerance = float(c3_thresholds[threshold_key])
        subset = conservation[conservation["dtype"] == dtype]
        for metric in (
            "relative_pair_force_residual",
            "relative_total_internal_force",
        ):
            maximum = float(subset[metric].max())
            add(
                "C3",
                f"{dtype}_{metric}",
                maximum <= tolerance,
                maximum,
                f"<= {tolerance:.17g}",
                "conservation_metrics.csv",
            )
        pressure = subset[
            subset["force_type"] == "conservative_pressure"
        ]
        torque_maximum = float(pressure["relative_pair_torque_linf"].max())
        add(
            "C3",
            f"{dtype}_pressure_relative_pair_torque",
            torque_maximum <= tolerance,
            torque_maximum,
            f"<= {tolerance:.17g}",
            "conservation_metrics.csv",
        )
        viscosity = subset[
            subset["force_type"] == "conservative_viscosity"
        ]
        gamma_residual = float(
            viscosity["relative_gamma_symmetry_residual"].max()
        )
        add(
            "C3",
            f"{dtype}_Gamma_symmetry",
            gamma_residual <= tolerance,
            gamma_residual,
            f"<= {tolerance:.17g}",
            "conservation_metrics.csv",
        )
    viscosity = conservation[
        conservation["force_type"] == "conservative_viscosity"
    ]
    eps = np.where(
        viscosity["dtype"].to_numpy() == "float32",
        np.finfo(np.float32).eps,
        np.finfo(np.float64).eps,
    )
    power_allowance = (
        64.0
        * eps
        * np.maximum(
            np.abs(viscosity["pair_direct_viscous_power"].to_numpy()),
            1.0,
        )
    )
    power_pass = bool(
        (
            viscosity["accumulated_viscous_power"].to_numpy()
            <= power_allowance
        ).all()
        and (
            viscosity["pair_direct_viscous_power"].to_numpy()
            <= power_allowance
        ).all()
    )
    add(
        "C3",
        "viscous_power_nonpositive",
        power_pass,
        float(viscosity["accumulated_viscous_power"].max()),
        "<= dtype-scaled roundoff allowance",
        "conservation_metrics.csv",
    )
    required_cases = bool(
        (
            (conservation["force_type"] == "conservative_pressure")
            & (conservation["density_case"] == "variable_05")
            & (conservation["field_case"] == "mixed_sign")
        ).any()
        and (
            (conservation["force_type"] == "conservative_viscosity")
            & (conservation["density_case"] == "variable_05")
        ).any()
    )
    add(
        "C3",
        "required_mixed_pressure_and_variable_density_cases",
        required_cases,
        required_cases,
        "both present",
        "conservation_metrics.csv",
    )

    autograd = frames["autograd"]
    short = autograd[autograd["steps"].isin((1, 3, 5, 8))]
    long = autograd[autograd["steps"] == 16]
    maximum_relative = float(short["relative_difference"].max())
    c4_maximum = float(
        record["qualification_thresholds"]["C4"][
            "steps_1_3_5_8_AD_FD_relative_difference_maximum"
        ]
    )
    add(
        "C4",
        "steps_1_3_5_8_finite_nonzero",
        bool(short["finite"].all() and short["nonzero"].all()),
        f"{int((short['finite'] & short['nonzero']).sum())}/{len(short)}",
        "16/16",
        "native_autograd_fd.csv",
    )
    add(
        "C4",
        "steps_1_3_5_8_AD_FD_relative_difference",
        maximum_relative <= c4_maximum,
        maximum_relative,
        f"<= {c4_maximum:.17g}",
        "native_autograd_fd.csv",
    )
    add(
        "C4",
        "step_16_finite_nonzero",
        bool(
            len(long) == 4
            and long["finite"].all()
            and long["nonzero"].all()
        ),
        f"{int((long['finite'] & long['nonzero']).sum())}/{len(long)}",
        "4/4",
        "native_autograd_fd.csv",
    )
    add(
        "C4",
        "topology_differentiability_not_claimed",
        bool((~autograd["topology_differentiability_claimed"]).all()),
        bool(autograd["topology_differentiability_claimed"].any()),
        "False",
        "native_autograd_fd.csv",
    )

    frame = pd.DataFrame(evidence)
    gates = {
        gate: bool(group["passed"].all())
        for gate, group in frame.groupby("gate")
    }
    if all(gates.get(gate, False) for gate in ("C1", "C2", "C3", "C4")):
        status = "C1_PASS_C2_PASS_C3_PASS_C4_PASS"
    elif gates.get("C1", False) and not gates.get("C2", False):
        status = "C1_PASS_C2_CONDITIONAL"
    elif not gates.get("C3", False):
        status = "C3_FAIL"
    elif not gates.get("C4", False):
        status = "C4_FAIL"
    else:
        status = "REQUALIFICATION_FAIL"
    return frame, status


def run(experiment_root: Path) -> str:
    _, record = load_preregistered_design()
    frames = _read_results(experiment_root)
    selection = select_candidates(frames)
    evidence, status = evaluate_gates(frames, selection, record)
    output = (
        experiment_root
        / "stage_01c_operator_candidates"
        / "results"
    )
    selection.to_csv(output / "candidate_selection.csv", index=False)
    evidence.to_csv(output / "stage01c_gate_evidence.csv", index=False)
    (output / "stage01c_gate_status.txt").write_text(
        status + "\n",
        encoding="utf-8",
    )
    print(status)
    return status


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--experiment-root",
        type=Path,
        default=PROJECT_ROOT / "06_experiments",
    )
    args = parser.parse_args()
    run(args.experiment_root.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
