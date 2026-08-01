"""Preregistered Stage 01D-R2 attribution analysis and status selection."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOLVER_ROOT = PROJECT_ROOT / "01_solver"
if str(SOLVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SOLVER_ROOT))

from resource_diagnostics.edge_working_set_model import robust_edge_step_fit  # noqa: E402


EXPERIMENT_ROOT = PROJECT_ROOT / "06_experiments" / "stage_01dr2_storage_attribution"
CONFIG_PATH = EXPERIMENT_ROOT / "configs" / "preregistered_storage_attribution.yml"
RESULTS_ROOT = EXPERIMENT_ROOT / "results"
FIGURES_ROOT = EXPERIMENT_ROOT / "figures"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path.relative_to(PROJECT_ROOT)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"no rows for {path.name}")
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path.relative_to(PROJECT_ROOT)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(value), indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path.relative_to(PROJECT_ROOT)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _bool(value: Any) -> bool:
    return str(value).lower() == "true"


def _summary(run_id: str) -> dict[str, Any]:
    path = RESULTS_ROOT / "run_summaries" / f"{run_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _run_ids(control: str, *, include_confirmation: bool = False) -> list[str]:
    values = [f"stage01dr2_{control.lower()}_r{repeat}" for repeat in (1, 2, 3)]
    if control == "D" and include_confirmation:
        confirmation = "stage01dr2_d_confirm_2000"
        if (RESULTS_ROOT / "run_summaries" / f"{confirmation}.json").exists():
            values.append(confirmation)
    return values


def _inventory_analysis(configuration: Mapping[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    rows: list[dict[str, Any]] = []
    all_pass = True
    for repeat, run_id in enumerate(_run_ids("A"), start=1):
        summary = _summary(run_id)
        passed = bool(
            summary.get("status") == "PASS"
            and int(summary["lightweight_tensor_count_delta"]) == int(configuration["inventory_self_test"]["required_tensor_count_delta"])
            and int(summary["lightweight_unique_storage_bytes_delta"]) == int(configuration["inventory_self_test"]["required_unique_storage_bytes_delta"])
            and summary.get("view_and_base_deduplication_pass") is True
            and summary.get("storage_key_contract_pass") is True
        )
        all_pass = all_pass and passed
        rows.append(
            {
                "run_id": run_id,
                "repeat": repeat,
                "iterations": summary["iterations"],
                "tensor_count_delta": summary["lightweight_tensor_count_delta"],
                "unique_storage_bytes_delta": summary["lightweight_unique_storage_bytes_delta"],
                "fixture_tensor_count": summary["fixture_tensor_count"],
                "fixture_unique_storage_count": summary["fixture_unique_storage_count"],
                "fixture_unique_storage_bytes": summary["fixture_unique_storage_bytes"],
                "view_base_deduplication_pass": summary["view_and_base_deduplication_pass"],
                "inventory_self_retention_pass": summary["inventory_self_retention_pass"],
                "pass": passed,
            }
        )
    return rows, all_pass


def _lifetime_analysis() -> tuple[list[dict[str, Any]], bool]:
    rows: list[dict[str, Any]] = []
    all_pass = True
    for control in ("B", "C", "D"):
        for run_id in _run_ids(control, include_confirmation=control == "D"):
            samples = [row for row in _read_csv(RESULTS_ROOT / "weakref_lifetime" / f"{run_id}.csv") if _bool(row["gc_collected"])]
            maximum_count = max(int(row["old_survivor_storage_count"]) for row in samples)
            maximum_bytes = max(int(row["old_survivor_bytes"]) for row in samples)
            maximum_same_slot = max(int(row["same_slot_multiple_generation_count"]) for row in samples)
            maximum_age2 = max(int(row["age2_alive_tensor_reference_count"]) for row in samples)
            passed = maximum_count == 0 and maximum_bytes == 0 and maximum_same_slot == 0
            all_pass = all_pass and passed
            rows.append(
                {
                    "run_id": run_id,
                    "control": control,
                    "gc_checkpoint_count": len(samples),
                    "maximum_age2_alive_tensor_reference_count": maximum_age2,
                    "maximum_old_survivor_storage_count": maximum_count,
                    "maximum_old_survivor_bytes": maximum_bytes,
                    "maximum_same_slot_multiple_generation_count": maximum_same_slot,
                    "explicit_referrer_chain_count": _summary(run_id).get("referrer_chain_count", 0),
                    "pass": passed,
                }
            )
    return rows, all_pass


def _fixed_topology_analysis() -> tuple[list[dict[str, Any]], bool]:
    rows: list[dict[str, Any]] = []
    all_pass = True
    for control in ("B", "C"):
        for run_id in _run_ids(control):
            ledger = _read_csv(RESULTS_ROOT / "ledger_summary" / f"{run_id}.csv")
            edge_values = {int(row["directed_edge_count"]) for row in ledger}
            tensor_count_delta = int(ledger[-1]["live_tensor_count"]) - int(ledger[0]["live_tensor_count"])
            unknown_delta = int(ledger[-1]["unknown_live_bytes"]) - int(ledger[0]["unknown_live_bytes"])
            old_delta = int(ledger[-1]["old_survivor_bytes"]) - int(ledger[0]["old_survivor_bytes"])
            passed = len(edge_values) == 1 and tensor_count_delta == 0 and unknown_delta == 0 and old_delta == 0
            all_pass = all_pass and passed
            rows.append(
                {
                    "run_id": run_id,
                    "control": control,
                    "sample_count": len(ledger),
                    "unique_directed_edge_counts": len(edge_values),
                    "directed_edge_count": min(edge_values),
                    "live_tensor_count_delta": tensor_count_delta,
                    "unknown_live_bytes_delta": unknown_delta,
                    "old_survivor_bytes_delta": old_delta,
                    "pass": passed,
                }
            )
    return rows, all_pass


def _model_analysis(configuration: Mapping[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    model_config = configuration["working_set_model"]
    rows: list[dict[str, Any]] = []
    all_pass = True
    for index, run_id in enumerate(_run_ids("D", include_confirmation=True)):
        ledger = _read_csv(RESULTS_ROOT / "ledger_summary" / f"{run_id}.csv")
        steps = [float(row["step"]) for row in ledger]
        edges = [float(row["directed_edge_count"]) for row in ledger]
        total = [float(row["live_total_bytes"]) for row in ledger]
        unknown = [float(row["unknown_live_bytes"]) for row in ledger]
        total_fit = robust_edge_step_fit(
            steps=steps,
            edge_counts=edges,
            values=total,
            bootstrap_samples=int(model_config["bootstrap_samples"]),
            seed=int(model_config["bootstrap_seed"]) + index,
        )
        unknown_fit = robust_edge_step_fit(
            steps=steps,
            edge_counts=edges,
            values=unknown,
            bootstrap_samples=int(model_config["bootstrap_samples"]),
            seed=int(model_config["bootstrap_seed"]) + 100 + index,
        )
        total_near_zero = abs(total_fit.step_coefficient) <= float(model_config["adjusted_step_near_zero_absolute_bytes_per_step"])
        total_ci_zero = total_fit.step_ci95_lower <= 0.0 <= total_fit.step_ci95_upper
        unknown_near_zero = abs(unknown_fit.step_coefficient) <= float(model_config["unknown_step_near_zero_absolute_bytes_per_step"])
        unknown_ci_zero = unknown_fit.step_ci95_lower <= 0.0 <= unknown_fit.step_ci95_upper
        passed = bool(total_near_zero and total_ci_zero and unknown_near_zero and unknown_ci_zero)
        all_pass = all_pass and passed
        rows.append(
            {
                "run_id": run_id,
                **total_fit.as_dict(prefix="total_"),
                **unknown_fit.as_dict(prefix="unknown_"),
                "total_adjusted_step_near_zero": total_near_zero,
                "total_step_ci_includes_zero": total_ci_zero,
                "unknown_adjusted_step_near_zero": unknown_near_zero,
                "unknown_step_ci_includes_zero": unknown_ci_zero,
                "pass": passed,
            }
        )
    return rows, all_pass


def _numerical_analysis() -> tuple[list[dict[str, Any]], bool]:
    rows: list[dict[str, Any]] = []
    all_pass = True
    for run_id in _run_ids("D", include_confirmation=True):
        samples = _read_csv(RESULTS_ROOT / "numerical_regression" / f"{run_id}.csv")
        passed_rows = sum(_bool(row["all_state_values_finite"]) and _bool(row["all_fields_bitwise_equal"]) and float(row["maximum_absolute_difference"]) == 0.0 for row in samples)
        passed = len(samples) == 5 and passed_rows == 5
        all_pass = all_pass and passed
        rows.append(
            {
                "run_id": run_id,
                "rows": len(samples),
                "bitwise_and_finite_rows": passed_rows,
                "maximum_absolute_difference": max(float(row["maximum_absolute_difference"]) for row in samples),
                "pass": passed,
            }
        )
    return rows, all_pass


def _all_workers_complete() -> tuple[bool, int, int]:
    expected = _run_ids("A") + _run_ids("B") + _run_ids("C") + _run_ids("D")
    confirmation = "stage01dr2_d_confirm_2000"
    if (RESULTS_ROOT / "run_summaries" / f"{confirmation}.json").exists():
        expected.append(confirmation)
    passed = 0
    for run_id in expected:
        path = RESULTS_ROOT / "run_summaries" / f"{run_id}.json"
        if not path.exists():
            continue
        summary = json.loads(path.read_text(encoding="utf-8"))
        passed += int(summary.get("status") == "PASS" and int(summary.get("completed_steps", 0)) == int(summary.get("planned_steps", -1)))
    return passed == len(expected), passed, len(expected)


def _figures(inventory_rows: list[dict[str, Any]], lifetime_rows: list[dict[str, Any]]) -> None:
    FIGURES_ROOT.mkdir(parents=True, exist_ok=True)
    for name in ("stage01dr2_inventory_validation.png", "stage01dr2_edge_attribution.png", "stage01dr2_old_survivor_lifetime.png"):
        if (FIGURES_ROOT / name).exists():
            raise RuntimeError(f"refusing to overwrite figure {name}")
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    ax.bar([row["run_id"] for row in inventory_rows], [row["unique_storage_bytes_delta"] for row in inventory_rows], color="#4477AA")
    ax.axhline(0.0, color="black", linewidth=0.8)
    ax.set_ylabel("static unique-storage delta (B)")
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(FIGURES_ROOT / "stage01dr2_inventory_validation.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    colors = ("#4477AA", "#EE6677", "#228833", "#CCBB44")
    for color, run_id in zip(colors, _run_ids("D", include_confirmation=True)):
        ledger = _read_csv(RESULTS_ROOT / "ledger_summary" / f"{run_id}.csv")
        ax.scatter(
            [int(row["directed_edge_count"]) for row in ledger],
            [int(row["live_total_bytes"]) / 1.0e6 for row in ledger],
            s=15,
            alpha=0.7,
            label=run_id,
            color=color,
        )
    ax.set_xlabel("directed edge count")
    ax.set_ylabel("live unique tensor storage (MB)")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(FIGURES_ROOT / "stage01dr2_edge_attribution.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    ax.bar([row["run_id"] for row in lifetime_rows], [row["maximum_old_survivor_bytes"] for row in lifetime_rows], color="#228833")
    ax.set_ylabel("maximum old-survivor storage (B)")
    ax.tick_params(axis="x", rotation=75, labelsize=6)
    fig.tight_layout()
    fig.savefig(FIGURES_ROOT / "stage01dr2_old_survivor_lifetime.png", dpi=180)
    plt.close(fig)


def main() -> int:
    configuration = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    outputs = [
        RESULTS_ROOT / "inventory_validation_summary.csv",
        RESULTS_ROOT / "weakref_lifetime_summary.csv",
        RESULTS_ROOT / "fixed_topology_summary.csv",
        RESULTS_ROOT / "edge_working_set_models.csv",
        RESULTS_ROOT / "numerical_regression_summary.csv",
        RESULTS_ROOT / "attribution_gate_evidence.csv",
        RESULTS_ROOT / "analysis_summary.json",
        RESULTS_ROOT / "stage01dr2_attribution_status.txt",
    ]
    if any(path.exists() for path in outputs):
        raise RuntimeError("analysis outputs already exist")
    inventory_rows, inventory_pass = _inventory_analysis(configuration)
    workers_pass, worker_pass_count, worker_count = _all_workers_complete()
    if inventory_pass:
        lifetime_rows, lifetime_pass = _lifetime_analysis()
        fixed_rows, fixed_pass = _fixed_topology_analysis()
        model_rows, model_pass = _model_analysis(configuration)
        numerical_rows, numerical_pass = _numerical_analysis()
    else:
        lifetime_rows, fixed_rows, model_rows, numerical_rows = [], [], [], []
        lifetime_pass = fixed_pass = model_pass = numerical_pass = False

    explicit_retention = bool(
        lifetime_rows
        and any(
            int(row["maximum_old_survivor_storage_count"]) > 0
            or int(row["maximum_old_survivor_bytes"]) > 0
            or int(row["maximum_same_slot_multiple_generation_count"]) > 0
            for row in lifetime_rows
        )
    )
    if not inventory_pass:
        status = "INVENTORY_INSTRUMENTATION_BIAS"
    elif explicit_retention:
        status = "RETENTION_CONFIRMED_UNFIXED"
    elif workers_pass and lifetime_pass and fixed_pass and model_pass and numerical_pass:
        status = "ATTRIBUTED_TO_DYNAMIC_WORKING_SET"
    else:
        status = "ATTRIBUTION_UNRESOLVED"
    if status not in set(configuration["allowed_statuses"]):
        raise RuntimeError("selected status is not preregistered")
    eligible = status in set(configuration["stage01d2_application_eligible_statuses"])

    if inventory_rows:
        _write_csv(outputs[0], inventory_rows)
    if lifetime_rows:
        _write_csv(outputs[1], lifetime_rows)
        _write_csv(outputs[2], fixed_rows)
        _write_csv(outputs[3], model_rows)
        _write_csv(outputs[4], numerical_rows)
    gates = [
        {"gate": "A", "name": "inventory_self_validation", "passed": inventory_pass, "observed": f"{sum(row['pass'] for row in inventory_rows)}/3", "required": "3/3"},
        {"gate": "B", "name": "all_required_workers_complete", "passed": workers_pass, "observed": f"{worker_pass_count}/{worker_count}", "required": f"{worker_count}/{worker_count}"},
        {"gate": "C", "name": "weakref_old_survivor_absent", "passed": lifetime_pass, "observed": "no old storage" if lifetime_pass else "survivor or missing", "required": "zero"},
        {"gate": "D", "name": "fixed_topology_controls_constant", "passed": fixed_pass, "observed": f"{sum(row['pass'] for row in fixed_rows)}/{len(fixed_rows)}" if fixed_rows else "not run", "required": "6/6"},
        {"gate": "E", "name": "edge_adjusted_step_terms_near_zero", "passed": model_pass, "observed": f"{sum(row['pass'] for row in model_rows)}/{len(model_rows)}" if model_rows else "not run", "required": "all D runs"},
        {"gate": "F", "name": "frozen_first_four_state_regression", "passed": numerical_pass, "observed": f"{sum(row['pass'] for row in numerical_rows)}/{len(numerical_rows)}" if numerical_rows else "not run", "required": "all D runs"},
        {"gate": "STATUS", "name": "unique_attribution_status", "passed": True, "observed": status, "required": json.dumps(configuration["allowed_statuses"], separators=(",", ":"))},
    ]
    _write_csv(outputs[5], gates)
    summary = {
        "schema_version": "sph-pio-poc.stage01dr2.analysis.v1",
        "config_sha256": _sha256(CONFIG_PATH),
        "status": status,
        "stage01d2_application_eligible": bool(eligible),
        "inventory_pass": bool(inventory_pass),
        "all_workers_complete": bool(workers_pass),
        "worker_pass_count": int(worker_pass_count),
        "worker_count": int(worker_count),
        "lifetime_pass": bool(lifetime_pass),
        "fixed_topology_pass": bool(fixed_pass),
        "edge_model_pass": bool(model_pass),
        "numerical_regression_pass": bool(numerical_pass),
        "explicit_retention_detected": bool(explicit_retention),
        "retention_fix_applied": False,
        "old_stage01d_status": "V2_FAIL",
        "old_stage01dr_status": "RESOURCE_FAIL_LINEAR_GROWTH",
        "stage01d2_started": False,
        "v3_started": False,
        "stage02_started": False,
    }
    _write_json(outputs[6], summary)
    _write_text(outputs[7], status + "\n")
    if lifetime_rows:
        _figures(inventory_rows, lifetime_rows)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
