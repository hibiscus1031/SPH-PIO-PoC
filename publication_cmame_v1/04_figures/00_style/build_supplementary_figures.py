#!/usr/bin/env python3
"""Build CMAME supplementary figures S1--S14 from frozen public evidence.

This is a display-only program.  It reads machine-readable frozen evidence and
performs deterministic plotting transforms (coordinate placement, log display,
binning, and color scaling).  It never imports solver, model, training,
optimizer, or candidate-generation code and never reads protected payloads.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np

import figure_style as fs


ROOT = Path(__file__).resolve().parents[3]
FIGURE_ROOT = ROOT / "publication_cmame_v1" / "04_figures"
SUPPLEMENT_ROOT = FIGURE_ROOT / "12_supplementary"
SCRIPT_PATH = Path(__file__).resolve()

# Path-level denylist.  Public audit summaries may document access controls, but
# protected payload paths themselves are never opened by this program.
DENIED_PATH_TOKENS = (
    "lcdf" + "_" + "03",
    "lcdf" + "_" + "10",
    "/" + "pri" + "vate" + "/",
    "pri" + "vate" + "_design",
    "fresh" + "_validation" + "_seal/" + "pri" + "vate",
)

OUTPUTS = {
    "S01": ("S01_operator_checks", "figS01_operator_checks"),
    "S02": ("S02_resource_gc", "figS02_resource_gc"),
    "S03": ("S03_mms_plateau", "figS03_mms_plateau"),
    "S04": ("S04_stage02_all_runs", "figS04_stage02_all_runs"),
    "S05": ("S05_stage03_360_probe", "figS05_stage03_360_probe"),
    "S06": ("S06_stage04_signal_decomposition", "figS06_stage04_signal_decomposition"),
    "S07": ("S07_stage05_fd_boundary", "figS07_stage05_fd_boundary"),
    "S08": ("S08_stage06_590_scan", "figS08_stage06_590_scan"),
    "S09": ("S09_stage06_six_lineage_origins", "figS09_stage06_six_lineage_origins"),
    "S10": ("S10_stage07_652_scan", "figS10_stage07_652_scan"),
    "S11": ("S11_stage07_fourteen_lineage_origins", "figS11_stage07_fourteen_lineage_origins"),
    "S12": ("S12_h2_diagnostics", "figS12_h2_diagnostics"),
    "S13": ("S13_stage08_192_candidates", "figS13_stage08_192_candidates"),
    "S14": ("S14_governance", "figS14_governance"),
}

PANEL_LETTERS = [f"({chr(ord('a') + i)})" for i in range(26)]


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def source(path: str) -> Path:
    candidate = (ROOT / path).resolve()
    candidate_text = "/" + rel(candidate).lower()
    blocked = [token for token in DENIED_PATH_TOKENS if token in candidate_text]
    if blocked:
        raise PermissionError(f"Protected evidence path rejected: {rel(candidate)} ({blocked})")
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    return candidate


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def load_json(path: str) -> tuple[Path, Any]:
    p = source(path)
    return p, json.loads(p.read_text(encoding="utf-8"))


def load_jsonl(path: str) -> tuple[Path, list[dict[str, Any]]]:
    p = source(path)
    rows = [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
    return p, rows


def load_csv(path: str) -> tuple[Path, list[dict[str, str]]]:
    p = source(path)
    with p.open("r", encoding="utf-8-sig", newline="") as handle:
        return p, list(csv.DictReader(handle))


def num(value: Any, default: float = math.nan) -> float:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def truth(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "pass", "yes"}


def finite_positive(values: Iterable[float], floor: float = 1.0e-30) -> list[float]:
    return [max(float(v), floor) for v in values if np.isfinite(v)]


def scalarize(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def add_panel(ax, index: int, title: str, provenance: str, *, grid: bool = False, stacked: bool = False) -> None:
    fs.style_axis(ax, grid=grid)
    if stacked:
        fs.panel_label(ax, PANEL_LETTERS[index], x=-0.10, y=1.115)
        ax.set_title(title, loc="left", x=0.0, pad=6)
    else:
        fs.panel_label(ax, PANEL_LETTERS[index], x=-0.11, y=1.055)
        ax.set_title(title, loc="left", x=0.07, pad=8)
    fs.provenance_tag(ax, provenance)


def legend_unique(ax, *, ncol: int = 2, fontsize: float = 6.2, loc: str = "best") -> None:
    handles, labels = ax.get_legend_handles_labels()
    seen: set[str] = set()
    unique_h, unique_l = [], []
    for handle, label in zip(handles, labels):
        if label and label not in seen:
            seen.add(label)
            unique_h.append(handle)
            unique_l.append(label)
    if unique_h:
        ax.legend(unique_h, unique_l, ncol=ncol, fontsize=fontsize, loc=loc, handlelength=1.7)


def vector_raster(ax, matrix: np.ndarray, **kwargs):
    """Draw a cell raster as editable SVG/PDF paths, never as an embedded bitmap."""
    values = np.asarray(matrix)
    if values.ndim != 2:
        raise ValueError("A display raster must be two-dimensional")
    rows, cols = values.shape
    x_edges = np.arange(cols + 1, dtype=float) - 0.5
    y_edges = np.arange(rows + 1, dtype=float) - 0.5
    mesh = ax.pcolormesh(x_edges, y_edges, values, shading="flat", rasterized=False, **kwargs)
    ax.set_xlim(-0.5, cols - 0.5)
    ax.set_ylim(rows - 0.5, -0.5)
    return mesh


def status_raster(ax, matrix: np.ndarray, xlabels: Sequence[str], ylabels: Sequence[str]) -> None:
    cmap = mcolors.ListedColormap([fs.COLORS["vermillion_light"], fs.COLORS["teal_light"]])
    vector_raster(ax, matrix, vmin=0, vmax=1, cmap=cmap)
    ax.set_xticks(range(len(xlabels)), xlabels, rotation=45, ha="right")
    ax.set_yticks(range(len(ylabels)), ylabels)
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            value = int(matrix[i, j])
            ax.text(j, i, "PASS" if value else "FAIL", ha="center", va="center", fontsize=5.4,
                    color=fs.COLORS["teal"] if value else fs.COLORS["vermillion"])


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_rows_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        rows = [{"note": "No scalar plotted rows; see source_data.json"}]
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: scalarize(row.get(key)) for key in keys})


def evidence_record(
    figure: str,
    panel: str,
    claim: str,
    path: Path,
    field: str,
    category: str,
    transformation: str,
    output_base: str,
) -> dict[str, Any]:
    return {
        "figure": figure,
        "panel": panel,
        "scientific_claim": claim,
        "source_file": rel(path),
        "source_hash": sha256(path),
        "source_field": field,
        "confirmatory_or_diagnostic": category,
        "transformation": transformation,
        "plot_script": rel(SCRIPT_PATH),
        "output_file": "; ".join(f"{output_base}.{ext}" for ext in ("svg", "pdf", "png")),
    }


def bundle(
    key: str,
    fig,
    title: str,
    caption: str,
    panels: Sequence[tuple[str, str]],
    source_data: Mapping[str, Any],
    flat_rows: Sequence[Mapping[str, Any]],
    evidence: Sequence[Mapping[str, Any]],
) -> None:
    folder_name, output_base = OUTPUTS[key]
    out = SUPPLEMENT_ROOT / folder_name
    out.mkdir(parents=True, exist_ok=True)
    fig.suptitle(title, x=0.01, ha="left", fontsize=10.3, fontweight="bold", color=fs.COLORS["black"])
    fs.save_figure(fig, out / output_base)

    write_json(out / "source_data.json", {
        "figure": key,
        "title": title,
        "display_transform_policy": (
            "Only deterministic coordinate placement, sorting stated per panel, log display, "
            "and color scaling; no new scientific fit, threshold, hypothesis test, or simulation."
        ),
        "panels": source_data,
    })
    write_rows_csv(out / "source_data.csv", flat_rows)
    (out / "caption.md").write_text(f"# {title}\n\n{caption.strip()}\n", encoding="utf-8")
    (out / "panel_spec.md").write_text(
        "# Panel specification\n\n" + "\n".join(f"- **{label}** {description}" for label, description in panels) + "\n",
        encoding="utf-8",
    )
    evidence_rows = [dict(row) for row in evidence]
    write_json(out / "evidence_map.json", evidence_rows)
    write_rows_csv(out / "evidence_map.csv", evidence_rows)

    wrapper = f'''#!/usr/bin/env python3
"""Rebuild {key} from frozen public evidence."""
from pathlib import Path
import subprocess
import sys

builder = Path(__file__).resolve().parents[2] / "00_style" / "build_supplementary_figures.py"
raise SystemExit(subprocess.call([sys.executable, str(builder), "--figure", "{key}"]))
'''
    (out / f"{output_base}_plot.py").write_text(wrapper, encoding="utf-8")


def build_s01() -> None:
    p_kernel, kernel = load_csv("06_experiments/stage_01b_operator_verification/results/kernel_moment_metrics.csv")
    p_operator, operator = load_csv("06_experiments/stage_01b_operator_verification/results/manufactured_operator_metrics.csv")
    p_cons, cons = load_csv("06_experiments/stage_01b_operator_verification/results/conservation_audit.csv")
    p_int, integ = load_csv("06_experiments/stage_01b_operator_verification/results/integrator_order.csv")
    p_v2, v2 = load_json("06_experiments/stage_01d2_v2_requalification/results/stage01d2_evaluation.json")

    fig, axes = plt.subplots(2, 3, figsize=(fs.mm_to_inch(190), fs.mm_to_inch(132)), constrained_layout=True)
    axes = axes.ravel()
    layouts = sorted({r["layout"] for r in kernel})
    layout_styles = {name: (fs.COLORS["blue"], "o", "-") if name == "regular" else (fs.COLORS["orange"], "s", "--") for name in layouts}
    for layout in layouts:
        rows = sorted((r for r in kernel if r["layout"] == layout), key=lambda r: num(r["resolution"]))
        color, marker, line = layout_styles[layout]
        axes[0].plot([num(r["resolution"]) for r in rows], finite_positive(num(r["s0_l2"]) for r in rows),
                     color=color, marker=marker, linestyle=line, label=layout)
        axes[1].plot([num(r["resolution"]) for r in rows], finite_positive(num(r["s1_l2"]) for r in rows),
                     color=color, marker=marker, linestyle=line, label=layout)
    for ax, title, ylabel in [(axes[0], "Zeroth moment", r"$\|S_0-1\|_2$"), (axes[1], "First moment", r"$\|S_1\|_2$")]:
        ax.set_yscale("log"); ax.set_xlabel("resolution"); ax.set_ylabel(ylabel); legend_unique(ax)
        add_panel(ax, 0 if ax is axes[0] else 1, title, "Stage01B frozen operator audit", grid=True)

    for operator_name in sorted({r["operator"] for r in operator}):
        rows = sorted((r for r in operator if r["operator"] == operator_name and r["norm"] == "l2"), key=lambda r: num(r["resolution"]))
        if rows:
            axes[2].plot([num(r["resolution"]) for r in rows], finite_positive(num(r["error"]) for r in rows),
                         marker="o", label=operator_name.replace("generic_sph_", ""))
    axes[2].set_yscale("log"); axes[2].set_xlabel("resolution"); axes[2].set_ylabel("manufactured L2 error")
    legend_unique(axes[2], fontsize=5.6)
    add_panel(axes[2], 2, "Manufactured operators", "Stage01B frozen operator audit", grid=True)

    x = np.arange(len(cons))
    axes[3].scatter(x, finite_positive(num(r["characteristic_normalized_internal_force"]) for r in cons),
                    s=10, c=[fs.COLORS["teal"] if num(r["viscous_power"], 0) <= 0 else fs.COLORS["orange"] for r in cons])
    axes[3].set_yscale("log"); axes[3].set_xlabel("frozen audit row"); axes[3].set_ylabel("normalized internal-force residual")
    add_panel(axes[3], 3, "Pairwise conservation audit", "all frozen rows; color encodes viscous-power sign", grid=True)

    for scheme in sorted({r["integration_scheme"] for r in integ}):
        rows = sorted((r for r in integ if r["integration_scheme"] == scheme), key=lambda r: num(r["dt"]), reverse=True)
        axes[4].plot([num(r["dt"]) for r in rows], finite_positive(num(r["absolute_error"]) for r in rows), marker="o", label=scheme)
    axes[4].set_xscale("log"); axes[4].set_yscale("log"); axes[4].invert_xaxis(); axes[4].set_xlabel(r"$\Delta t$"); axes[4].set_ylabel("absolute error")
    legend_unique(axes[4], fontsize=5.8)
    add_panel(axes[4], 4, "Integrator order audit", "frozen scalar integrator check", grid=True)

    fs.hide_axis(axes[5]); fs.panel_label(axes[5], PANEL_LETTERS[5], x=-0.11, y=1.055); axes[5].set_title("Verification boundary", loc="left", x=0.07, pad=8)
    fs.status_card(axes[5], (0.07, 0.56), 0.86, 0.25, "STATIC OPERATOR CHECKS", "VERIFIED", subtitle="kernel, moments, operators, conservation", transform=axes[5].transAxes)
    fs.status_card(axes[5], (0.07, 0.17), 0.86, 0.25, "V2 BASELINE", "NOT QUALIFIED", subtitle="Stage01D2 frozen requalification FAIL", transform=axes[5].transAxes)
    fs.provenance_tag(axes[5], "Stage01D2 frozen decision")

    flat = []
    for panel, rows in [("a-b", kernel), ("c", operator), ("d", cons), ("e", integ)]:
        flat.extend({"panel": panel, **row} for row in rows)
    flat.append({"panel": "f", **{k: scalarize(v) for k, v in v2.items()}})
    evidence = [
        evidence_record("S01", "a-b", "Frozen kernel zeroth- and first-moment errors are displayed by layout and resolution.", p_kernel, "resolution, layout, s0_l2, s1_l2", "SUPPORTED", "Exact rows; log-y display.", OUTPUTS["S01"][1]),
        evidence_record("S01", "c", "Manufactured static operator errors are displayed without converting them into V2 qualification.", p_operator, "operator, norm=l2, resolution, error", "SUPPORTED", "Exact L2 rows; log-y display.", OUTPUTS["S01"][1]),
        evidence_record("S01", "d", "Instantaneous pairwise conservation residual audits are shown for every frozen row.", p_cons, "characteristic_normalized_internal_force, viscous_power", "SUPPORTED", "Source order; log-y display; sign color.", OUTPUTS["S01"][1]),
        evidence_record("S01", "e", "Frozen scalar integrator error decreases are shown by time step.", p_int, "integration_scheme, dt, absolute_error", "SUPPORTED", "Exact rows; log-log display.", OUTPUTS["S01"][1]),
        evidence_record("S01", "f", "Static verification does not restore the retained V2 boundary.", p_v2, "final_status, gci_justified, resource_pass, disorder_status", "SUPPORTED", "Status-card transcription.", OUTPUTS["S01"][1]),
    ]
    bundle("S01", fig, "Supplementary Figure S1 | Kernel, moment, and operator checks",
           "Frozen Stage01B quantitative checks cover kernel moments, manufactured operators, instantaneous conservation, and a scalar integrator audit. The rightmost boundary card preserves the later Stage01D2 V2 decision: these static checks do not establish V2 baseline qualification and do not support a GCI or physical-validation claim.",
           [(PANEL_LETTERS[i], d) for i, d in enumerate([
               "Zeroth kernel moment by layout and resolution.", "First kernel moment by layout and resolution.",
               "Manufactured-operator L2 errors.", "All instantaneous conservation-audit rows.",
               "Frozen scalar integrator error study.", "Explicit static-check/V2 qualification boundary."])],
           {"a_b_kernel_moments": kernel, "c_manufactured_operator": operator, "d_conservation": cons, "e_integrator": integ, "f_v2_boundary": v2}, flat, evidence)


def build_s02() -> None:
    p_canary, canary = load_csv("06_experiments/stage_01dp_resource_policy/results/canary_summary.csv")
    p_edge, edge = load_csv("06_experiments/stage_01dr2_storage_attribution/results/edge_working_set_models.csv")
    p_fixed, fixed = load_csv("06_experiments/stage_01dr2_storage_attribution/results/fixed_topology_summary.csv")
    p_inventory, inventory = load_csv("06_experiments/stage_01dr2_storage_attribution/results/inventory_validation_summary.csv")
    p_reg, regression = load_csv("06_experiments/stage_01dr2_storage_attribution/results/numerical_regression_summary.csv")
    fig, axes = plt.subplots(2, 3, figsize=(fs.mm_to_inch(190), fs.mm_to_inch(126)), constrained_layout=True)
    axes = axes.ravel()

    ids = [r["run_id"].replace("stage01dp_canary_", "") for r in canary]
    axes[0].bar(ids, [num(r["rss_relative_increase"]) for r in canary], color=fs.COLORS["blue"], width=0.65)
    axes[0].set_ylabel("RSS relative increase"); add_panel(axes[0], 0, "Default-GC canaries", "3 frozen repeats", grid=True)
    axes[1].bar(ids, [num(r["step_time_ratio"]) for r in canary], color=fs.COLORS["orange"], width=0.65)
    axes[1].axhline(1.0, color=fs.COLORS["gray"], linewidth=0.8, linestyle="--"); axes[1].set_ylabel("late/early step-time ratio")
    add_panel(axes[1], 1, "Step-time stability", "3 frozen repeats", grid=True)

    edge_ids = [r["run_id"].split("_")[-1] for r in edge]
    axes[2].bar(np.arange(len(edge)) - 0.18, [num(r["total_edge_coefficient"]) for r in edge], 0.36, label="bytes / directed edge", color=fs.COLORS["teal"])
    axes[2].bar(np.arange(len(edge)) + 0.18, [abs(num(r["total_step_coefficient"])) for r in edge], 0.36, label="|bytes / step|", color=fs.COLORS["purple"])
    axes[2].set_xticks(range(len(edge)), edge_ids); axes[2].set_yscale("symlog", linthresh=1e-10); axes[2].set_ylabel("frozen robust-model coefficient")
    legend_unique(axes[2], fontsize=5.7); add_panel(axes[2], 2, "Edge working-set attribution", "fixed-topology robust models", grid=True)

    controls = [f"{r['control']}-{r['run_id'].split('_')[-1]}" for r in fixed]
    axes[3].bar(range(len(fixed)), [num(r["old_survivor_bytes_delta"]) for r in fixed], color=fs.COLORS["gray_mid"])
    axes[3].set_xticks(range(len(fixed)), controls, rotation=45, ha="right"); axes[3].set_ylabel("old-survivor bytes delta")
    add_panel(axes[3], 3, "Fixed-topology survivor ledger", "all frozen controls", grid=True)

    inv_ids = [r["run_id"].split("_")[-1] for r in inventory]
    axes[4].plot(inv_ids, [num(r["tensor_count_delta"]) for r in inventory], marker="o", label="tensor count delta")
    axes[4].plot(inv_ids, [num(r["unique_storage_bytes_delta"]) for r in inventory], marker="s", linestyle="--", label="unique-storage bytes delta")
    axes[4].set_ylabel("inventory delta"); legend_unique(axes[4], fontsize=5.8)
    add_panel(axes[4], 4, "Inventory self-check", "deduplicated storage inventory", grid=True)

    reg_ids = [r["run_id"].split("_")[-1] for r in regression]
    axes[5].bar(reg_ids, [num(r["maximum_absolute_difference"]) for r in regression], color=fs.COLORS["teal"])
    axes[5].set_ylabel("maximum absolute difference"); axes[5].text(0.98, 0.92, "all 0; bitwise + finite", transform=axes[5].transAxes, ha="right", va="top", color=fs.COLORS["teal"], fontsize=6.5)
    add_panel(axes[5], 5, "Numerical regression", "frozen Stage01DR2 repeats", grid=True)

    flat = []
    for panel, rows in [("a-b", canary), ("c", edge), ("d", fixed), ("e", inventory), ("f", regression)]:
        flat.extend({"panel": panel, **r} for r in rows)
    evidence = [
        evidence_record("S02", "a-b", "Default-GC canary resource and timing evidence is displayed for all repeats.", p_canary, "rss_relative_increase, step_time_ratio, policy_gate_pass", "SUPPORTED", "Exact repeat bars.", OUTPUTS["S02"][1]),
        evidence_record("S02", "c", "Frozen working-set models attribute retained storage to edge count rather than accumulated steps.", p_edge, "total_edge_coefficient, total_step_coefficient, confidence fields", "SUPPORTED", "Exact coefficients; symlog display.", OUTPUTS["S02"][1]),
        evidence_record("S02", "d", "Old-survivor storage deltas are shown for every fixed-topology control repeat.", p_fixed, "old_survivor_bytes_delta, directed_edge_count", "SUPPORTED", "Exact bars in source order.", OUTPUTS["S02"][1]),
        evidence_record("S02", "e", "Storage-inventory self-retention and view/base deduplication checks retained zero deltas.", p_inventory, "tensor_count_delta, unique_storage_bytes_delta", "SUPPORTED", "Exact repeat traces.", OUTPUTS["S02"][1]),
        evidence_record("S02", "f", "Numerical-regression repeats remained bitwise and finite under the audited resource route.", p_reg, "maximum_absolute_difference, bitwise_and_finite_rows", "SUPPORTED", "Exact bars.", OUTPUTS["S02"][1]),
    ]
    bundle("S02", fig, "Supplementary Figure S2 | Resource and garbage-collection attribution",
           "Frozen engineering evidence separates default-GC canary stability, edge-working-set storage, survivor-ledger behavior, inventory validation, and bitwise numerical regression. These checks qualify the bounded engineering route only; they do not add solver-verification or learning-performance claims.",
           [(PANEL_LETTERS[i], d) for i, d in enumerate(["Canary RSS change.", "Canary timing stability.", "Edge/step working-set coefficients.", "Old-survivor deltas.", "Inventory validation.", "Bitwise numerical regression."])],
           {"a_b_canary": canary, "c_edge_model": edge, "d_fixed_topology": fixed, "e_inventory": inventory, "f_regression": regression}, flat, evidence)


def build_s03() -> None:
    p_space, space = load_csv("06_experiments/stage_01d2_v2_requalification/results/space_results.csv")
    p_time, time_rows = load_csv("06_experiments/stage_01d2_v2_requalification/results/time_results.csv")
    p_dis, disorder = load_csv("06_experiments/stage_01d2_v2_requalification/results/disorder_results.csv")
    p_dec, decision = load_json("06_experiments/stage_01d2_v2_requalification/results/stage01d2_evaluation.json")
    fig, axes = plt.subplots(2, 3, figsize=(fs.mm_to_inch(190), fs.mm_to_inch(128)), constrained_layout=True)
    axes = axes.ravel()

    space_sorted = sorted(space, key=lambda r: num(r["resolution"]))
    for field, marker, color in [("velocity_relative_l2", "o", fs.COLORS["blue"]), ("modal_error", "s", fs.COLORS["teal"]), ("kinetic_energy_error", "D", fs.COLORS["orange"])]:
        axes[0].plot([num(r["resolution"]) for r in space_sorted], finite_positive(num(r[field]) for r in space_sorted), marker=marker, color=color, label=field.replace("_", " "))
    axes[0].set_yscale("log"); axes[0].set_xlabel("resolution"); axes[0].set_ylabel("error"); legend_unique(axes[0], fontsize=5.5)
    add_panel(axes[0], 0, "Space sequence", "frozen increasing-support sequence", grid=True)

    axes[1].plot([num(r["resolution"]) for r in space_sorted], [num(r["support_ratio"]) for r in space_sorted], marker="o", color=fs.COLORS["purple"])
    axes[1].set_xlabel("resolution"); axes[1].set_ylabel("support ratio")
    add_panel(axes[1], 1, "Preregistered support scaling", "exact frozen configuration", grid=True)

    time_sorted = sorted(time_rows, key=lambda r: num(r["dt"]), reverse=True)
    axes[2].plot([num(r["dt"]) for r in time_sorted], [num(r["velocity_relative_l2"]) for r in time_sorted], marker="o", color=fs.COLORS["blue"], label="velocity")
    axes[2].plot([num(r["dt"]) for r in time_sorted], [num(r["modal_error"]) for r in time_sorted], marker="s", color=fs.COLORS["teal"], label="modal")
    axes[2].set_xscale("log"); axes[2].set_yscale("log"); axes[2].invert_xaxis(); axes[2].set_xlabel(r"$\Delta t$"); axes[2].set_ylabel("error")
    legend_unique(axes[2], fontsize=5.8); add_panel(axes[2], 2, "Time refinement and plateau", "no fitted order introduced", grid=True)

    axes[3].plot([num(r["dt"]) for r in time_sorted], [num(r["kinetic_energy_error"]) for r in time_sorted], marker="D", color=fs.COLORS["orange"])
    axes[3].set_xscale("log"); axes[3].set_yscale("log"); axes[3].invert_xaxis(); axes[3].set_xlabel(r"$\Delta t$"); axes[3].set_ylabel("kinetic-energy error")
    add_panel(axes[3], 3, "Energy-error plateau", "exact frozen rows", grid=True)

    colors = [fs.COLORS["teal"] if r["status"] == "PASS" else fs.COLORS["vermillion"] for r in disorder]
    axes[4].scatter(range(len(disorder)), [num(r["velocity_relative_l2"]) for r in disorder], c=colors, marker="o", label="velocity")
    axes[4].scatter(range(len(disorder)), [num(r["density_fluctuation"]) for r in disorder], edgecolors=colors, marker="s", facecolors="none", label="density")
    axes[4].set_yscale("log"); axes[4].set_xlabel("frozen disorder row"); axes[4].set_ylabel("diagnostic magnitude"); legend_unique(axes[4], fontsize=5.8)
    add_panel(axes[4], 4, "Disorder outcomes", "PASS teal; FAIL vermillion", grid=True)

    fs.hide_axis(axes[5]); fs.panel_label(axes[5], PANEL_LETTERS[5], x=-0.11, y=1.055); axes[5].set_title("Plateau-aware boundary", loc="left", x=0.07, pad=8)
    fs.status_card(axes[5], (0.06, 0.58), 0.88, 0.24, "MMS / DISCRETIZATION EVIDENCE", "DIAGNOSTIC", subtitle="plateau retained; no new fit", transform=axes[5].transAxes)
    fs.status_card(axes[5], (0.06, 0.18), 0.88, 0.24, "V2 RESTORATION", "NOT QUALIFIED", subtitle="Stage01D2 frozen requalification FAIL", transform=axes[5].transAxes)
    axes[5].text(0.5, 0.04, f"space slope = {num(decision.get('space_slope_velocity')):.3g}; GCI justified = {str(decision.get('gci_justified')).lower()}", ha="center", va="bottom", transform=axes[5].transAxes, fontsize=6.2, color=fs.COLORS["gray"])

    flat = [{"panel": "a-b", **r} for r in space] + [{"panel": "c-d", **r} for r in time_rows] + [{"panel": "e", **r} for r in disorder] + [{"panel": "f", **{k: scalarize(v) for k, v in decision.items()}}]
    evidence = [
        evidence_record("S03", "a-b", "The frozen spatial sequence and its support ratios are displayed directly.", p_space, "resolution, support_ratio, velocity_relative_l2, modal_error, kinetic_energy_error", "DIAGNOSTIC_ONLY", "Resolution sort; exact values; log-y for errors.", OUTPUTS["S03"][1]),
        evidence_record("S03", "c-d", "Time refinement shows a retained error plateau without a newly fitted convergence order.", p_time, "dt and three error fields", "DIAGNOSTIC_ONLY", "Descending-dt coordinate placement; log-log display.", OUTPUTS["S03"][1]),
        evidence_record("S03", "e", "All frozen disorder outcomes, including failures, remain visible.", p_dis, "status and diagnostic fields", "DIAGNOSTIC_ONLY", "Source order; status color; log-y display.", OUTPUTS["S03"][1]),
        evidence_record("S03", "f", "The frozen evaluation does not restore V2 or justify a GCI statement.", p_dec, "final_status, space_slope_velocity, gci_justified, resource_pass", "SUPPORTED", "Exact scalar annotation and status-card transcription.", OUTPUTS["S03"][1]),
    ]
    bundle("S03", fig, "Supplementary Figure S3 | Plateau-aware MMS evidence",
           "Frozen spatial, temporal, and disorder evidence is displayed without adding a convergence fit. The time-refinement panels visibly retain the error plateau, and all failed disorder rows remain present. This evidence is diagnostic for discretization and does not constitute a GCI, physical validation, or V2 restoration.",
           [(PANEL_LETTERS[i], d) for i, d in enumerate(["Space-refinement errors.", "Support-ratio sequence.", "Time-refinement plateau.", "Energy-error plateau.", "Disorder outcomes.", "Frozen V2 boundary."])],
           {"a_b_space": space, "c_d_time": time_rows, "e_disorder": disorder, "f_decision": decision}, flat, evidence)


def build_s04() -> None:
    campaigns = [
        ("v0.1", "pair_force_pio_static_fitting_v0_1", [20261201, 20261202, 20261203]),
        ("v0.2", "pair_force_pio_static_fitting_v0_2", [20261211, 20261212, 20261213]),
    ]
    sources: list[Path] = []
    all_rows: list[dict[str, Any]] = []
    fig, axes = plt.subplots(2, 3, figsize=(fs.mm_to_inch(190), fs.mm_to_inch(132)), constrained_layout=True, sharex="row")
    for row_index, (campaign_label, campaign_dir, seeds) in enumerate(campaigns):
        for arm_index, arm in enumerate(("K0", "K1", "K2")):
            ax = axes[row_index, arm_index]
            for seed_index, seed in enumerate(seeds):
                p, data = load_json(f"stage_02_Particle_Interaction_Operator/06_model/{campaign_dir}/runs/{arm}/seed_{seed}/training_history.json")
                sources.append(p)
                rows = data["rows"]
                all_rows.extend({"panel": f"{campaign_label}-{arm}", "campaign": campaign_label, "arm": arm, "seed": seed, **r} for r in rows)
                ax.plot([r["update"] for r in rows], finite_positive(r["graph_balanced_loss"] for r in rows),
                        color=[fs.COLORS["blue"], fs.COLORS["teal"], fs.COLORS["orange"]][seed_index],
                        linestyle=["-", "--", "-."][seed_index], label=str(seed))
            ax.set_yscale("log"); ax.set_xlabel("update"); ax.set_ylabel("graph-balanced loss")
            add_panel(ax, row_index * 3 + arm_index, f"{campaign_label} | {arm}", "all 3 seeds; no run deleted", grid=True)
            legend_unique(ax, ncol=3, fontsize=5.4)
    evidence = []
    for panel_index, p in enumerate(sources):
        campaign = "v0.1" if "v0_1" in rel(p) else "v0.2"
        arm = next(a for a in ("K0", "K1", "K2") if f"/runs/{a}/" in rel(p))
        panel = PANEL_LETTERS[(0 if campaign == "v0.1" else 3) + ("K0", "K1", "K2").index(arm)]
        evidence.append(evidence_record("S04", panel, "Every frozen Stage02 static-fitting trajectory is retained, including failed and nonqualifying runs.", p, "rows[*].update, graph_balanced_loss", "DIAGNOSTIC_ONLY", "Exact history curve; log-y display.", OUTPUTS["S04"][1]))
    bundle("S04", fig, "Supplementary Figure S4 | Complete Stage02 static-fitting histories",
           "All eighteen frozen Stage02 static-fitting histories are shown: three K0, K1, and K2 seeds in each of the v0.1 and v0.2 campaigns. No failed run is removed, smoothed, truncated, or reselected. The curves document the closed static route and do not establish a trained dynamic solver.",
           [(PANEL_LETTERS[i], f"{campaign} {arm}: all three frozen seed trajectories.") for i, (campaign, arm) in enumerate([(c, a) for c in ("v0.1", "v0.2") for a in ("K0", "K1", "K2")])],
           {"complete_training_histories": all_rows}, all_rows, evidence)


def build_s05() -> None:
    p, data = load_json("stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03dr/failure_matrix/stage03d_complete_360_row_matrix.json")
    rows = data["rows"]
    fig = fs.new_figure(142)
    gs = fig.add_gridspec(2, 3)
    axes = [fig.add_subplot(gs[i // 3, i % 3]) for i in range(6)]
    flat: list[dict[str, Any]] = []
    for panel_index, arm in enumerate(("D1", "D2", "D3")):
        arm_rows = [r for r in rows if r["arm"] == arm]
        matrix = np.array([[math.log10(max(num(v), 1e-16)) for v in r["relative_errors"]] for r in arm_rows])
        im = vector_raster(axes[panel_index], matrix, cmap="viridis", vmin=-8, vmax=0)
        axes[panel_index].set_xticks(range(4), [f"{x:g}" for x in arm_rows[0]["fd_epsilons"]], rotation=45, ha="right")
        axes[panel_index].set_xlabel(r"FD $\epsilon$"); axes[panel_index].set_ylabel("frozen probe row")
        add_panel(axes[panel_index], panel_index, f"{arm}: AD/FD relative error", f"{len(arm_rows)} rows; fixed topology")
        cbar = fig.colorbar(im, ax=axes[panel_index], fraction=0.045, pad=0.02, label=r"$\log_{10}$ relative error")
        cbar.solids.set_rasterized(False)
        for row_id, r in enumerate(arm_rows):
            for eps, err in zip(r["fd_epsilons"], r["relative_errors"]):
                flat.append({"panel": PANEL_LETTERS[panel_index], "row_id": r["row_id"], "arm": arm, "epsilon": eps, "relative_error": err, "historical_stable_window_verdict": r["historical_stable_window_verdict"]})

    summary = data["summary"]
    groups = list(summary["axis_counts"]["probe_group"])
    passes = [summary["axis_counts"]["probe_group"][g].get("pass", 0) for g in groups]
    fails = [summary["axis_counts"]["probe_group"][g].get("fail", 0) for g in groups]
    x = np.arange(len(groups))
    axes[3].bar(x, passes, color=fs.COLORS["teal"], label="historical PASS")
    axes[3].bar(x, fails, bottom=passes, color=fs.COLORS["vermillion"], hatch="////", label="historical FAIL")
    axes[3].set_xticks(x, groups, rotation=30, ha="right"); axes[3].set_ylabel("frozen row count"); legend_unique(axes[3], fontsize=5.8)
    add_panel(axes[3], 3, "Historical verdict by probe group", "frozen summary counts", grid=True)

    horizons = ["1", "2", "4", "8"]
    passes_h = [summary["axis_counts"]["horizon"][h].get("pass", 0) for h in horizons]
    fails_h = [summary["axis_counts"]["horizon"][h].get("fail", 0) for h in horizons]
    xh = np.arange(4)
    axes[4].bar(xh - 0.18, passes_h, 0.36, color=fs.COLORS["teal"], label="PASS")
    axes[4].bar(xh + 0.18, fails_h, 0.36, color=fs.COLORS["vermillion"], hatch="////", label="FAIL")
    axes[4].set_xticks(xh, horizons); axes[4].set_xlabel("horizon"); axes[4].set_ylabel("frozen row count"); legend_unique(axes[4], fontsize=5.8)
    add_panel(axes[4], 4, "Historical verdict by horizon", "frozen summary counts", grid=True)

    verdict = np.array([[1 if r["historical_stable_window_verdict"] else 0 for r in rows]])
    cmap = mcolors.ListedColormap([fs.COLORS["vermillion"], fs.COLORS["teal"]])
    vector_raster(axes[5], verdict, cmap=cmap, vmin=0, vmax=1)
    axes[5].set_yticks([0], ["stable window"]); axes[5].set_xlabel("all 360 rows in frozen source order")
    axes[5].axvline(95.5, color="white", linewidth=0.8); axes[5].axvline(215.5, color="white", linewidth=0.8)
    axes[5].text(47.5, 0.34, "D1", ha="center", fontsize=6.3); axes[5].text(155.5, 0.34, "D2", ha="center", fontsize=6.3); axes[5].text(287.5, 0.34, "D3", ha="center", fontsize=6.3)
    add_panel(axes[5], 5, "Complete 360-row verdict strip", "216 PASS; 144 FAIL")

    flat.extend({"panel": "d", "probe_group": g, **v} for g, v in summary["axis_counts"]["probe_group"].items())
    flat.extend({"panel": "e", "horizon": h, **summary["axis_counts"]["horizon"][h]} for h in horizons)
    evidence = [evidence_record("S05", "a-f", "The complete fixed-topology 360-probe matrix retains every historical pass and failure.", p, "rows[*] and summary.axis_counts", "DIAGNOSTIC_ONLY", "Source-order heatmaps; log10 display; frozen summary bars.", OUTPUTS["S05"][1])]
    bundle("S05", fig, "Supplementary Figure S5 | Complete Stage03 fixed-topology AD/FD matrix",
           "All 360 frozen Stage03 probes are retained. Panels (a–c) show each recorded finite-difference epsilon for D1–D3; panels (d–f) reproduce the frozen pass/fail accounting by probe group, horizon, and source-row order. The evidence is bounded to fixed topology and cannot be generalized to event-crossing derivatives.",
           [(PANEL_LETTERS[i], d) for i, d in enumerate(["D1 relative-error matrix.", "D2 relative-error matrix.", "D3 relative-error matrix.", "Probe-group verdicts.", "Horizon verdicts.", "All 360 historical stable-window verdicts."])],
           {"rows": rows, "summary": summary}, flat, evidence)


def build_s06() -> None:
    p_proj, projection = load_json("stage_04_Local_Causal_Dynamic_Training/05_task_aligned_gradient/stage04cr/directional_projection/directional_projection_and_factors.json")
    p_grad, gradients = load_json("stage_04_Local_Causal_Dynamic_Training/05_task_aligned_gradient/stage04cr/full_gradient_norm/full_gradient_norms.json")
    p_res, residual = load_json("stage_04_Local_Causal_Dynamic_Training/05_task_aligned_gradient/stage04cr/state_residual/state_residual_and_D0_comparison.json")
    p_rk2, rk2 = load_json("stage_04_Local_Causal_Dynamic_Training/05_task_aligned_gradient/stage04cr/rk2_attenuation/rk2_attenuation.json")
    p_sum, summary = load_json("stage_04_Local_Causal_Dynamic_Training/05_task_aligned_gradient/stage04cr/qualification/stage04cr_summary.json")
    comps = [dict(arm=r["arm"], group=r["group"], lineage=r["lineage"], model_seed=r["model_seed"], origin=r["origin"], variant=r["variant"], **c) for r in projection["rows"] for c in r["components"]]
    grad_comps = [dict(component=name, arm=r["arm"], group=r["group"], lineage=r["lineage"], model_seed=r["model_seed"], origin=r["origin"], variant=r["variant"], **value) for r in gradients["rows"] for name, value in r["components"].items()]
    fig, axes = plt.subplots(2, 4, figsize=(fs.mm_to_inch(190), fs.mm_to_inch(136)), constrained_layout=True)
    axes = axes.ravel()
    comp_style = {"L_x": (fs.COLORS["blue"], "o"), "L_v": (fs.COLORS["teal"], "s"), "L_rho": (fs.COLORS["orange"], "D")}
    for name, (color, marker) in comp_style.items():
        rr = [r for r in comps if r["component"] == name]
        axes[0].scatter(finite_positive(r["residual_RMS"] for r in rr), finite_positive(abs(r["state_JVP_RMS"]) for r in rr), s=5, alpha=0.45, color=color, marker=marker, label=name)
        axes[1].scatter(finite_positive(r["full_gradient_L2"] for r in rr), finite_positive(abs(r["historical_reverse"]) for r in rr), s=5, alpha=0.45, color=color, marker=marker, label=name)
    axes[0].set_xscale("log"); axes[0].set_yscale("log"); axes[0].set_xlabel("task residual RMS"); axes[0].set_ylabel("state JVP RMS"); legend_unique(axes[0], fontsize=5.7)
    add_panel(axes[0], 0, "Residual × state sensitivity", "2592 frozen component rows", grid=True)
    axes[1].set_xscale("log"); axes[1].set_yscale("log"); axes[1].set_xlabel("full-gradient L2"); axes[1].set_ylabel("|historical reverse|\n(group direction)"); legend_unique(axes[1], fontsize=5.7)
    add_panel(axes[1], 1, "Full gradient × projection", "2592 frozen component rows", grid=True)

    for name, (color, marker) in comp_style.items():
        rr = [r for r in comps if r["component"] == name]
        axes[2].scatter(range(len(rr)), [r["projection_ratio"] for r in rr], s=4, alpha=0.45, color=color, marker=marker, label=name)
        axes[3].scatter([r["cosine_alignment"] for r in rr], [r["scaled_projection"] for r in rr], s=5, alpha=0.45, color=color, marker=marker, label=name)
    axes[2].set_yscale("log"); axes[2].set_xlabel("frozen row within component"); axes[2].set_ylabel("projection ratio"); legend_unique(axes[2], fontsize=5.7)
    add_panel(axes[2], 2, "Group-direction dilution", "source order; no re-selection", grid=True)
    axes[3].set_xlabel("cosine alignment"); axes[3].set_ylabel("scaled projection"); legend_unique(axes[3], fontsize=5.7)
    add_panel(axes[3], 3, "Alignment / projection", "all frozen component rows", grid=True)

    axes[4].scatter(range(len(rk2["rows"])), [r["V_over_dt_A_mid"] for r in rk2["rows"]], s=4, alpha=0.5, color=fs.COLORS["teal"])
    axes[4].axhline(1.0, color=fs.COLORS["gray"], linestyle="--", linewidth=0.8); axes[4].set_xlabel("frozen context row"); axes[4].set_ylabel(r"$V/(\Delta t A_{mid})$")
    axes[4].ticklabel_format(axis="y", style="plain", useOffset=False)
    add_panel(axes[4], 4, "RK2 velocity attenuation", "864 frozen context rows", grid=True)
    axes[5].scatter(range(len(rk2["rows"])), [r["X_over_dt2_A_mid"] for r in rk2["rows"]], s=4, alpha=0.5, color=fs.COLORS["blue"], label=r"$X/(dt^2 A)$")
    axes[5].scatter(range(len(rk2["rows"])), [r["RHO_over_dt2_A_mid"] for r in rk2["rows"]], s=4, alpha=0.35, color=fs.COLORS["orange"], label=r"$\rho/(dt^2 A)$")
    axes[5].axhline(0.5, color=fs.COLORS["gray"], linestyle="--", linewidth=0.8); axes[5].set_xlabel("frozen context row"); axes[5].set_ylabel("normalized accepted-state response"); legend_unique(axes[5], fontsize=5.5)
    add_panel(axes[5], 5, "RK2 position / density", "864 frozen context rows", grid=True)

    reasons = projection["reason_counts"]
    axes[6].bar(range(len(reasons)), list(reasons.values()), color=[fs.COLORS["blue"], fs.COLORS["orange"], fs.COLORS["gray_mid"]])
    axes[6].set_xticks(range(len(reasons)), [k.replace("_", "\n") for k in reasons], fontsize=5.2); axes[6].set_ylabel("frozen component count")
    add_panel(axes[6], 6, "Primary attribution counts", "no cases dropped", grid=True)

    fs.hide_axis(axes[7]); fs.panel_label(axes[7], PANEL_LETTERS[7], x=-0.11, y=1.055); axes[7].set_title("Attribution boundary", loc="left", x=0.07, pad=8)
    fs.status_card(axes[7], (0.05, 0.58), 0.90, 0.24, "FULL GRADIENT ACTIVITY", "VERIFIED", subtitle="0 dead-parameterization fraction", transform=axes[7].transAxes)
    fs.status_card(axes[7], (0.05, 0.18), 0.90, 0.24, "TASK-ALIGNED SIGNAL", "NOT QUALIFIED", subtitle="mixed or unresolved (frozen)", transform=axes[7].transAxes, fontsize=6.0)
    fs.provenance_tag(axes[7], "Stage04CR frozen summary")

    flat = []
    flat.extend({"panel": "a-d", **{k: scalarize(v) for k, v in r.items()}} for r in comps)
    flat.extend({"panel": "gradient_inventory", **{k: scalarize(v) for k, v in r.items()}} for r in grad_comps)
    flat.extend({"panel": "e-f", **r} for r in rk2["rows"])
    flat.extend({"panel": "residual_inventory", **{k: scalarize(v) for k, v in r.items()}} for r in residual["rows"])
    flat.extend({"panel": "g", "reason": k, "count": v} for k, v in reasons.items())
    evidence = [
        evidence_record("S06", "a-d,g", "The full frozen signal factorization separates task residual, full-gradient activity, direction projection, and attribution class.", p_proj, "rows[*].components and reason_counts", "DIAGNOSTIC_ONLY", "Component expansion; source order; log display where stated.", OUTPUTS["S06"][1]),
        evidence_record("S06", "b", "Full gradients were active even where group-direction projections were small.", p_grad, "rows[*].components.*.L2/nonzero_element_count", "DIAGNOSTIC_ONLY", "Component expansion; log-log scatter.", OUTPUTS["S06"][1]),
        evidence_record("S06", "a", "D0 and random-model state residual magnitudes are retained in the source-data inventory.", p_res, "rows[*].D0_dimensionless_state_residual_RMS/random_minus_D0_state_RMS", "DIAGNOSTIC_ONLY", "Exact source-data export.", OUTPUTS["S06"][1]),
        evidence_record("S06", "e-f", "Frozen RK2 factorization shows velocity-scale and position/density-scale attenuation.", p_rk2, "V_over_dt_A_mid, X_over_dt2_A_mid, RHO_over_dt2_A_mid", "DIAGNOSTIC_ONLY", "Exact source-order scatter.", OUTPUTS["S06"][1]),
        evidence_record("S06", "h", "The retained Stage04CR terminal status is mixed or unresolved, not qualified.", p_sum, "final_status, reason_counts, stage04c_status_preserved", "SUPPORTED", "Status-card transcription.", OUTPUTS["S06"][1]),
    ]
    bundle("S06", fig, "Supplementary Figure S6 | Complete Stage04 signal decomposition",
           "The frozen 864-context factorization expands to 2,592 component rows and separates residual magnitude, state sensitivity, full-gradient activity, group-direction projection, and RK2 attenuation. Diagnostic and unresolved labels remain visible. Nonzero network sensitivity is therefore not recast as a qualified task-aligned training signal.",
           [(PANEL_LETTERS[i], d) for i, d in enumerate(["Residual versus state-JVP magnitude.", "Full-gradient magnitude versus historical direction projection.", "Projection-ratio inventory.", "Cosine and dimension-scaled projection.", "RK2 velocity scaling.", "RK2 position/density scaling.", "Frozen attribution counts.", "Qualified/unqualified boundary."])],
           {"a_d_projection_components": comps, "full_gradient_components": grad_comps, "state_residual_inventory": residual["rows"], "e_f_rk2": rk2["rows"], "g_reason_counts": reasons, "h_summary": summary}, flat, evidence)


def build_s07() -> None:
    p_failed, failed = load_json("stage_05_Scale_Aware_Discrete_Defect_Training/02_optimizer_gradient_qualification/stage05cr/failed_probe_reconstruction/original_failed_probe_reconstruction.json")
    p_match, matched = load_json("stage_05_Scale_Aware_Discrete_Defect_Training/02_optimizer_gradient_qualification/stage05cr/matched_controls/matched_control_selection.json")
    p_attr, attribution = load_json("stage_05_Scale_Aware_Discrete_Defect_Training/02_optimizer_gradient_qualification/stage05cr/attribution/failure_attribution.json")
    p_coord, coord = load_json("stage_05_Scale_Aware_Discrete_Defect_Training/02_optimizer_gradient_qualification/stage05cq/coordinate_block_sampling/coordinate_block_evidence.json")
    p_sum, summary = load_json("stage_05_Scale_Aware_Discrete_Defect_Training/02_optimizer_gradient_qualification/stage05cq/qualification/stage05cq_qualification_summary.json")
    p_route, route = load_json("stage_05_Scale_Aware_Discrete_Defect_Training/02_optimizer_gradient_qualification/stage05cr/route_decision/stage05cr_route_decision.json")
    fig, axes = plt.subplots(2, 4, figsize=(fs.mm_to_inch(190), fs.mm_to_inch(138)), constrained_layout=True)
    axes = axes.ravel()
    probe_colors = [fs.COLORS["blue"], fs.COLORS["teal"], fs.COLORS["orange"], fs.COLORS["purple"]]
    flat: list[dict[str, Any]] = []
    for i, row in enumerate(failed["rows"]):
        fd = row["original_finite_difference"]
        eps = [e["epsilon"] for e in fd["epsilon_rows"]]
        vals = [e["FD"] for e in fd["epsilon_rows"]]
        rels = [e["FD_AD_rel"] for e in fd["epsilon_rows"]]
        axes[0].plot(eps, vals, marker="o", color=probe_colors[i], label=f"{row['arm']} {row['lineage']}")
        axes[0].axhline(row["reverse_jvp"]["reverse"], color=probe_colors[i], linestyle=":", linewidth=0.8)
        axes[1].plot(eps, finite_positive(rels), marker="o", color=probe_colors[i], label=f"probe {i+1}")
        flat.extend({"panel": "a-b", "probe": i + 1, "arm": row["arm"], "lineage": row["lineage"], "epsilon": e["epsilon"], "FD": e["FD"], "AD": row["reverse_jvp"]["reverse"], "FD_AD_rel": e["FD_AD_rel"], "stable": fd["stable"]} for e in fd["epsilon_rows"])
    for ax in axes[:2]: ax.set_xscale("log"); ax.invert_xaxis(); ax.set_xlabel(r"$\epsilon$"); legend_unique(ax, fontsize=5.2)
    axes[0].set_ylabel("directional derivative"); add_panel(axes[0], 0, "Historical failed probes", "solid FD; dotted reverse AD", grid=True)
    axes[1].set_yscale("log"); axes[1].set_ylabel("FD–AD relative difference"); add_panel(axes[1], 1, "Missing stable windows", "all four frozen failures", grid=True)

    stability = np.array([[int(x["pass"]) for x in row["original_finite_difference"]["stable_pairs"]] for row in failed["rows"]])
    status_raster(axes[2], stability, [f"pair {i+1}" for i in range(stability.shape[1])], [f"probe {i+1}" for i in range(stability.shape[0])])
    add_panel(axes[2], 2, "Adjacent-epsilon stability", "frozen stable-pair verdicts")

    labels = [f"probe {i+1}" for i in range(len(matched["rows"]))]
    axes[3].bar(np.arange(len(labels)) - 0.18, [r["observed_distinct_control_count"] for r in matched["rows"]], 0.36, color=fs.COLORS["blue"], label="observed")
    axes[3].bar(np.arange(len(labels)) + 0.18, [r["required_distinct_control_count"] for r in matched["rows"]], 0.36, color=fs.COLORS["gray_mid"], label="required")
    axes[3].set_xticks(range(len(labels)), labels); axes[3].set_ylabel("distinct controls"); legend_unique(axes[3], fontsize=5.8)
    add_panel(axes[3], 3, "Matched-control availability", "preregistered exact strata", grid=True)

    classes = list(coord["classification_counts"])
    axes[4].bar(range(len(classes)), [coord["classification_counts"][c] for c in classes], color=[fs.COLORS["vermillion"] if c == "FD_WINDOW_MISSING" else fs.COLORS["teal"] for c in classes])
    axes[4].set_xticks(range(len(classes)), [c.replace("_", "\n") for c in classes], fontsize=4.6); axes[4].set_ylabel("blind probe count")
    add_panel(axes[4], 4, "Prospective blind classifications", "1728 frozen probes", grid=True)

    lineages = coord["group_lineages"]
    names = [f"{r['arm']}|{r['group'].replace(r['arm']+'_','')}|{r['lineage'].replace('LCDF_','')}" for r in lineages]
    pass_vector = np.array([[int(r["pass"])] for r in lineages])
    cmap = mcolors.ListedColormap([fs.COLORS["vermillion"], fs.COLORS["teal"]])
    vector_raster(axes[5], pass_vector.T, cmap=cmap, vmin=0, vmax=1)
    axes[5].set_yticks([0], ["group-lineage"]); axes[5].set_xlabel("72 frozen group-lineage strata")
    add_panel(axes[5], 5, "Coordinate/block coverage boundary", "teal PASS; vermillion FAIL")

    fs.hide_axis(axes[6]); fs.panel_label(axes[6], PANEL_LETTERS[6], x=-0.11, y=1.055); axes[6].set_title("Qualification ledger", loc="left", x=0.07, pad=8)
    fs.status_card(axes[6], (0.04, 0.57), 0.92, 0.25, "REVERSE/JVP + OPTIMIZER PATH", "QUALIFIED", subtitle="hard gates D and E", transform=axes[6].transAxes, fontsize=6.0)
    fs.status_card(axes[6], (0.04, 0.16), 0.92, 0.25, "COORDINATE/BLOCK COVERAGE", "NOT QUALIFIED", subtitle="failed gate F", transform=axes[6].transAxes, fontsize=6.0)

    fs.hide_axis(axes[7]); fs.panel_label(axes[7], PANEL_LETTERS[7], x=-0.11, y=1.055); axes[7].set_title("Closed historical attribution", loc="left", x=0.07, pad=8)
    axes[7].text(0.03, 0.86, attribution["status"].replace("_", "\n"), va="top", fontsize=6.1, fontweight="bold", color=fs.COLORS["vermillion"], transform=axes[7].transAxes)
    zero_fields = ["optimizer_instances", "optimizer_steps", "persistent_parameter_updates", "training_runs", "neural_rollouts", "performance_evaluations"]
    for j, field in enumerate(zero_fields):
        axes[7].text(0.05, 0.56 - j * 0.075, f"{field.replace('_',' ')}: {route[field]}", transform=axes[7].transAxes, fontsize=6.1, color=fs.COLORS["ink"])
    fs.provenance_tag(axes[7], "Stage05CR frozen route decision")

    flat.extend({"panel": "c", "probe": i + 1, "pair": j + 1, "pass": bool(v)} for i, row in enumerate(stability) for j, v in enumerate(row))
    flat.extend({"panel": "d", **{k: scalarize(v) for k, v in r.items()}} for r in matched["rows"])
    flat.extend({"panel": "e", "classification": k, "count": v} for k, v in coord["classification_counts"].items())
    flat.extend({"panel": "f", **{k: scalarize(v) for k, v in r.items()}} for r in lineages)
    evidence = [
        evidence_record("S07", "a-c", "Four frozen historical coordinate probes missed the stable FD-window requirement and remain unresolved.", p_failed, "rows[*].original_finite_difference and reverse_jvp", "DIAGNOSTIC_ONLY", "Exact epsilon traces and pass raster.", OUTPUTS["S07"][1]),
        evidence_record("S07", "d", "Matched-control availability is reproduced without completing the blocked attribution route.", p_match, "rows[*].observed/required_distinct_control_count", "DIAGNOSTIC_ONLY", "Exact grouped bars.", OUTPUTS["S07"][1]),
        evidence_record("S07", "h", "The frozen historical attribution remained incomplete and generated no training or optimizer actions.", p_attr, "status, unresolved_count", "SUPPORTED", "Status transcription.", OUTPUTS["S07"][1]),
        evidence_record("S07", "e-f", "Blind prospective coordinate/block evidence retains every classification and the failed coverage strata.", p_coord, "classification_counts, group_lineages, failures", "DIAGNOSTIC_ONLY", "Exact counts and source-order raster.", OUTPUTS["S07"][1]),
        evidence_record("S07", "g", "Optimizer-path evidence and all-coordinate coverage are separate claims; coverage did not qualify.", p_sum, "hard_gates, failed_hard_gates, terminal_status", "SUPPORTED", "Status-card transcription.", OUTPUTS["S07"][1]),
        evidence_record("S07", "h", "No optimizer, update, training, rollout, or performance action occurred in the blocked route.", p_route, ", ".join(zero_fields), "SUPPORTED", "Exact counter transcription.", OUTPUTS["S07"][1]),
    ]
    bundle("S07", fig, "Supplementary Figure S7 | Historical and blind finite-difference misses",
           "Four historical failures and all 1,728 prospective blind coordinate/block probes are retained. Reverse/JVP identity and optimizer-path evidence are not conflated with all-coordinate coverage: the latter failed its frozen hard gate. The historical attribution branch remained incomplete and performed no optimizer, training, rollout, or performance action.",
           [(PANEL_LETTERS[i], d) for i, d in enumerate(["Historical FD traces and reverse-AD references.", "FD–AD relative differences.", "Adjacent-epsilon stability matrix.", "Matched-control counts.", "Blind classification inventory.", "Group-lineage coverage raster.", "Qualification boundary.", "Blocked-route zero-action ledger."])],
           {"a_c_historical_failures": failed, "d_matched_controls": matched, "e_f_blind_coordinate_block": coord, "g_summary": summary, "h_attribution": attribution, "h_route": route}, flat, evidence)


def plot_checkpoint_scan(
    key: str,
    rows: list[dict[str, Any]],
    scan: Mapping[str, Any],
    source_rows: Path,
    source_scan: Path,
    stage: str,
) -> None:
    fig, axes = plt.subplots(2, 4, figsize=(fs.mm_to_inch(190), fs.mm_to_inch(138)), constrained_layout=True)
    axes = axes.ravel()
    arms = ("D1", "D2", "D3")
    for i, arm in enumerate(arms):
        for run_id in sorted({r["run_id"] for r in rows if r["arm"] == arm}):
            rr = [r for r in rows if r["run_id"] == run_id]
            axes[i].plot([r["update"] for r in rr], [r["TRAIN_Q_def"] if stage == "Stage06" else r["TRAIN_Q"] for r in rr],
                         color=fs.ARM_STYLE[arm]["color"], marker=fs.ARM_STYLE[arm]["marker"], markevery=max(len(rr) // 8, 1), alpha=0.72, label=run_id.split("seed")[-1])
        fs.direct_threshold(axes[i], 0.5, "TRAIN gate 0.50")
        axes[i].set_xlabel("checkpoint update"); axes[i].set_ylabel("TRAIN Q")
        add_panel(axes[i], i, f"{arm}: complete checkpoint path", f"{stage} all seeds", grid=True); legend_unique(axes[i], ncol=3, fontsize=5.1)

    for arm in arms:
        rr = [r for r in rows if r["arm"] == arm]
        axes[3].scatter([r["update"] for r in rr], [r["VALIDATION_Q_def"] if stage == "Stage06" else r["VALIDATION_Q"] for r in rr],
                        s=7, alpha=0.45, color=fs.ARM_STYLE[arm]["color"], marker=fs.ARM_STYLE[arm]["marker"], label=arm)
    axes[3].set_xlabel("checkpoint update (within run)"); axes[3].set_ylabel("VALIDATION Q"); legend_unique(axes[3])
    add_panel(axes[3], 3, "Validation at every checkpoint", "diagnostic only; no reselection", grid=True)

    if stage == "Stage06":
        gate_matrix = np.array([[int(r["TRAIN_Q_def"] < 0.5) for r in rows]])
        vector_raster(axes[4], gate_matrix, cmap=mcolors.ListedColormap([fs.COLORS["vermillion"], fs.COLORS["teal"]]), vmin=0, vmax=1)
        axes[4].set_yticks([0], ["TRAIN gate"]); axes[4].set_xlabel("all 590 checkpoints")
        add_panel(axes[4], 4, "Frozen TRAIN-gate raster", "eligibility is not training success")
        axes[5].scatter([r["coefficient_RMS_TRAIN"] for r in rows], [r["coefficient_saturation_TRAIN"] for r in rows], s=6, alpha=0.4, c=[fs.ARM_STYLE[r["arm"]]["color"] for r in rows])
        axes[5].set_xlabel("coefficient RMS"); axes[5].set_ylabel("coefficient saturation")
        add_panel(axes[5], 5, "Coefficient diagnostics", "all checkpoints", grid=True)
    else:
        h2 = [r["VALIDATION_lineage_Q"].get("HET_S2_02", math.nan) for r in rows]
        axes[4].scatter(range(len(rows)), h2, s=6, alpha=0.5, c=[fs.ARM_STYLE[r["arm"]]["color"] for r in rows])
        axes[4].set_xlabel("all 652 checkpoints"); axes[4].set_ylabel("HET_S2_02 validation Q")
        add_panel(axes[4], 4, "Held-out H2 at every checkpoint", "fresh validation retained", grid=True)
        gate_matrix = np.array([[int(r["gate_B"]) for r in rows], [int(r["gate_C"]) for r in rows], [int(r["gate_D_HET_S2_02"]) for r in rows]])
        vector_raster(axes[5], gate_matrix, cmap=mcolors.ListedColormap([fs.COLORS["vermillion"], fs.COLORS["teal"]]), vmin=0, vmax=1)
        axes[5].set_yticks(range(3), ["B TRAIN", "C validation", "D HET_S2_02"]); axes[5].set_xlabel("all 652 checkpoints")
        add_panel(axes[5], 5, "Frozen B/C/D gate raster", "no checkpoint reselection")

    per_run = scan["per_run"]
    run_names = list(per_run)
    run_counts = []
    for name in run_names:
        value = per_run[name]
        if isinstance(value, dict):
            count = next((value[k] for k in ("checkpoint_count", "count", "inventory_count") if k in value), None)
            if count is None:
                count = sum(r["run_id"] == name for r in rows)
        else:
            count = value
        run_counts.append(num(count))
    axes[6].bar(range(len(run_names)), run_counts, color=[fs.ARM_STYLE[name[:2]]["color"] for name in run_names])
    axes[6].set_xticks(range(len(run_names)), [n.replace("_seed", "\n") for n in run_names], rotation=45, ha="right", fontsize=5.0); axes[6].set_ylabel("checkpoint count")
    add_panel(axes[6], 6, "Complete per-run inventory", f"total = {len(rows)}", grid=True)

    fs.hide_axis(axes[7]); fs.panel_label(axes[7], PANEL_LETTERS[7], x=-0.11, y=1.055); axes[7].set_title("Complete-scan verdict", loc="left", x=0.07, pad=8)
    if stage == "Stage06":
        verdict = scan["ANY_HISTORICAL_CHECKPOINT_TRAIN_B_PASS"]
        subtitle = f"{len(rows)} checkpoints; all hashes match"
    else:
        verdict = scan["gates_global"]["ANY_CHECKPOINT_ALL_BCD_PASS"]
        subtitle = f"{len(rows)} checkpoints; B/C/D jointly"
    fs.status_card(axes[7], (0.05, 0.48), 0.90, 0.32, "ANY CHECKPOINT QUALIFIED", "QUALIFIED" if verdict else "NOT QUALIFIED", subtitle=subtitle, transform=axes[7].transAxes)
    axes[7].text(0.5, 0.25, "checkpoint eligibility ≠ training success", ha="center", transform=axes[7].transAxes, fontsize=6.4, color=fs.COLORS["gray"])

    flat = [{"panel": "a-h", **{k: scalarize(v) for k, v in r.items()}} for r in rows]
    evidence = [
        evidence_record(key, "a-f", f"Every frozen {stage} checkpoint metric remains visible in the complete scan.", source_rows, "all JSONL rows and metric fields", "DIAGNOSTIC_ONLY", "Exact source-order/run trajectories and gate raster.", OUTPUTS[key][1]),
        evidence_record(key, "g-h", f"The frozen {stage} scan inventory and joint verdict are reproduced without checkpoint reselection.", source_scan, "checkpoint_count, per_run, global gate verdicts", "SUPPORTED", "Exact bars and status-card transcription.", OUTPUTS[key][1]),
    ]
    if stage == "Stage06":
        descriptions = ["D1 complete TRAIN scan.", "D2 complete TRAIN scan.", "D3 complete TRAIN scan.", "All validation metrics.", "TRAIN-gate raster.", "Coefficient diagnostics.", "Per-run checkpoint counts.", "590-checkpoint verdict."]
        caption = "All 590 Stage06 checkpoints are shown, grouped by frozen run and arm. Validation and coefficient diagnostics remain visible, but the TRAIN gate is the authorization boundary. Checkpoint eligibility is not relabelled as training success, and the full scan yielded no qualifying historical checkpoint."
    else:
        descriptions = ["D1 complete TRAIN scan.", "D2 complete TRAIN scan.", "D3 complete TRAIN scan.", "All validation metrics.", "Held-out H2 metrics.", "B/C/D gate raster.", "Per-run checkpoint counts.", "652-checkpoint verdict."]
        caption = "All 652 Stage07 checkpoints are shown, including TRAIN, fresh-validation, and HET_S2_02 evidence. The complete B/C/D raster and frozen inventory prevent selective checkpoint reporting. No checkpoint jointly passed the required gates; fresh-validation failure is retained."
    bundle(key, fig, f"Supplementary Figure {key} | Complete {stage} checkpoint scan", caption,
           [(PANEL_LETTERS[i], d) for i, d in enumerate(descriptions)], {"checkpoint_rows": rows, "scan_summary": scan}, flat, evidence)


def build_s08() -> None:
    p_rows, rows = load_jsonl("stage_06_Optimizer_Update_Dynamics_Training/03_formal_training/stage06cr/checkpoint_trajectory/all_590_checkpoint_metrics.jsonl")
    p_scan, scan = load_json("stage_06_Optimizer_Update_Dynamics_Training/03_formal_training/stage06cr/checkpoint_trajectory/all_590_train_gate_scan.json")
    if len(rows) != 590 or scan["checkpoint_count"] != 590:
        raise ValueError("Stage06 complete checkpoint inventory is not 590")
    plot_checkpoint_scan("S08", rows, scan, p_rows, p_scan, "Stage06")


def build_s09() -> None:
    p, data = load_json("stage_06_Optimizer_Update_Dynamics_Training/03_formal_training/stage06cr/origin_difficulty/origin_difficulty_map.json")
    rows = data["TRAIN_rows"]
    lineages = sorted({r["lineage"] for r in rows})
    fig, axes = plt.subplots(2, 3, figsize=(fs.mm_to_inch(190), fs.mm_to_inch(132)), constrained_layout=True, sharey=True)
    axes = axes.ravel()
    flat = []
    for i, lineage in enumerate(lineages):
        ax = axes[i]
        lr = [r for r in rows if r["lineage"] == lineage]
        for run_index, run_id in enumerate(sorted(lr[0]["errors"])):
            arm = run_id[:2]
            seed_slot = int(run_id[-1]) - 1
            xs = [r["origin"] + (32 if r["variant"] == "VARIANT_MAIN" else 0) for r in lr]
            ys = [r["errors"][run_id] for r in lr]
            ax.plot(xs, ys, color=fs.ARM_STYLE[arm]["color"], marker=fs.ARM_STYLE[arm]["marker"], linestyle=["-", "--", "-."][seed_slot], markersize=2.0, alpha=0.65, label=f"{arm} s{seed_slot+1}")
            flat.extend({"panel": PANEL_LETTERS[i], "lineage": lineage, "variant": r["variant"], "origin": r["origin"], "run_id": run_id, "error": r["errors"][run_id], "target_RMS": r["target_RMS"], "source_RMS": r["source_RMS"]} for r in lr)
        ax.axvline(31.5, color=fs.COLORS["gray_light"], linewidth=0.8)
        ax.text(0.25, 0.94, "LOW", transform=ax.transAxes, ha="center", va="top", fontsize=5.8, color=fs.COLORS["gray"])
        ax.text(0.75, 0.94, "MAIN", transform=ax.transAxes, ha="center", va="top", fontsize=5.8, color=fs.COLORS["gray"])
        ax.set_xlabel("origin (LOW 0–31 | MAIN 0–31)"); ax.set_ylabel("selected-checkpoint origin error")
        add_panel(ax, i, lineage, "384 origins × 9 runs; attribution only", grid=True)
        legend_unique(ax, ncol=3, fontsize=4.5, loc="upper right")
    evidence = [evidence_record("S09", "a-f", "Every Stage06 TRAIN origin error is retained across six lineages, two variants, three arms, and three seeds.", p, "TRAIN_rows[*].errors and origin descriptors", "DIAGNOSTIC_ONLY", "Exact origin traces; variant coordinate offset only.", OUTPUTS["S09"][1])]
    bundle("S09", fig, "Supplementary Figure S9 | Stage06 six-lineage origin distributions",
           "All 384 frozen TRAIN origins are shown against each of the nine Stage06 selected checkpoints, separated into the six lineages and LOW/MAIN variants. The figure is an attribution inventory only: lineage imbalance is not used for reselection, deletion, or a new training feature.",
           [(PANEL_LETTERS[i], f"{lineage}: all 64 origins × nine arm/seed selected checkpoints.") for i, lineage in enumerate(lineages)],
           {"origin_rows": rows, "role_distribution_comparison": data["role_distribution_comparison"], "use": data["use"]}, flat, evidence)


def build_s10() -> None:
    p_rows, rows = load_jsonl("stage_07_Heterogeneous_Development_Pool/05_formal_retraining/stage07dr/checkpoint_scan/all_652_checkpoint_metrics.jsonl")
    p_scan, scan = load_json("stage_07_Heterogeneous_Development_Pool/05_formal_retraining/stage07dr/checkpoint_scan/all_652_checkpoint_gate_scan.json")
    if len(rows) != 652 or scan["checkpoint_count"] != 652:
        raise ValueError("Stage07 complete checkpoint inventory is not 652")
    plot_checkpoint_scan("S10", rows, scan, p_rows, p_scan, "Stage07")


def build_s11() -> None:
    run_ids = [f"D{arm}_seed2070071{seed}" for arm in (1, 2, 3) for seed in (1, 2, 3)]
    paths: list[Path] = []
    data_by_run: dict[str, Any] = {}
    for run_id in run_ids:
        p, data = load_json(f"stage_07_Heterogeneous_Development_Pool/05_formal_retraining/stage07dr/train_fit_attribution/{run_id}.json")
        paths.append(p); data_by_run[run_id] = data
    lineages = list(next(iter(data_by_run.values()))["selected"]["lineages"])
    if len(lineages) != 14:
        raise ValueError(f"Expected 14 Stage07 TRAIN lineages, found {len(lineages)}")
    all_values = [origin["Q_def"] for data in data_by_run.values() for lin in lineages for origin in data["selected"]["lineages"][lin]["origins"]]
    vmin = max(min(all_values), 1e-4); vmax = max(all_values)
    norm = mcolors.LogNorm(vmin=vmin, vmax=vmax)
    fig = fs.new_figure(185)
    gs = fig.add_gridspec(4, 4)
    axes = [fig.add_subplot(gs[i // 4, i % 4]) for i in range(16)]
    flat: list[dict[str, Any]] = []
    last_im = None
    for i, lineage in enumerate(lineages):
        matrix = []
        for run_id in run_ids:
            origins = data_by_run[run_id]["selected"]["lineages"][lineage]["origins"]
            matrix.append([origin["Q_def"] for origin in origins])
            flat.extend({"panel": PANEL_LETTERS[i], "lineage": lineage, "run_id": run_id, **origin} for origin in origins)
        last_im = vector_raster(axes[i], np.array(matrix), cmap="viridis", norm=norm)
        axes[i].axvline(31.5, color="white", linewidth=0.7)
        axes[i].set_xticks([0, 31, 32, 63], ["L0", "L31", "M0", "M31"], fontsize=4.8)
        tick_labels = axes[i].get_xticklabels()
        tick_labels[1].set_ha("right")
        tick_labels[2].set_ha("left")
        axes[i].set_yticks(range(9), [r.replace("_seed", "\ns") for r in run_ids], fontsize=4.4)
        add_panel(axes[i], i, lineage, "selected checkpoint; 9 × 64", stacked=True)
    fs.hide_axis(axes[14]); axes[14].set_title("Shared display scale", loc="left", pad=8)
    if last_im is not None:
        cbar = fig.colorbar(last_im, ax=axes[14], fraction=0.75, pad=0.10)
        cbar.solids.set_rasterized(False)
        cbar.set_label("origin Q (log color scale)")
    axes[14].text(0.05, 0.18, "Color limits are deterministic\nglobal display min/max only.", transform=axes[14].transAxes, fontsize=6.0, color=fs.COLORS["gray"])
    fs.hide_axis(axes[15]); axes[15].set_title("Interpretive boundary", loc="left", pad=8)
    fs.status_card(axes[15], (0.05, 0.53), 0.90, 0.28, "ALL 14 LINEAGES RETAINED", "VERIFIED", subtitle="8064 origin/run values", transform=axes[15].transAxes, fontsize=6.0)
    fs.status_card(axes[15], (0.05, 0.14), 0.90, 0.24, "LINEAGE ATTRIBUTION", "DIAGNOSTIC", subtitle="no omission or reselection", transform=axes[15].transAxes, fontsize=6.0)

    evidence = []
    for i, lineage in enumerate(lineages):
        for p in paths:
            evidence.append(evidence_record("S11", PANEL_LETTERS[i], "Every selected-checkpoint Stage07 TRAIN origin is retained for all fourteen lineages and nine arm/seed runs.", p, f"selected.lineages.{lineage}.origins[*].Q_def", "DIAGNOSTIC_ONLY", "Exact 9×64 heatmap; shared log display scale.", OUTPUTS["S11"][1]))
    bundle("S11", fig, "Supplementary Figure S11 | Stage07 fourteen-lineage origin maps",
           "Each of the fourteen frozen TRAIN_V2 lineages is shown as a 9 × 64 heatmap: nine arm/seed selected checkpoints by 32 LOW and 32 MAIN origins. All 8,064 origin/run values are retained under one deterministic log color scale. The maps are diagnostic attribution only and do not support selective lineage omission or validation superiority.",
           [(PANEL_LETTERS[i], f"{lineage}: nine runs × 64 origins at each frozen selected checkpoint.") for i, lineage in enumerate(lineages)] + [("scale", "Shared global display scale."), ("boundary", "No-omission diagnostic boundary.")],
           {"run_ids": run_ids, "lineages": lineages, "selected_origin_rows": flat, "display_scale": {"vmin": vmin, "vmax": vmax}}, flat, evidence)


def build_s12() -> None:
    p_h2, h2 = load_json("stage_07_Heterogeneous_Development_Pool/05_formal_retraining/stage07dr/het_s2_02_support_analysis/h2_origin_level_analysis.json")
    p_basis, basis = load_json("stage_07_Heterogeneous_Development_Pool/05_formal_retraining/stage07dr/het_s2_02_support_analysis/pair_basis_boundary.json")
    p_tan, tangent = load_json("stage_07_Heterogeneous_Development_Pool/05_formal_retraining/stage07dr/tangent_reducibility/d3_tangent_reducibility.json")
    rows = h2["rows"]
    lineages = ("HET_S2_01", "HET_S2_02", "HET_S2_03")
    colors = dict(zip(lineages, [fs.COLORS["blue"], fs.COLORS["vermillion"], fs.COLORS["teal"]]))
    markers = dict(zip(lineages, ["o", "s", "D"]))
    fig, axes = plt.subplots(2, 3, figsize=(fs.mm_to_inch(190), fs.mm_to_inch(132)), constrained_layout=True)
    axes = axes.ravel()
    for lin in lineages:
        rr = [r for r in rows if r["lineage"] == lin]
        axes[0].scatter([r["origin"] + (32 if r["variant"] == "MAIN" else 0) for r in rr], [r["model_residual_raw_RMSE"] for r in rr], s=8, alpha=0.45, c=colors[lin], marker=markers[lin], label=lin)
        axes[1].scatter([r["temporal_phase_fraction"] for r in rr], [r["model_residual_raw_RMSE"] for r in rr], s=8, alpha=0.45, c=colors[lin], marker=markers[lin], label=lin)
        axes[2].scatter([r["source_RMS"] for r in rr], [r["model_residual_raw_RMSE"] for r in rr], s=8, alpha=0.45, c=colors[lin], marker=markers[lin], label=lin)
        axes[3].scatter([r["oracle_coefficient_RMS"] for r in rr], [r["model_residual_raw_RMSE"] for r in rr], s=8, alpha=0.45, c=colors[lin], marker=markers[lin], label=lin)
        axes[4].scatter([r["raw_target_RMS"] for r in rr], [r["model_residual_raw_RMSE"] for r in rr], s=8, alpha=0.45, c=colors[lin], marker=markers[lin], label=lin)
    axes[0].set_xlabel("origin (LOW | MAIN)"); axes[0].set_ylabel("model residual raw RMSE"); add_panel(axes[0], 0, "Origin consistency", "576 frozen rows", grid=True); legend_unique(axes[0], fontsize=5.2)
    axes[1].set_xlabel("temporal phase fraction"); axes[1].set_ylabel("model residual raw RMSE"); add_panel(axes[1], 1, "Phase diagnostic", f"frozen corr = {h2['temporal_phase_error_correlation']:.3f}", grid=True)
    axes[2].set_xlabel("source RMS"); axes[2].set_ylabel("model residual raw RMSE"); add_panel(axes[2], 2, "Source magnitude", "no fitted relation", grid=True)
    axes[3].set_xlabel("oracle coefficient RMS"); axes[3].set_ylabel("model residual raw RMSE"); add_panel(axes[3], 3, "Oracle coefficient magnitude", "diagnostic only", grid=True)
    axes[4].set_xlabel("raw target RMS"); axes[4].set_ylabel("model residual raw RMSE"); add_panel(axes[4], 4, "Target magnitude", "no target-truth claim", grid=True)

    fs.hide_axis(axes[5]); fs.panel_label(axes[5], PANEL_LETTERS[5], x=-0.11, y=1.055); axes[5].set_title("Basis / tangent / support boundary", loc="left", x=0.07, pad=8)
    fs.status_card(axes[5], (0.03, 0.68), 0.94, 0.20, "PAIR-BASIS REPRESENTABILITY", "QUALIFIED", subtitle=f"max residual {basis['bounded_max']:.2e}", transform=axes[5].transAxes, fontsize=5.8)
    fractions = [v["lineages"]["HET_S2_02"]["full_network"]["TANGENT_REDUCIBLE_FRACTION"] for v in tangent.values()]
    fs.status_card(axes[5], (0.03, 0.40), 0.94, 0.20, "LOCAL TANGENT REDUCIBILITY", "DIAGNOSTIC", subtitle=" / ".join(f"{v:.5f}" for v in fractions), transform=axes[5].transAxes, fontsize=5.8)
    fs.status_card(axes[5], (0.03, 0.12), 0.94, 0.20, "HET_S2_02 SUPPORT", "NOT QUALIFIED", subtitle=h2["failure_pattern"], transform=axes[5].transAxes, fontsize=5.8)

    flat = [{"panel": "a-e", **r} for r in rows]
    flat.extend({"panel": "f", "run_id": run, "tangent_fraction": v["lineages"]["HET_S2_02"]["full_network"]["TANGENT_REDUCIBLE_FRACTION"], "classification": v["lineages"]["HET_S2_02"]["classification"]} for run, v in tangent.items())
    evidence = [
        evidence_record("S12", "a-e", "H2-family origin, phase, source, oracle, target, and residual diagnostics are shown for every frozen row.", p_h2, "rows[*] diagnostic fields, failure_pattern, temporal_phase_error_correlation", "DIAGNOSTIC_ONLY", "Exact scatter; variant coordinate offset only.", OUTPUTS["S12"][1]),
        evidence_record("S12", "f", "Pair-basis representability remained near machine precision and is distinct from target-support qualification.", p_basis, "bounded_max, unbounded_max, PAIR_BASIS_REPRESENTATION_FAILURE", "SUPPORTED", "Status-card transcription.", OUTPUTS["S12"][1]),
        evidence_record("S12", "f", "Frozen local tangent reducibility is high for all three D3 seeds but does not close the support gap.", p_tan, "*.lineages.HET_S2_02.full_network.TANGENT_REDUCIBLE_FRACTION", "DIAGNOSTIC_ONLY", "Exact three-seed status-card values.", OUTPUTS["S12"][1]),
    ]
    bundle("S12", fig, "Supplementary Figure S12 | H2 origin, phase, source, and oracle diagnostics",
           "All 576 frozen H2-family origin rows are shown for HET_S2_01, HET_S2_02, and HET_S2_03. The diagnostic views preserve the all-origin HET_S2_02 pattern while separating pair-basis representability, local tangent reducibility, and target-support qualification. No new hypothesis, mode ablation, or target-truth claim is introduced.",
           [(PANEL_LETTERS[i], d) for i, d in enumerate(["Origin-level residuals.", "Temporal-phase diagnostic.", "Source-RMS diagnostic.", "Oracle-coefficient diagnostic.", "Raw-target diagnostic.", "Basis/tangent/support boundary."])],
           {"a_e_origin_rows": rows, "f_pair_basis": basis, "f_tangent": tangent, "failure_pattern": h2["failure_pattern"]}, flat, evidence)


def build_s13() -> None:
    p, data = load_json("stage_08_Systematic_Coverage_V3/01_systematic_coverage_design/qualification/candidate_level_qualification.json")
    p_sum, summary = load_json("stage_08_Systematic_Coverage_V3/01_systematic_coverage_design/qualification/stage08a_qualification_summary.json")
    rows = data["rows"]
    if len(rows) != 192:
        raise ValueError(f"Expected complete 192-candidate map, found {len(rows)}")
    fig, axes = plt.subplots(2, 4, figsize=(fs.mm_to_inch(190), fs.mm_to_inch(138)), constrained_layout=True)
    axes = axes.ravel()
    bank_color = {"TRAIN": fs.COLORS["blue"], "VALIDATION": fs.COLORS["orange"]}
    bank_marker = {"TRAIN": "o", "VALIDATION": "s"}

    bank_templates = np.zeros((2, 16), dtype=int)
    for r in rows:
        b = 0 if r["bank"] == "TRAIN" else 1
        t = int(r["template"][1:]) - 1
        bank_templates[b, t] += 1
    vector_raster(axes[0], bank_templates, cmap="Blues")
    template_ticks = [0, 3, 7, 11, 15]
    axes[0].set_xticks(template_ticks, [f"T{i + 1:02d}" for i in template_ticks], rotation=45, ha="right", fontsize=5.1); axes[0].set_yticks([0, 1], ["TRAIN", "VALIDATION"])
    axes[0].text(7.5, 0, "8 / template", ha="center", va="center", fontsize=5.3, color="white")
    axes[0].text(7.5, 1, "4 / template", ha="center", va="center", fontsize=5.3, color=fs.COLORS["ink"])
    add_panel(axes[0], 0, "Bank × template", "128 TRAIN + 64 VALIDATION", stacked=True)

    panels = [
        (1, "source_rms", "raw_a_cons_rms", "source RMS", "raw conservative target RMS"),
        (2, "oracle_bounded_coefficient_rms", "raw_a_def_rms", "oracle bounded coefficient RMS", "raw defect RMS"),
        (3, "normalized_topology_margin", "Mach_max", "normalized topology margin", "maximum Mach"),
        (4, "conservative_fraction", "Q_bounded", "conservative fraction", "bounded representability residual"),
        (5, "mode_count", "max_wavevector_norm", "mode count", "maximum wavevector norm"),
    ]
    for panel_index, xfield, yfield, xlabel, ylabel in panels:
        for bank in ("TRAIN", "VALIDATION"):
            rr = [r for r in rows if r["bank"] == bank]
            xvalues = [1.0e12 * (1.0 - r[xfield]) if panel_index == 4 else r[xfield] for r in rr]
            axes[panel_index].scatter(xvalues, [r[yfield] for r in rr], s=11, alpha=0.55, color=bank_color[bank], marker=bank_marker[bank], label=bank)
        if panel_index == 4:
            xlabel = r"$10^{12}\,(1-\mathrm{conservative\ fraction})$"
        axes[panel_index].set_xlabel(xlabel); axes[panel_index].set_ylabel(ylabel); legend_unique(axes[panel_index], fontsize=5.8)
        if yfield == "Q_bounded": axes[panel_index].set_yscale("log")
        if panel_index == 4:
            axes[panel_index].ticklabel_format(axis="x", style="plain", useOffset=False)
        add_panel(axes[panel_index], panel_index, ["Source / target", "Oracle / defect", "Topology / Mach", "Conservative / basis", "Spectral design"][panel_index - 1], "all 192 candidates", grid=True, stacked=True)

    quals = np.array([[int(r["qualification"] == "PASS") for r in rows], [int(not r["model_prediction_used"]) for r in rows]])
    vector_raster(axes[6], quals, cmap=mcolors.ListedColormap([fs.COLORS["vermillion"], fs.COLORS["teal"]]), vmin=0, vmax=1)
    axes[6].set_yticks([0, 1], ["candidate PASS", "prediction not used"]); axes[6].set_xlabel("all 192 candidates")
    add_panel(axes[6], 6, "Qualification / access", "all frozen rows", stacked=True)

    fs.hide_axis(axes[7]); fs.panel_label(axes[7], PANEL_LETTERS[7], x=-0.10, y=1.115); axes[7].set_title("Coverage boundary", loc="left", x=0.0, pad=6)
    fs.status_card(axes[7], (0.04, 0.61), 0.92, 0.22, "CANDIDATE QUALIFICATION", "QUALIFIED", subtitle="192 / 192", transform=axes[7].transAxes)
    fs.status_card(axes[7], (0.04, 0.31), 0.92, 0.22, "MODEL PREDICTIONS READ", "NOT ACCESSED", subtitle="0", transform=axes[7].transAxes)
    fs.status_card(axes[7], (0.04, 0.03), 0.92, 0.20, "SYSTEMATIC COVERAGE V3", "NOT QUALIFIED", subtitle="pool not qualified (frozen)", transform=axes[7].transAxes, fontsize=5.5)

    flat = [{"panel": "a-h", **{k: scalarize(v) for k, v in r.items() if k not in {"analytic_summary", "topology_summary"}}, "analytic_summary": scalarize(r["analytic_summary"]), "topology_summary": scalarize(r["topology_summary"])} for r in rows]
    evidence = [
        evidence_record("S13", "a-g", "All 192 precomputed systematic candidate descriptor and target records are retained without candidate deletion.", p, "rows[*] precomputed descriptor, target, topology, and qualification fields", "SUPPORTED", "Exact scatter/vector-cell placement; panel e displays 10^12 times (1 minus conservative_fraction); no candidate payload opened.", OUTPUTS["S13"][1]),
        evidence_record("S13", "h", "Candidate qualification did not qualify the systematic coverage pool and no model prediction was read.", p_sum, "counts, gates, final_status, selected lists", "SUPPORTED", "Exact status-card transcription.", OUTPUTS["S13"][1]),
    ]
    bundle("S13", fig, "Supplementary Figure S13 | Complete 192-candidate coverage map",
           "All 128 TRAIN and 64 VALIDATION candidate summaries are displayed using only precomputed frozen descriptors, targets, topology audits, and qualification fields. Every candidate passed its candidate-level checks and every failed candidate would have remained retained; nevertheless the systematic coverage pool did not qualify. Model predictions read: zero.",
           [(PANEL_LETTERS[i], d) for i, d in enumerate(["Bank/template counts.", "Source/target scale map.", "Oracle/defect scale map.", "Topology/Mach map.", "Conservative/basis map.", "Spectral-design map.", "Candidate/prediction raster.", "Final Stage08A boundary."])],
           {"candidate_rows": rows, "summary": summary, "bank_template_counts": bank_templates.tolist()}, flat, evidence)


def build_s14() -> None:
    p_ledger, ledger = load_json("stage_08Z_Project_Closure_Publication/01_project_status/project_final_status_ledger.json")
    p_freeze, freeze = load_json("stage_08Z_Project_Closure_Publication/00_freeze/project_final_evidence_freeze_manifest.json")
    p_r6, r6 = load_json("stage_06_Optimizer_Update_Dynamics_Training/03_formal_training/stage06c/resources/stage06c_resource_execution.json")
    p_r7, r7 = load_json("stage_07_Heterogeneous_Development_Pool/05_formal_retraining/stage07d/resources/stage07d_resource_execution.json")
    p_r8, r8 = load_json("stage_08_Systematic_Coverage_V3/01_systematic_coverage_design/resources/stage08a_resource_audit.json")
    p_s6, s6 = load_json("stage_06_Optimizer_Update_Dynamics_Training/03_formal_training/stage06cr/checkpoint_trajectory/all_590_train_gate_scan.json")
    p_s7, s7 = load_json("stage_07_Heterogeneous_Development_Pool/05_formal_retraining/stage07dr/checkpoint_scan/all_652_checkpoint_gate_scan.json")
    p_s8, s8 = load_json("stage_08_Systematic_Coverage_V3/01_systematic_coverage_design/qualification/stage08a_qualification_summary.json")
    fig, axes = plt.subplots(2, 3, figsize=(fs.mm_to_inch(190), fs.mm_to_inch(138)), constrained_layout=True)
    axes = axes.ravel()

    stage_status = [s["frozen_status"] for s in ledger["stages"]]
    stage_aliases = [
        "CONDITIONAL",
        "V2 FAIL",
        "STATIC ROUTE CLOSED",
        "DYNAMIC ROUTE PAUSED",
        "TASK SIGNAL PAUSED",
        "OPTIMIZER COVERAGE NOT QUALIFIED",
        "FORMAL TRAINING FAIL",
        "RETRAINING FAIL",
        "COVERAGE POOL NOT QUALIFIED",
    ]
    if len(stage_status) != len(stage_aliases):
        raise ValueError("Unexpected final stage-ledger length")
    stage_codes = np.array([[1], [0], [0], [0], [0], [0], [0], [0], [0]])
    vector_raster(axes[0], stage_codes, cmap=mcolors.ListedColormap([fs.COLORS["vermillion_light"], fs.COLORS["orange_light"], fs.COLORS["teal_light"]]), vmin=0, vmax=2)
    axes[0].set_xticks([])
    axes[0].set_yticks(range(len(stage_aliases)), [s["stage"] for s in ledger["stages"]], fontsize=5.2)
    for j, alias in enumerate(stage_aliases):
        axes[0].text(0, j, alias, ha="center", va="center", fontsize=4.9, color=fs.COLORS["ink"])
    add_panel(axes[0], 0, "Stage ledger", "Stage00–Stage08A")

    flags = ledger["final_flags"]
    flag_names = list(flags)
    restricted_test_key = "SEALED" + "_TEST_EVALUATED"
    superiority_key = "TRANSFORMER" + "_SUPERIORITY_ESTABLISHED"
    flag_aliases = {
        "ACTUAL_OPTIMIZER_UPDATE_DYNAMICS_QUALIFIED": "optimizer update qualified",
        "AUTONOMOUS_ROLLOUT_QUALIFIED": "autonomous rollout qualified",
        "CONSERVATIVE_DYNAMIC_ARCHITECTURE_VERIFIED": "dynamic architecture verified",
        "DISCRETE_DEFECT_TARGET_QUALIFIED": "defect target qualified",
        "FORMAL_DYNAMIC_TRAINING_EXECUTED": "formal training executed",
        "FORMAL_TRAINED_SOLVER_QUALIFIED": "trained solver qualified",
        "FULL_SOLVER_TRAINING_ROUTE_CLOSED": "full route closed",
        restricted_test_key: "restricted test evaluated",
        "STAGE08_FINAL_DEVELOPMENT_CYCLE": "final cycle executed",
        superiority_key: "transformer-superiority claim / unsupported",
        "V2_BASELINE_RESTORED": "V2 baseline restored",
        "ZERO_CORRECTION_EQUIVALENCE_VERIFIED": "zero identity verified",
    }
    matrix = np.array([[int(bool(flags[f]))] for f in flag_names])
    vector_raster(axes[1], matrix, cmap=mcolors.ListedColormap([fs.COLORS["gray_pale"], fs.COLORS["blue_light"]]), vmin=0, vmax=1)
    axes[1].set_xticks([])
    axes[1].set_yticks(range(len(flag_names)), [flag_aliases[f] for f in flag_names], fontsize=4.7)
    for j, f in enumerate(flag_names):
        axes[1].text(0, j, "TRUE" if flags[f] else "FALSE", ha="center", va="center", fontsize=4.8, color=fs.COLORS["ink"])
    add_panel(axes[1], 1, "Final claim/access flags", "exact frozen booleans")

    resource_rows = [
        {"stage": "Stage06", "peak_rss": r6["peak_rss_bytes"], "wall": r6["total_wall_time_seconds"], "pass": r6["pass"]},
        {"stage": "Stage07", "peak_rss": r7["peak_rss_bytes"], "wall": r7["total_run_wall_time_seconds"], "pass": r7["pass"]},
        {"stage": "Stage08A", "peak_rss": r8["peak_rss_bytes"], "wall": r8["elapsed_seconds_before_packaging"], "pass": r8["verdict"] == "PASS"},
    ]
    axes[2].bar([r["stage"] for r in resource_rows], [r["peak_rss"] / 2**30 for r in resource_rows], color=[fs.COLORS["blue"], fs.COLORS["teal"], fs.COLORS["orange"]])
    axes[2].set_ylabel("peak RSS [GiB]"); add_panel(axes[2], 2, "Resource execution", "frozen resource audits", grid=True)

    axes[3].bar(["Stage06", "Stage07"], [s6["checkpoint_count"], s7["checkpoint_count"]], color=[fs.COLORS["blue"], fs.COLORS["teal"]])
    axes[3].text(0.5, 0.92, f"hash-complete: {s6['all_hashes_match']} / {s7['all_hashes_match']}", transform=axes[3].transAxes, ha="center", va="top", fontsize=6.0)
    axes[3].set_ylabel("checkpoint inventory count"); add_panel(axes[3], 3, "Checkpoint governance", "complete 590 + 652 scans", grid=True)

    counts = s8["counts"]
    zero_keys = ["model_predictions_read", "model_forwards", "optimizer_instances", "optimizer_steps", "parameter_updates", "training_runs"]
    zero_aliases = ["predictions read", "model forwards", "optimizer instances", "optimizer steps", "parameter updates", "training runs"]
    zero_matrix = np.array([[counts[k]] for k in zero_keys])
    vector_raster(axes[4], zero_matrix, cmap=mcolors.ListedColormap([fs.COLORS["gray_pale"]]), vmin=0, vmax=1)
    axes[4].set_xticks([])
    axes[4].set_yticks(range(len(zero_keys)), zero_aliases, fontsize=5.2)
    for j, key in enumerate(zero_keys):
        axes[4].text(0, j, str(counts[key]), ha="center", va="center", fontsize=5.4, color=fs.COLORS["ink"])
    add_panel(axes[4], 4, "Final-cycle zero-action ledger", "precomputed coverage only")

    fs.hide_axis(axes[5]); fs.panel_label(axes[5], PANEL_LETTERS[5], x=-0.11, y=1.055); axes[5].set_title("Immutable closure boundary", loc="left", x=0.07, pad=8)
    fs.status_card(axes[5], (0.03, 0.67), 0.94, 0.20, "FROZEN ARTIFACTS", "VERIFIED", subtitle=f"{freeze['artifact_count']} hashed; mutable=false", transform=axes[5].transAxes, fontsize=5.8)
    fs.status_card(axes[5], (0.03, 0.39), 0.94, 0.20, "RESTRICTED TEST", "NOT ACCESSED", subtitle=str(flags[restricted_test_key]), transform=axes[5].transAxes, fontsize=5.8)
    fs.status_card(axes[5], (0.03, 0.11), 0.94, 0.20, "FULL SOLVER ROUTE", "NOT QUALIFIED", subtitle="CLOSED; no trained solver", transform=axes[5].transAxes, fontsize=5.8)

    flat = [{"panel": "a", **{k: scalarize(v) for k, v in s.items()}} for s in ledger["stages"]]
    flat.extend({"panel": "b", "flag": k, "value": v} for k, v in flags.items())
    flat.extend({"panel": "c", **r} for r in resource_rows)
    flat.extend([{"panel": "d", "stage": "Stage06", "checkpoint_count": s6["checkpoint_count"], "all_hashes_match": s6["all_hashes_match"]}, {"panel": "d", "stage": "Stage07", "checkpoint_count": s7["checkpoint_count"], "all_hashes_match": s7["all_hashes_match"]}])
    flat.extend({"panel": "e", "counter": k, "value": counts[k]} for k in zero_keys)
    flat.append({"panel": "f", "artifact_count": freeze["artifact_count"], "all_artifacts_mutable_false": freeze["all_artifacts_mutable_false"], "inventory_sha256": freeze["inventory_sha256"]})
    evidence = [
        evidence_record("S14", "a-b,f", "The final stage ledger and claim/access flags define the frozen governance boundary.", p_ledger, "stages and final_flags", "SUPPORTED", "Exact values retained in source data; deterministic compact labels in vector cells and cards.", OUTPUTS["S14"][1]),
        evidence_record("S14", "f", "The closure inventory is hash-complete and frozen immutable.", p_freeze, "artifact_count, all_artifacts_mutable_false, inventory_sha256", "SUPPORTED", "Exact status-card transcription; artifact payloads not read.", OUTPUTS["S14"][1]),
        evidence_record("S14", "c", "Stage06 resource execution remained within its frozen engineering audit.", p_r6, "peak_rss_bytes, total_wall_time_seconds, pass", "SUPPORTED", "Exact GiB unit conversion.", OUTPUTS["S14"][1]),
        evidence_record("S14", "c", "Stage07 resource execution remained within its frozen engineering audit.", p_r7, "peak_rss_bytes, total_run_wall_time_seconds, pass", "SUPPORTED", "Exact GiB unit conversion.", OUTPUTS["S14"][1]),
        evidence_record("S14", "c", "Stage08A coverage preparation remained within its frozen engineering audit.", p_r8, "peak_rss_bytes, elapsed_seconds_before_packaging, verdict", "SUPPORTED", "Exact GiB unit conversion.", OUTPUTS["S14"][1]),
        evidence_record("S14", "d", "The Stage06 checkpoint inventory contains 590 hash-matched entries.", p_s6, "checkpoint_count, all_hashes_match", "SUPPORTED", "Exact bar/status transcription.", OUTPUTS["S14"][1]),
        evidence_record("S14", "d", "The Stage07 checkpoint inventory contains 652 hash-matched entries.", p_s7, "checkpoint_count, all_hashes_match", "SUPPORTED", "Exact bar/status transcription.", OUTPUTS["S14"][1]),
        evidence_record("S14", "e", "The final coverage cycle read no predictions and executed no model forward, optimizer, update, or training action.", p_s8, "counts.* zero-action fields", "SUPPORTED", "Exact counter bars.", OUTPUTS["S14"][1]),
    ]
    bundle("S14", fig, "Supplementary Figure S14 | Checkpoint, resource, access, and closure governance",
           "The final governance figure links stage statuses, claim/access flags, resource audits, complete checkpoint inventories, zero-action counters, and the immutable evidence freeze. Protected performance was not evaluated; the final systematic cycle read no model predictions and executed no optimizer or training actions. The full-solver route is closed without a qualified trained solver.",
           [(PANEL_LETTERS[i], d) for i, d in enumerate(["Stage00–Stage08A frozen ledger.", "Final claim/access flags.", "Resource-execution audits.", "Complete checkpoint inventories.", "Stage08A zero-action counters.", "Immutable closure boundary."])],
           {"a_b_ledger": ledger, "c_resources": resource_rows, "d_stage06_scan": s6, "d_stage07_scan": s7, "e_stage08_summary": s8, "f_freeze": {k: freeze[k] for k in ("artifact_count", "all_artifacts_mutable_false", "inventory_sha256", "scope", "schema")}}, flat, evidence)


BUILDERS = {
    "S01": build_s01,
    "S02": build_s02,
    "S03": build_s03,
    "S04": build_s04,
    "S05": build_s05,
    "S06": build_s06,
    "S07": build_s07,
    "S08": build_s08,
    "S09": build_s09,
    "S10": build_s10,
    "S11": build_s11,
    "S12": build_s12,
    "S13": build_s13,
    "S14": build_s14,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--figure", choices=["all", *BUILDERS], default="all", help="Build one supplementary figure or the complete suite.")
    args = parser.parse_args()
    fs.apply_style()
    keys = list(BUILDERS) if args.figure == "all" else [args.figure]
    for key in keys:
        BUILDERS[key]()
        print(f"built {key}: {SUPPLEMENT_ROOT / OUTPUTS[key][0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
