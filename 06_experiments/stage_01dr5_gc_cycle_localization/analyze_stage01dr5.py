"""Analyze R5 GC envelopes, provenance, isolation, and unique status."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ROOT = PROJECT_ROOT / "06_experiments" / "stage_01dr5_gc_cycle_localization"
CONFIG_PATH = EXPERIMENT_ROOT / "configs" / "preregistered_gc_cycle_localization.yml"
RESULTS_ROOT = EXPERIMENT_ROOT / "results"
FIGURES_ROOT = EXPERIMENT_ROOT / "figures"
R4_RESULTS = PROJECT_ROOT / "06_experiments" / "stage_01dr4_weakref_semantics" / "results"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path.relative_to(PROJECT_ROOT)}")
    if not rows:
        raise ValueError(f"no rows for {path.name}")
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path.relative_to(PROJECT_ROOT)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(value), indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def _linear_fit(xs: Iterable[float], ys: Iterable[float]) -> tuple[float, float]:
    x = list(xs)
    y = list(ys)
    mean_x = sum(x) / len(x)
    mean_y = sum(y) / len(y)
    denominator = sum((value - mean_x) ** 2 for value in x)
    slope = 0.0 if denominator == 0.0 else sum((a - mean_x) * (b - mean_y) for a, b in zip(x, y)) / denominator
    predicted = [mean_y + slope * (value - mean_x) for value in x]
    total = sum((value - mean_y) ** 2 for value in y)
    residual = sum((value - estimate) ** 2 for value, estimate in zip(y, predicted))
    r_squared = 1.0 if total == 0.0 else max(0.0, 1.0 - residual / total)
    return slope, r_squared


def _gc_summary(mode: str, repeat: int) -> dict[str, Any]:
    run_id = f"stage01dr5_{mode.lower()}_r{repeat}"
    rows = _read_csv(RESULTS_ROOT / "lifetime_curves" / f"{run_id}.csv")
    steps = [int(row["step"]) for row in rows]
    retired = [int(row["retired_old_survivor_count"]) for row in rows]
    same_slot = [int(row["same_slot_multigeneration_count"]) for row in rows]
    slope, r_squared = _linear_fit(steps, retired)
    midpoint = len(rows) // 2
    collection_totals = [
        sum(int(row[f"gc_collections_generation_{generation}"]) for generation in (0, 1, 2))
        for row in rows
    ]
    events = [
        index for index in range(1, len(rows))
        if collection_totals[index] > collection_totals[index - 1]
    ]
    post_collection_values = [retired[index] for index in events]
    checkpoints = [
        index for index, row in enumerate(rows)
        if int(row["manual_gc_collected_objects"]) > 0 or int(row["step"]) % 25 == 0
    ]
    return {
        "run_id": run_id,
        "mode": mode,
        "repeat": repeat,
        "steps": len(rows),
        "maximum_retired_count": max(retired),
        "maximum_retired_bytes": max(int(row["retired_old_survivor_bytes"]) for row in rows),
        "maximum_same_slot_count": max(same_slot),
        "maximum_retired_generations_one_slot": max(int(row["maximum_retired_generations_in_one_slot"]) for row in rows),
        "first_half_retired_peak": max(retired[:midpoint]),
        "second_half_retired_peak": max(retired[midpoint:]),
        "retired_linear_slope_per_step": slope,
        "retired_linear_r_squared": r_squared,
        "natural_gc_collection_events": len(events),
        "maximum_post_natural_collection_retired": max(post_collection_values, default=-1),
        "manual_gc_checkpoint_zero_fraction": (
            sum(retired[index] == 0 for index in checkpoints) / len(checkpoints)
            if checkpoints else 0.0
        ),
        "manual_gc_total_wall_seconds": sum(float(row["manual_gc_wall_seconds"]) for row in rows),
        "total_step_wall_seconds": sum(float(row["step_wall_seconds"]) for row in rows),
        "maximum_rss_bytes": max(int(row["current_rss_bytes"]) for row in rows),
        "rss_delta_bytes": int(rows[-1]["current_rss_bytes"]) - int(rows[0]["current_rss_bytes"]),
        "current_tensor_bytes_delta": int(rows[-1]["live_current_tensor_bytes"]) - int(rows[0]["live_current_tensor_bytes"]),
    }


def _evidence_identity(configuration: Mapping[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    expected = configuration["r4_frozen_evidence"]
    rows: list[dict[str, Any]] = []
    passed = True
    for filename, digest in expected.items():
        path = R4_RESULTS / filename
        observed = _sha256(path)
        identity = observed == str(digest)
        passed = passed and identity
        rows.append(
            {
                "filename": filename,
                "expected_sha256": digest,
                "observed_sha256": observed,
                "identity_pass": identity,
            }
        )
    return rows, passed


def _provenance_outputs() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], bool]:
    source = RESULTS_ROOT / "retired_instances" / "stage01dr5_l1_r1.csv"
    instances: list[dict[str, Any]] = _read_csv(source) if source.exists() else []
    if not instances:
        instances = [{"semantic_slot": "none_observed", "tensor_object_id": -1, "storage_key": "none"}]
    slots: dict[str, list[dict[str, Any]]] = {}
    for row in instances:
        slots.setdefault(row["semantic_slot"], []).append(row)
    slot_rows = [
        {
            "semantic_slot": slot,
            "retired_instance_count": len(rows),
            "unique_storage_count": len({row.get("storage_key") for row in rows}),
            "first_retirement_step": min(int(row.get("retirement_step", -1)) for row in rows),
            "last_alive_step": max(int(row.get("last_alive_step", -1)) for row in rows),
            "owner_types": json.dumps(sorted({row.get("python_owner_object_type", "unresolved") for row in rows}), separators=(",", ":")),
            "owner_categories": json.dumps(sorted({row.get("owner_category", "unresolved") for row in rows}), separators=(",", ":")),
        }
        for slot, rows in sorted(slots.items())
    ]
    graph_path = RESULTS_ROOT / "referrer_graphs" / "stage01dr5_l1_r1.json"
    graphs = _read_json(graph_path) if graph_path.exists() else {"run_id": "stage01dr5_l1_r1", "graphs": []}
    localized = any(bool(graph.get("cycle_localized")) for graph in graphs["graphs"])
    return instances, slot_rows, graphs, localized


def _numerical_identity() -> tuple[list[dict[str, Any]], bool]:
    reference_rows = _read_csv(RESULTS_ROOT / "numerical_hashes" / "stage01dr5_g1_r1.csv")
    reference = {int(row["step"]): row for row in reference_rows}
    rows: list[dict[str, Any]] = []
    passed = True
    for path in sorted((RESULTS_ROOT / "numerical_hashes").glob("*.csv")):
        observed = _read_csv(path)
        identical = len(observed) == 5 and all(
            row["all_finite"].lower() == "true"
            and all(row[key] == reference[int(row["step"])][key] for key in row if key.endswith("_sha256"))
            for row in observed
        )
        passed = passed and identical
        rows.append({"run_id": path.stem, "rows": len(observed), "bitwise_hash_identity": identical})
    return rows, passed


def _figures(gc_rows: list[dict[str, Any]], isolation_rows: list[dict[str, Any]]) -> None:
    FIGURES_ROOT.mkdir(parents=True, exist_ok=True)
    paths = (FIGURES_ROOT / "gc_retired_curves.png", FIGURES_ROOT / "instrumentation_isolation.png")
    if any(path.exists() for path in paths):
        raise RuntimeError("R5 figures already exist")
    fig, axes = plt.subplots(3, 1, figsize=(8, 9), sharex=True)
    for axis, mode in zip(axes, ("G1", "G2", "G3")):
        for repeat in (1, 2, 3):
            rows = _read_csv(RESULTS_ROOT / "lifetime_curves" / f"stage01dr5_{mode.lower()}_r{repeat}.csv")
            axis.plot([int(row["step"]) for row in rows], [int(row["retired_old_survivor_count"]) for row in rows], linewidth=0.8, label=f"{mode}-r{repeat}")
        axis.set_ylabel("retired storages")
        axis.legend(ncol=3, fontsize=8)
    axes[-1].set_xlabel("accepted step")
    fig.tight_layout()
    fig.savefig(paths[0], dpi=180)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 4))
    modes = [f"I{index}" for index in range(5)]
    values = [max(int(row["maximum_retired_count"]) for row in isolation_rows if row["mode"] == mode) for mode in modes]
    ax.bar(modes, values, color="#4477AA")
    ax.set_ylabel("maximum retired storages (-1 = off-path)")
    fig.tight_layout()
    fig.savefig(paths[1], dpi=180)
    plt.close(fig)


def main() -> int:
    outputs = {
        "gc": RESULTS_ROOT / "gc_mode_summary.csv",
        "isolation": RESULTS_ROOT / "instrumentation_isolation_summary.csv",
        "instances": RESULTS_ROOT / "retired_object_instances.csv",
        "slots": RESULTS_ROOT / "retired_slot_summary.csv",
        "graphs": RESULTS_ROOT / "referrer_graph_summary.json",
        "identity": RESULTS_ROOT / "r4_evidence_identity.csv",
        "numeric": RESULTS_ROOT / "numerical_regression_summary.csv",
        "gates": RESULTS_ROOT / "r5_gate_evidence.csv",
        "analysis": RESULTS_ROOT / "analysis_summary.json",
        "status": RESULTS_ROOT / "stage01dr5_status.txt",
    }
    if any(path.exists() for path in outputs.values()):
        raise RuntimeError("R5 analysis outputs already exist")
    configuration = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    classification = configuration["classification"]
    gc_rows = [_gc_summary(mode, repeat) for repeat in (1, 2, 3) for mode in ("G1", "G2", "G3")]
    isolation_rows: list[dict[str, Any]] = []
    for repeat in (1, 2, 3):
        for mode in configuration["isolation"]["modes"]:
            run_id = f"stage01dr5_{mode.lower()}_r{repeat}"
            summary = _read_json(RESULTS_ROOT / "run_summaries" / f"{run_id}.json")
            curves = _read_csv(RESULTS_ROOT / "lifetime_curves" / f"{run_id}.csv")
            rss_slope, rss_r2 = _linear_fit(
                [int(row["step"]) for row in curves],
                [int(row["current_rss_bytes"]) for row in curves],
            )
            external_drift = 0
            external_path = RESULTS_ROOT / "external_type_counts" / f"{run_id}.csv"
            if external_path.exists():
                external = _read_csv(external_path)
                external_drift = int(external[-1]["tracked_tensor_storage_bytes"]) - int(external[0]["tracked_tensor_storage_bytes"])
            isolation_rows.append(
                {
                    "run_id": run_id,
                    "mode": mode,
                    "repeat": repeat,
                    "components": json.dumps(summary["components"], separators=(",", ":")),
                    "maximum_retired_count": summary["maximum_retired_old_survivor_count"],
                    "maximum_same_slot_count": summary["maximum_same_slot_multigeneration_count"],
                    "rss_slope_bytes_per_step": rss_slope,
                    "rss_slope_r_squared": rss_r2,
                    "current_tensor_bytes_delta": summary["current_tensor_bytes_delta"],
                    "external_tracked_tensor_bytes_delta": external_drift,
                    "state_finite": summary["all_state_values_finite"],
                }
            )
    evidence_rows, evidence_pass = _evidence_identity(configuration)
    instances, slots, graphs, cycle_localized = _provenance_outputs()
    numerical_rows, numerical_pass = _numerical_identity()
    campaign = _read_json(RESULTS_ROOT / "campaign_summary.json")
    provenance_pass = bool(
        campaign["expected_processes"] == 25
        and campaign["observed_processes"] == 25
        and campaign["pass_processes"] == 25
        and campaign["all_processes_reclaimed"]
        and numerical_pass
        and evidence_pass
    )
    g1 = [row for row in gc_rows if row["mode"] == "G1"]
    g2 = [row for row in gc_rows if row["mode"] == "G2"]
    g3 = [row for row in gc_rows if row["mode"] == "G3"]
    disabled_linear = all(
        float(row["retired_linear_slope_per_step"]) >= float(classification["disabled_gc_minimum_retired_slope_storage_per_step"])
        and float(row["retired_linear_r_squared"]) >= float(classification["disabled_gc_minimum_r_squared"])
        for row in g2
    )
    default_bounded = all(
        int(row["natural_gc_collection_events"]) >= int(classification["default_gc_required_natural_collection_events"])
        and int(row["second_half_retired_peak"]) <= int(row["first_half_retired_peak"]) + int(classification["default_gc_second_half_peak_allowance_storages"])
        for row in g1
    )
    default_unbounded = all(
        float(row["retired_linear_slope_per_step"]) >= float(classification["default_gc_unbounded_slope_storage_per_step"])
        and int(row["second_half_retired_peak"]) > int(row["first_half_retired_peak"]) + int(classification["default_gc_second_half_peak_allowance_storages"])
        for row in g1
    )
    periodic_zero = all(
        math.isclose(float(row["manual_gc_checkpoint_zero_fraction"]), float(classification["periodic_gc_required_checkpoint_zero_fraction"]), abs_tol=1.0e-12)
        for row in g3
    )
    i0_stable = all(
        abs(int(row["external_tracked_tensor_bytes_delta"])) <= int(classification["isolation_tensor_byte_drift_allowance"])
        for row in isolation_rows if row["mode"] == "I0"
    )
    tracker_modes_signal = any(
        int(row["maximum_retired_count"]) > 0
        for row in isolation_rows if row["mode"] in {"I1", "I4"}
    )
    instrumentation_isolated = bool(i0_stable and tracker_modes_signal)
    fix_implemented = bool(configuration["allowed_fixes"]["fix_implemented_in_preregistered_campaign"])
    if default_unbounded:
        status = "R5_UNBOUNDED_RETENTION_CONFIRMED"
    elif instrumentation_isolated and fix_implemented:
        status = "R5_INSTRUMENTATION_RETENTION_IDENTIFIED_AND_REMOVED"
    elif default_bounded and disabled_linear and periodic_zero and not cycle_localized:
        status = "R5_BOUNDED_GC_DELAY_CONFIRMED"
    else:
        status = "R5_ATTRIBUTION_UNRESOLVED"
    if status not in set(configuration["allowed_statuses"]):
        raise RuntimeError("R5 status is not preregistered")
    gates = [
        {"gate": "R1", "name": "retired_object_inventory", "passed": len(instances) > 0, "observed": len(instances), "required": ">0 itemized instances"},
        {"gate": "R2", "name": "pre_gc_referrer_graph", "passed": len(graphs["graphs"]) > 0, "observed": f"graphs={len(graphs['graphs'])} cycles={cycle_localized}", "required": "representative type graphs depth<=4"},
        {"gate": "R3", "name": "gc_schedule_contrast", "passed": default_bounded and disabled_linear and periodic_zero, "observed": f"G1bounded={default_bounded} G2linear={disabled_linear} G3zero={periodic_zero}", "required": "bounded/linear/zero"},
        {"gate": "R4", "name": "instrumentation_isolation", "passed": i0_stable, "observed": f"I0stable={i0_stable} trackerSignal={tracker_modes_signal}", "required": "solver-only current storage bounded"},
        {"gate": "R5", "name": "numerical_and_provenance", "passed": provenance_pass, "observed": f"workers={campaign['pass_processes']}/25 numeric={sum(row['bitwise_hash_identity'] for row in numerical_rows)}/{len(numerical_rows)}", "required": "25/25 reclaimed and hashes equal"},
        {"gate": "STATUS", "name": "unique_r5_status", "passed": True, "observed": status, "required": json.dumps(configuration["allowed_statuses"], separators=(",", ":"))},
    ]
    _write_csv(outputs["gc"], gc_rows)
    _write_csv(outputs["isolation"], isolation_rows)
    _write_csv(outputs["instances"], instances)
    _write_csv(outputs["slots"], slots)
    _write_json(outputs["graphs"], graphs)
    _write_csv(outputs["identity"], evidence_rows)
    _write_csv(outputs["numeric"], numerical_rows)
    _write_csv(outputs["gates"], gates)
    analysis = {
        "schema_version": "sph-pio-poc.stage01dr5.analysis.v1",
        "config_sha256": _sha256(CONFIG_PATH),
        "status": status,
        "default_gc_bounded": default_bounded,
        "disabled_gc_linear_growth": disabled_linear,
        "periodic_gc_checkpoint_zero": periodic_zero,
        "instrumentation_isolated": instrumentation_isolated,
        "explicit_cycle_localized": cycle_localized,
        "fix_implemented": fix_implemented,
        "numerical_identity_pass": numerical_pass,
        "evidence_identity_pass": evidence_pass,
        "stage01d2_application_eligible": status in set(configuration["stage01d2_application_eligible_statuses"]),
        "extra_resource_audit_eligible": status in set(configuration["extra_resource_audit_eligible_statuses"]),
        "stage01d_status": "V2_FAIL",
        "stage01dr_status": "RESOURCE_FAIL_LINEAR_GROWTH",
        "stage01dr2_status": "ATTRIBUTION_UNRESOLVED",
        "stage01dr3_status": "R3_CONFIRMATION_UNRESOLVED",
        "stage01dr4_status": "R4_RETENTION_REDETECTED",
        "stage01d2_started": False,
        "v3_started": False,
        "stage02_started": False,
    }
    _write_json(outputs["analysis"], analysis)
    outputs["status"].write_text(status + "\n", encoding="utf-8")
    _figures(gc_rows, isolation_rows)
    print(json.dumps(analysis, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
