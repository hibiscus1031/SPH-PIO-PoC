#!/usr/bin/env python3
"""Build the frozen graphical abstract and CMAME Figures 1--10.

This is a publication-display program only.  It reads a small allowlist of frozen,
public, machine-readable evidence.  It never imports project solver/model/training
code and never opens restricted artifacts.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import sys
import textwrap
from pathlib import Path
from typing import Any, Iterable

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle


ROOT = Path(__file__).resolve().parents[3]
SUITE = ROOT / "publication_cmame_v1" / "04_figures"
sys.path.insert(0, str(SUITE / "00_style"))

from figure_style import (  # noqa: E402
    ARM_STYLE,
    COLORS,
    ROLE_STYLE,
    arrow,
    direct_threshold,
    hide_axis,
    new_figure,
    panel_label,
    provenance_tag,
    save_figure,
    status_card,
    style_axis,
)


FORBIDDEN_SOURCE_FRAGMENTS = (
    "_".join(("LCDF", "03")),
    "_".join(("LCDF", "10")),
    "_".join(("lcdf", "03")),
    "_".join(("lcdf", "10")),
    "/pri" + "vate/",
    "sealed_" + "test",
    "fresh_validation_" + "seal",
    "/test_" + "seal/",
    "test_release_" + "manifest",
)

FIGURES: dict[str, dict[str, Any]] = {
    "graphical_abstract": {
        "directory": "01_graphical_abstract",
        "basename": "graphical_abstract",
        "title": "Qualification gates separate verified components from the closed full-solver route",
        "panels": ["route"],
    },
    "fig01": {
        "directory": "02_fig01_framework",
        "basename": "fig01_framework",
        "title": "Qualification-first evidence framework",
        "panels": ["a", "b", "c", "d", "e"],
    },
    "fig02": {
        "directory": "03_fig02_architecture",
        "basename": "fig02_architecture",
        "title": "Conservative-compatible dynamic neural-SPH architecture",
        "panels": list("abcdefghi"),
    },
    "fig03": {
        "directory": "04_fig03_verification",
        "basename": "fig03_verification",
        "title": "Numerical and dynamic verification with an explicit V2 boundary",
        "panels": list("abcdefg"),
    },
    "fig04": {
        "directory": "05_fig04_failed_learning_routes",
        "basename": "fig04_failed_learning_routes",
        "title": "Falsified learning routes and attenuation of the raw next-state signal",
        "panels": list("abcdefg"),
    },
    "fig05": {
        "directory": "06_fig05_discrete_defect",
        "basename": "fig05_discrete_defect",
        "title": "Scale-aware conservative discrete-defect target",
        "panels": list("abcdefgh"),
    },
    "fig06": {
        "directory": "07_fig06_optimizer_qualification",
        "basename": "fig06_optimizer_qualification",
        "title": "Gradient evidence and actual optimizer-path qualification",
        "panels": list("abcdefgh"),
    },
    "fig07": {
        "directory": "08_fig07_formal_training_v1",
        "basename": "fig07_formal_training_v1",
        "title": "First formal dynamic campaign: nine executed runs, no TRAIN qualification",
        "panels": list("abcdefgh"),
    },
    "fig08": {
        "directory": "09_fig08_heterogeneous_retraining",
        "basename": "fig08_heterogeneous_retraining",
        "title": "Prospective heterogeneity and the second formal campaign",
        "panels": list("abcdefghi"),
    },
    "fig09": {
        "directory": "10_fig09_support_gap",
        "basename": "fig09_support_gap",
        "title": "Held-out H2 support gap: representable basis, unsupported correction target",
        "panels": list("abcdefghi"),
    },
    "fig10": {
        "directory": "11_fig10_systematic_coverage",
        "basename": "fig10_systematic_coverage",
        "title": "Systematic coverage-by-design and evidence-based route closure",
        "panels": list("abcdefghij"),
    },
}


CAPTIONS = {
    "graphical_abstract": (
        "Frozen qualification route. Blue/teal cards denote verified or qualified layers; "
        "hatched vermillion cards denote criteria that were not qualified. The route ends in "
        "evidence-based closure and does not represent a successful trained solver."
    ),
    "fig01": (
        "Qualification-first framework. (a) The scientific objective separates a conservative "
        "dynamic architecture from the stronger trained-solver claim. (b) Reference roles are "
        "hierarchical; the finite-resolution V2 route remains not qualified. (c) Authorization "
        "requires distinct structure, target, gradient, optimizer, training, validation, support, "
        "and governance gates. (d) Frozen failures F1--F9 triggered bounded methodological "
        "responses rather than monotone tuning. (e) Final claim boundary. Stage identifiers are "
        "provenance tags only."
    ),
    "fig02": (
        "Conservative-compatible dynamic neural-SPH construction. (a--e) An unordered neighbor "
        "pair is evaluated once, resolved in radial/transverse bases, and applied reciprocally so "
        "that the correction forces are antisymmetric. (f) D1--D3 are comparison arms, not a "
        "performance ranking. (g,h) Midpoint RK2 rebuilds the graph at each source evaluation and "
        "commits only accepted states to causal history. (i) D0 is the exact zero-correction "
        "identity. These contracts establish architecture semantics, not trainability."
    ),
    "fig03": (
        "Frozen numerical and dynamic verification. (a) Reference roles are kept distinct. "
        "(b) Plateau-aware MMS evidence supports its registered consistency path without a GCI "
        "claim. (c) Zero correction passed 288/288 bitwise cases. (d) Independent D0 RK2 checks "
        "passed 48/48; D0-versus-exact diagnostics are not a V2 recovery claim. (e) Dense topology "
        "scans localize birth/death events. (f) All 540 registered conservation stages passed. "
        "(g) The dynamic implementation was verified while finite-resolution V2 and the complete "
        "Stage03 route remained not qualified."
    ),
    "fig04": (
        "Frozen evidence for failed learning routes and signal attenuation. (a,b) All 18 static "
        "TRAIN histories and their registered gates are retained. (c) The complete 864-by-three "
        "directional matrix contains nonzero sensitivities but mixed attribution. (d--f) State "
        "residuals, projection dilution, and RK2 scaling diagnose attenuation of the raw next-state "
        "signal. (g) The scale-aware defect target is the authorized methodological response, not "
        "proof that training will succeed."
    ),
    "fig05": (
        "Frozen qualification of the scale-aware conservative discrete defect. (a,b) Accepted-state "
        "and velocity-defect geometry are schematic or deterministic transforms of a frozen origin. "
        "(c) The target decomposes into conservative and center-of-mass-incompatible parts. (d--f) "
        "Signal-to-uncertainty, incompatibility, and pair-basis residuals satisfy the registered target "
        "gates across 384 origins. (g) The later prospectively requalified v2 scale is shown only as "
        "a distributional change. (h) The zero identity is retained. Target qualification is not "
        "training qualification and does not establish target truth."
    ),
    "fig06": (
        "Gradient-to-optimizer qualification. (a,b) Registered full-gradient and reverse/JVP tests "
        "were active and internally consistent. (c) Historical and prospective coordinate/block "
        "coverage retained their misses, so all-coordinate FD was not qualified. (d) Frozen "
        "optimizer-path directional FD passed. (e) Descent probes restored parameters without "
        "writeback. (f,g) Actual AdamW one-step and two-/four-step micro-trajectories qualified in "
        "Stage06A. (h) The evidence ladder explicitly separates the failed coordinate-wide claim from "
        "the qualified actual update path."
    ),
    "fig07": (
        "First formal dynamic campaign. (a--c) TRAIN Q trajectories for D1--D3 show all three seeds "
        "per arm against the frozen Q=0.50 gate. (d) Validation trajectories are displayed by role, "
        "not as a success criterion replacing TRAIN. (e,f) Selected global and lineage-resolved "
        "values preserve every run. (g) None of the 590 historical checkpoints passed the TRAIN "
        "gate. (h) Each arm finished with 0/3 seed passes. Validation behavior, including D3, does "
        "not establish Transformer superiority."
    ),
    "fig08": (
        "Prospective heterogeneous retraining. (a--c) The development pool expands from six to 14 "
        "TRAIN lineages across four registered strata, and the frozen target scale changes. (d--g) "
        "Every Stage07 run and lineage remains visible for TRAIN and fresh-validation roles. (h) "
        "The common-anchor raw acceleration error is the permitted cross-campaign comparison. (i) "
        "Branch B was not supported; no trained solver or validation qualification was established."
    ),
    "fig09": (
        "Support-gap diagnosis for HET_S2_02. (a) The H2 formula family and three spatial modes are "
        "prospectively registered. (b,c) Frozen descriptor distances and envelope exceedances show "
        "the robust-descriptor gap. (d,e) TRAIN-only target-space PCA places the held-out correction "
        "target above its frozen residual threshold. (f,g) D3 cross-lineage cosines and three seed "
        "diagnostics retain gradient conflict. (h,i) Pair-basis representability, local tangent "
        "reducibility, and origin consistency are distinct from target support."
    ),
    "fig10": (
        "Systematic coverage-by-design and closure. (a--c) Sixteen templates generated a frozen "
        "128-candidate TRAIN bank and 64-candidate validation bank; eight TRAIN candidates were "
        "selected without model predictions. (d--f) HET_S2_02 descriptor distance fell from 6.5115 "
        "to 1.8607, but its target residual 3.5113 exceeded the 1.5385 TRAIN threshold. (g,h) Only "
        "two provisional macro-group winners were eligible and formal fresh closure remained 0/4. "
        "(i,j) Model-prediction reads were zero and the full-solver route closed with lower layers "
        "qualified but training, rollout, and sealed-test claims unqualified."
    ),
}


PANEL_SPECS = {
    "graphical_abstract": ["route — verified/qualified layers, failed gates, and final closure"],
    "fig01": [
        "(a) scientific objective and claim separation",
        "(b) V0--V3/reference hierarchy",
        "(c) qualification ladder",
        "(d) cross-stage failure/response graph",
        "(e) final claim boundary",
    ],
    "fig02": [
        "(a) neighbor graph", "(b) unordered reciprocal edge", "(c) radial/transverse basis",
        "(d) coefficient head", "(e) antisymmetry", "(f) D1/D2/D3 arms",
        "(g) midpoint RK2", "(h) accepted-only history", "(i) D0 zero identity",
    ],
    "fig03": [
        "(a) reference hierarchy", "(b) MMS/convergence path", "(c) 288/288 zero identity",
        "(d) 48/48 independent D0 RK2", "(e) topology event scan",
        "(f) conservation residuals", "(g) verification boundary",
    ],
    "fig04": [
        "(a) all 18 static TRAIN histories", "(b) static gate matrix",
        "(c) complete 2,592 directional entries", "(d) state residual distributions",
        "(e) projection dilution", "(f) RK2 velocity/position scaling",
        "(g) authorized target transition",
    ],
    "fig05": [
        "(a) same-origin accepted transition", "(b) velocity-defect geometry",
        "(c) conservative decomposition", "(d) signal versus uncertainty",
        "(e) incompatible fraction", "(f) bounded/unbounded pair-basis residuals",
        "(g) v1/v2 scale values", "(h) zero-correction identity",
    ],
    "fig06": [
        "(a) full-gradient activity", "(b) reverse/JVP identity",
        "(c) coordinate/block FD coverage", "(d) optimizer-path FD",
        "(e) no-writeback descent", "(f) AdamW one-step loss change",
        "(g) two-/four-step micro-trajectories", "(h) qualification ladder",
    ],
    "fig07": [
        "(a--c) D1/D2/D3 TRAIN histories", "(d) validation histories",
        "(e) selected global Q", "(f) six-lineage selected Q",
        "(g) all-590 checkpoint scan", "(h) 0/3 per arm verdict",
    ],
    "fig08": [
        "(a) 6-to-14 TRAIN design", "(b) H1--H4 strata", "(c) scale shift",
        "(d) TRAIN_V2 histories", "(e) fresh-validation histories",
        "(f) 14-lineage matrix", "(g) four validation-lineage matrix",
        "(h) common-anchor raw RMSE", "(i) Branch B verdict",
    ],
    "fig09": [
        "(a) H2 formulas/modes", "(b) robust descriptor distances",
        "(c) envelope exceedances", "(d) TRAIN-only target PCA coefficients",
        "(e) target residual and threshold", "(f) D3 cross-lineage cosine matrix",
        "(g) three-seed conflict", "(h) tangent reducibility", "(i) origin consistency",
    ],
    "fig10": [
        "(a) 16 structural templates", "(b) 128+64 candidate banks",
        "(c) eight selected TRAIN candidates", "(d) descriptor change",
        "(e) target residual/gate", "(f) descriptor versus target verdict",
        "(g) four validation macro groups", "(h) 0/4 formal closure",
        "(i) zero model-prediction reads", "(j) final qualification ladder",
    ],
}


SOURCE_HASHES: dict[str, str] = {}


def _safe_source(relative: str) -> Path:
    normalized = relative.replace("\\", "/")
    if any(fragment in normalized for fragment in FORBIDDEN_SOURCE_FRAGMENTS):
        raise PermissionError(f"Protected source blocked by publication builder: {relative}")
    path = (ROOT / relative).resolve()
    if ROOT not in path.parents:
        raise PermissionError(f"Source outside repository: {relative}")
    if not path.is_file():
        raise FileNotFoundError(relative)
    return path


def source_hash(relative: str) -> str:
    if relative not in SOURCE_HASHES:
        path = _safe_source(relative)
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        SOURCE_HASHES[relative] = f"sha256:{digest.hexdigest()}"
    return SOURCE_HASHES[relative]


def load_json(relative: str) -> Any:
    path = _safe_source(relative)
    source_hash(relative)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_jsonl(relative: str) -> list[dict[str, Any]]:
    path = _safe_source(relative)
    source_hash(relative)
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def load_csv(relative: str) -> list[dict[str, str]]:
    path = _safe_source(relative)
    source_hash(relative)
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_npz(relative: str) -> dict[str, np.ndarray]:
    """Read frozen numeric arrays without executing pickled objects."""
    path = _safe_source(relative)
    source_hash(relative)
    with np.load(path, allow_pickle=False) as archive:
        return {key: np.asarray(archive[key]) for key in archive.files}


def ev(
    figure: str,
    panel: str,
    claim: str,
    source_file: str,
    source_field: str,
    evidence_class: str,
    transformation: str,
) -> dict[str, str]:
    return {
        "figure": figure,
        "panel": panel,
        "scientific_claim": claim,
        "source_file": source_file,
        "source_hash": source_hash(source_file),
        "source_field": source_field,
        "confirmatory_or_diagnostic": evidence_class,
        "transformation": transformation,
        "plot_script": "publication_cmame_v1/04_figures/00_style/build_main_figures.py",
        "output_file": "",
    }


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _flatten_rows(value: Any, prefix: str = "") -> list[dict[str, Any]]:
    """Flatten source-data records for an auxiliary CSV without changing JSON values."""
    rows: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            new_prefix = f"{prefix}.{key}" if prefix else str(key)
            rows.extend(_flatten_rows(item, new_prefix))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            new_prefix = f"{prefix}[{index}]"
            rows.extend(_flatten_rows(item, new_prefix))
    else:
        rows.append({"field": prefix, "value": value})
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    if not fields:
        fields = ["field", "value"]
        rows = [{"field": "none", "value": ""}]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_bundle(
    key: str,
    fig,
    source_data: dict[str, Any],
    evidence: list[dict[str, str]],
    *,
    source_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    meta = FIGURES[key]
    output_dir = SUITE / meta["directory"]
    output_dir.mkdir(parents=True, exist_ok=True)
    base = output_dir / meta["basename"]
    outputs = save_figure(fig, base)
    output_rel = ";".join(str(Path(v).relative_to(ROOT)) for v in outputs.values())
    for row in evidence:
        row["output_file"] = output_rel

    payload = {
        "figure": key,
        "title": meta["title"],
        "frozen_evidence_only": True,
        "new_scientific_computation": False,
        "display_data": _jsonable(source_data),
    }
    (output_dir / "source_data.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    rows = source_rows if source_rows is not None else _flatten_rows(payload["display_data"])
    _write_csv(output_dir / "source_data.csv", _jsonable(rows))

    (output_dir / "caption.md").write_text(
        f"# {meta['title']}\n\n{CAPTIONS[key]}\n", encoding="utf-8"
    )
    (output_dir / "panel_spec.md").write_text(
        f"# Panel specification — {meta['basename']}\n\n"
        + "\n".join(f"- {item}" for item in PANEL_SPECS[key])
        + "\n\nAll panels use frozen evidence or explanatory vector geometry. Stage IDs, where "
        "shown, are provenance tags and not the organizing scientific hierarchy.\n",
        encoding="utf-8",
    )
    (output_dir / "evidence_map.json").write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    _write_csv(output_dir / "evidence_map.csv", evidence)

    wrapper = output_dir / f"{meta['basename']}_plot.py"
    wrapper.write_text(
        "#!/usr/bin/env python3\n"
        "from pathlib import Path\nimport subprocess\nimport sys\n\n"
        "builder = Path(__file__).resolve().parents[1] / '00_style' / 'build_main_figures.py'\n"
        f"subprocess.run([sys.executable, str(builder), '--figure', '{key}'], check=True)\n",
        encoding="utf-8",
    )
    return {"key": key, "directory": str(output_dir), "outputs": outputs, "evidence": evidence}


def _title(fig, text: str) -> None:
    engine = fig.get_layout_engine()
    if engine is not None and hasattr(engine, "set"):
        engine.set(rect=(0.0, 0.0, 1.0, 0.955), h_pad=0.035, w_pad=0.025)
    fig.suptitle(text, x=0.01, y=0.992, ha="left", va="top", fontsize=10.5, fontweight="bold")


def _card_text(ax, title: str, body: str, status: str = "DIAGNOSTIC") -> None:
    hide_axis(ax)
    status_card(ax, (0.04, 0.14), 0.92, 0.72, title, status, subtitle=body, transform=ax.transAxes)


def _annotate_panel(ax, label: str, title: str) -> None:
    panel_label(ax, label)
    ax.set_title(title, loc="left", pad=5)


def _draw_flow(ax, labels: list[str], statuses: list[str], *, y: float = 0.5) -> None:
    hide_axis(ax)
    n = len(labels)
    gap = 0.018
    width = (0.94 - gap * (n - 1)) / n
    for i, (label, status) in enumerate(zip(labels, statuses)):
        x = 0.03 + i * (width + gap)
        status_card(ax, (x, y - 0.16), width, 0.32, label, status, transform=ax.transAxes, fontsize=6.4)
        if i < n - 1:
            arrow(ax, (x + width, y), (x + width + gap * 0.85, y), transform=ax.transAxes)


def _heatmap(ax, matrix: np.ndarray, xlabels: list[str], ylabels: list[str], *, vmin=None, vmax=None, cmap="viridis"):
    matrix = np.asarray(matrix)
    x_edges = np.arange(matrix.shape[1] + 1)
    y_edges = np.arange(matrix.shape[0] + 1)
    mesh = ax.pcolormesh(x_edges, y_edges, matrix, cmap=cmap, vmin=vmin, vmax=vmax, shading="flat", rasterized=False)
    ax.set_xlim(0, matrix.shape[1])
    ax.set_ylim(matrix.shape[0], 0)
    ax.set_xticks(np.arange(len(xlabels)) + 0.5, xlabels, rotation=45, ha="right")
    ax.set_yticks(np.arange(len(ylabels)) + 0.5, ylabels)
    return mesh


def _vector_colorbar(fig, mappable, *, ax, **kwargs):
    colorbar = fig.colorbar(mappable, ax=ax, **kwargs)
    if getattr(colorbar, "solids", None) is not None:
        colorbar.solids.set_rasterized(False)
    return colorbar


def _log_positive(values: Iterable[float], floor: float = 1e-18) -> np.ndarray:
    return np.maximum(np.asarray(list(values), dtype=float), floor)


def build_graphical_abstract() -> dict[str, Any]:
    src = "stage_08Z_Project_Closure_Publication/02_cross_stage_evidence/cross_stage_evidence_matrix.json"
    status_src = "stage_08Z_Project_Closure_Publication/03_claim_matrix/final_claim_support_matrix.json"
    cross = load_json(src)
    claims = load_json(status_src)
    fig = new_figure(92)
    ax = fig.add_subplot(111)
    hide_axis(ax)
    _title(fig, FIGURES["graphical_abstract"]["title"])

    labels = [
        "SPH\nfoundation", "reciprocal\ninteraction", "dynamic\nRK2", "defect\ntarget",
        "optimizer\npath", "formal\ncampaigns", "support\ndiagnosis", "systematic\ncoverage", "route\nclosure",
    ]
    statuses = [
        "VERIFIED", "QUALIFIED", "VERIFIED", "QUALIFIED", "QUALIFIED",
        "NOT QUALIFIED", "DIAGNOSTIC", "NOT QUALIFIED", "NOT QUALIFIED",
    ]
    _draw_flow(ax, labels, statuses, y=0.58)
    ax.text(0.03, 0.18, "VERIFIED / QUALIFIED", color=COLORS["teal"], fontweight="bold", transform=ax.transAxes)
    ax.text(0.37, 0.18, "≠ trained solver", color=COLORS["vermillion"], fontweight="bold", transform=ax.transAxes)
    ax.text(0.66, 0.18, "PROJECT_FULL_SOLVER_ROUTE_CLOSED", color=COLORS["vermillion"], fontweight="bold", transform=ax.transAxes)
    ax.text(0.98, 0.03, "frozen public evidence • no solver/model execution", ha="right", color=COLORS["gray"], fontsize=6.5, transform=ax.transAxes)
    evidence = [
        ev("Graphical abstract", "route", "Cross-stage qualification route is frozen.", src, "stage rows/status and authorization edges", "CONFIRMATORY", "Selected frozen stage nodes; deterministic horizontal layout."),
        ev("Graphical abstract", "route", "Qualified lower layers do not establish a trained solver.", status_src, "allowed_claims/prohibited_claims", "NEGATIVE_CONFIRMATORY", "Claims grouped by frozen qualification status."),
    ]
    return write_bundle(
        "graphical_abstract", fig,
        {"route_labels": labels, "route_status": statuses, "source_key_count": len(cross) if isinstance(cross, dict) else None, "claim_keys": list(claims) if isinstance(claims, dict) else []},
        evidence,
        source_rows=[{"node": a, "status": b} for a, b in zip(labels, statuses)],
    )


def build_fig01() -> dict[str, Any]:
    progression_src = "stage_08Z_Project_Closure_Publication/06_figures_and_tables/Figure_01/data.json"
    failure_src = "stage_08Z_Project_Closure_Publication/04_failure_taxonomy/final_failure_taxonomy.json"
    claim_src = "stage_08Z_Project_Closure_Publication/03_claim_matrix/final_claim_support_matrix.json"
    ledger_src = "stage_08Z_Project_Closure_Publication/01_project_status/project_final_status_ledger.md"
    progression = load_json(progression_src)["frozen_data"]["progression"]
    failures = load_json(failure_src)
    claims = load_json(claim_src)
    source_hash(ledger_src)

    fig = new_figure(205)
    gs = fig.add_gridspec(3, 2, height_ratios=[0.9, 1.35, 1.2])
    axa, axb, axc, axd, axe = (
        fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[1, :]),
        fig.add_subplot(gs[2, 0]), fig.add_subplot(gs[2, 1]),
    )
    _title(fig, FIGURES["fig01"]["title"])

    _annotate_panel(axa, "a", "Scientific objective")
    _card_text(axa, "Can a dynamic conservative correction be qualified?", "architecture → target → optimizer → training", "DIAGNOSTIC")
    axa.text(0.5, 0.06, "Lower-layer qualification does not imply a trained solver", ha="center", color=COLORS["vermillion"], fontsize=7, transform=axa.transAxes)

    _annotate_panel(axb, "b", "Reference roles V0–V3")
    hide_axis(axb)
    levels = [("V0", "analytic / exact", "VERIFIED"), ("V1", "operator checks", "QUALIFIED"), ("V2", "finite resolution", "NOT QUALIFIED"), ("V3", "dynamic role boundary", "DIAGNOSTIC")]
    for i, (lab, sub, stat) in enumerate(levels):
        y = 0.78 - 0.2 * i
        status_card(axb, (0.12, y), 0.76, 0.14, lab, stat, subtitle=sub, transform=axb.transAxes, fontsize=7)
        if i < 3:
            arrow(axb, (0.5, y), (0.5, y - 0.045), transform=axb.transAxes)

    _annotate_panel(axc, "c", "Authorization ladder")
    ladder = ["structure", "target", "gradient", "optimizer", "TRAIN", "validation", "support", "governance"]
    status = ["QUALIFIED", "QUALIFIED", "NOT QUALIFIED", "QUALIFIED", "NOT QUALIFIED", "NOT QUALIFIED", "NOT QUALIFIED", "QUALIFIED"]
    _draw_flow(axc, ladder, status, y=0.52)
    axc.text(0.03, 0.11, "Each gate has its own claim scope", color=COLORS["gray"], transform=axc.transAxes)

    _annotate_panel(axd, "d", "Failure → bounded response")
    hide_axis(axd)
    failure_rows = failures.get("failures", failures if isinstance(failures, list) else [])
    for i in range(9):
        col, row = i % 3, i // 3
        x, y = 0.04 + col * 0.32, 0.74 - row * 0.29
        item = failure_rows[i] if i < len(failure_rows) and isinstance(failure_rows[i], dict) else {}
        label = item.get("id", f"F{i+1}")
        status_card(axd, (x, y), 0.25, 0.18, label, "NOT QUALIFIED", subtitle="evidence → response", transform=axd.transAxes, fontsize=6.8)
        if col < 2:
            arrow(axd, (x + 0.25, y + 0.09), (x + 0.31, y + 0.09), transform=axd.transAxes)

    _annotate_panel(axe, "e", "Frozen final boundary")
    hide_axis(axe)
    final_items = [
        ("dynamic architecture", "QUALIFIED"), ("zero correction", "VERIFIED"),
        ("defect target", "QUALIFIED"), ("actual updates", "QUALIFIED"),
        ("trained solver", "NOT QUALIFIED"), ("autonomous rollout", "NOT QUALIFIED"),
        ("sealed test", "NOT ACCESSED"),
    ]
    for i, (label, stat) in enumerate(final_items):
        x = 0.04 + (i % 2) * 0.48
        y = 0.82 - (i // 2) * 0.22
        status_card(axe, (x, y), 0.42, 0.15, label, stat, transform=axe.transAxes, fontsize=6.8)
    provenance_tag(axe, "Stage08Z frozen closure ledger")

    evidence = [
        ev("Figure 1", "a,c", "The workflow is qualification-first and evidence-layered.", progression_src, "frozen_data.progression", "CONFIRMATORY", "Scientific layers grouped from frozen progression; stage IDs suppressed from hierarchy."),
        ev("Figure 1", "b,e", "V2 and the trained-solver route remain not qualified.", ledger_src, "reference hierarchy and final flags", "NEGATIVE_CONFIRMATORY", "Verbatim status categories rendered as cards."),
        ev("Figure 1", "d", "Nine documented failures motivated bounded methodological responses.", failure_src, "failures F1--F9", "CONFIRMATORY", "Frozen sequence shown in row-major layout; no causal magnitude implied."),
        ev("Figure 1", "e", "Allowed and prohibited claims are separated.", claim_src, "allowed_claims/prohibited_claims", "NEGATIVE_CONFIRMATORY", "Claims grouped by final qualification boundary."),
    ]
    return write_bundle("fig01", fig, {"progression": progression, "ladder": list(zip(ladder, status)), "final_items": final_items, "claim_matrix_keys": list(claims) if isinstance(claims, dict) else []}, evidence)


def build_fig02() -> dict[str, Any]:
    arch_src = "stage_02_Particle_Interaction_Operator/06_model/pair_force_pio_architecture_v0_1/results/stage02k_qualification_summary.json"
    pair_contract = "stage_03_Dynamic_SPH_Transformer_Hybrid/02_temporal_architecture/reciprocal_pair_head_contract.md"
    transformer_contract = "stage_03_Dynamic_SPH_Transformer_Hybrid/02_temporal_architecture/temporal_transformer_contract.md"
    baseline_contract = "stage_03_Dynamic_SPH_Transformer_Hybrid/02_temporal_architecture/baseline_arm_contract.md"
    rk2_contract = "stage_03_Dynamic_SPH_Transformer_Hybrid/03_time_integration/rk2_stage_semantics.md"
    history_contract = "stage_03_Dynamic_SPH_Transformer_Hybrid/03_time_integration/history_commit_contract.md"
    zero_contract = "stage_03_Dynamic_SPH_Transformer_Hybrid/02_temporal_architecture/zero_fallback_contract.md"
    arch = load_json(arch_src)
    for p in [pair_contract, transformer_contract, baseline_contract, rk2_contract, history_contract, zero_contract]:
        source_hash(p)

    fig = new_figure(224)
    axes = fig.subplots(3, 3)
    _title(fig, FIGURES["fig02"]["title"])
    titles = ["Neighbor graph", "One unordered edge", "Pair basis", "Coefficient head", "Reciprocity", "Comparison arms", "Midpoint RK2", "Accepted history", "D0 identity"]
    for ax, label, title in zip(axes.flat, list("abcdefghi"), titles):
        _annotate_panel(ax, label, title)
        hide_axis(ax)

    ax = axes[0, 0]
    pts = np.array([[.18,.25],[.33,.73],[.50,.45],[.72,.72],[.82,.28],[.55,.17]])
    edges = [(0,2),(1,2),(2,3),(2,4),(2,5),(3,4)]
    for i,j in edges: ax.plot(pts[[i,j],0], pts[[i,j],1], color=COLORS["gray_mid"], lw=1)
    ax.scatter(pts[:,0], pts[:,1], s=65, c=COLORS["blue_light"], edgecolor=COLORS["blue"])
    ax.scatter([pts[2,0]],[pts[2,1]],s=90,c=COLORS["teal"],edgecolor="white")
    ax.text(.50,.54,"i",ha="center",fontweight="bold")

    ax = axes[0, 1]
    ax.scatter([.23,.77],[.5,.5],s=100,c=[COLORS["blue"],COLORS["orange"]],edgecolor="white")
    ax.plot([.27,.73],[.5,.5],color=COLORS["ink"],lw=1.4)
    arrow(ax,(.47,.58),(.29,.58),transform=ax.transAxes,color=COLORS["teal"])
    arrow(ax,(.53,.42),(.71,.42),transform=ax.transAxes,color=COLORS["teal"])
    ax.text(.5,.73,"evaluate {i,j} once",ha="center",fontsize=7)

    ax = axes[0, 2]
    ax.arrow(.28,.32,.48,.34,width=.008,head_width=.05,color=COLORS["blue"],length_includes_head=True)
    ax.arrow(.28,.32,-.20,.28,width=.008,head_width=.05,color=COLORS["orange"],length_includes_head=True)
    ax.text(.68,.70,r"$\hat{r}_{ij}$",color=COLORS["blue"])
    ax.text(.06,.66,r"$\hat{t}_{ij}$",color=COLORS["orange"])
    ax.text(.28,.22,"radial + transverse",ha="center",fontsize=7)

    ax = axes[1, 0]
    boxes = [("symmetric\npair features",.06),("causal\nencoding",.38),(r"$\alpha,\beta$",.70)]
    for text,x in boxes:
        status_card(ax,(x,.35),.24,.3,text,"DIAGNOSTIC",transform=ax.transAxes,fontsize=6.5)
    arrow(ax,(.30,.5),(.37,.5),transform=ax.transAxes); arrow(ax,(.62,.5),(.69,.5),transform=ax.transAxes)

    ax = axes[1, 1]
    ax.text(.5,.67,r"$\mathbf{f}_{ij}^{\theta}=\alpha\hat{r}_{ij}+\beta\hat{t}_{ij}$",ha="center",fontsize=8)
    ax.text(.5,.42,r"$\mathbf{f}_{ji}^{\theta}=-\mathbf{f}_{ij}^{\theta}$",ha="center",fontsize=8,fontweight="bold",color=COLORS["teal"])
    ax.text(.5,.18,"momentum-compatible by construction",ha="center",fontsize=6.6,color=COLORS["gray"])

    ax = axes[1, 2]
    for i,(arm,body) in enumerate([("D1","pair\nMLP"),("D2","causal\ntoken"),("D3","temporal\nTransformer")]):
        x=.03+i*.325
        patch=FancyBboxPatch((x,.27),.29,.45,boxstyle="round,pad=.015",fc="white",ec=ARM_STYLE[arm]["color"],ls=ARM_STYLE[arm]["linestyle"],lw=1.2)
        ax.add_patch(patch); ax.text(x+.145,.55,arm,ha="center",fontweight="bold",color=ARM_STYLE[arm]["color"]); ax.text(x+.145,.39,body,ha="center",fontsize=6.4)
    ax.text(.5,.12,"arms ≠ ranking",ha="center",color=COLORS["vermillion"],fontweight="bold",fontsize=6.7)

    ax = axes[2, 0]
    labels=[r"$y_n$",r"$k_1$",r"$y_{1/2}$",r"$G_{1/2}$",r"$k_2$",r"$y_{n+1}$"]
    xs=np.linspace(.06,.94,len(labels))
    for i,(x,l) in enumerate(zip(xs,labels)):
        circ=Circle((x,.48),.055,fc=COLORS["blue_light"] if i not in (3,) else COLORS["orange_light"],ec=COLORS["blue"] if i not in (3,) else COLORS["orange"])
        ax.add_patch(circ); ax.text(x,.48,l,ha="center",va="center",fontsize=6.4)
        if i<len(labels)-1:arrow(ax,(x+.06,.48),(xs[i+1]-.06,.48),transform=ax.transAxes)
    ax.text(.5,.18,"graph rebuilt at source evaluations",ha="center",fontsize=6.5,color=COLORS["gray"])

    ax = axes[2, 1]
    xs=np.linspace(.12,.88,5)
    for i,x in enumerate(xs):
        stat="QUALIFIED" if i in (0,2,4) else "DIAGNOSTIC"
        status_card(ax,(x-.07,.38),.14,.25,"accept" if i in (0,2,4) else "mid",stat,transform=ax.transAxes,fontsize=6.0)
        if i<len(xs)-1:arrow(ax,(x+.07,.5),(xs[i+1]-.07,.5),transform=ax.transAxes)
    ax.text(.5,.16,"history commit only after acceptance",ha="center",fontsize=6.6,fontweight="bold")

    ax = axes[2, 2]
    ax.text(.5,.68,r"$\Delta\mathbf{f}_{ij}^{D0}\equiv 0$",ha="center",fontsize=11,fontweight="bold")
    ax.text(.5,.47,r"$\mathcal{T}_{D0}=\mathcal{T}_{\mathrm{SPH}}$",ha="center",fontsize=9,color=COLORS["teal"])
    status_card(ax,(.20,.16),.60,.18,"exact implementation identity","VERIFIED",transform=ax.transAxes,fontsize=6.5)

    evidence = [
        ev("Figure 2", "a--e", "Reciprocal unordered pair evaluation is antisymmetric and conservation-compatible.", pair_contract, "reciprocal pair construction", "CONFIRMATORY", "Explanatory vector schematic; no numerical values introduced."),
        ev("Figure 2", "d", "Causal temporal encoding is distinct from an SPH kernel interpretation.", transformer_contract, "token/head semantics", "CONFIRMATORY", "Contract blocks arranged left-to-right."),
        ev("Figure 2", "f", "D1/D2/D3 are comparison arms and do not encode superiority.", baseline_contract, "D1/D2/D3 arm definitions", "CONFIRMATORY", "Equal-size arm cards with non-ordinal styling."),
        ev("Figure 2", "g", "Midpoint RK2 rebuilds graph/source state at registered stages.", rk2_contract, "RK2 stage semantics", "CONFIRMATORY", "Stage sequence shown schematically."),
        ev("Figure 2", "h", "Only accepted states commit to causal history.", history_contract, "accepted-only history semantics", "CONFIRMATORY", "Accepted and midpoint states visually differentiated."),
        ev("Figure 2", "i", "D0 is the exact zero-correction identity.", zero_contract, "D0 identity", "CONFIRMATORY", "Formula typeset verbatim as explanatory identity."),
        ev("Figure 2", "all", "The pair-force architecture passed its frozen structural qualification.", arch_src, "status and architecture gates", "CONFIRMATORY", "Status used as boundary; no training claim."),
    ]
    return write_bundle("fig02", fig, {"architecture_status": arch.get("status"), "arm_roles": ["D1", "D2", "D3"], "schematic_only_panels": list("abcdefghi")}, evidence)


def build_fig03() -> dict[str, Any]:
    mms_src = "06_experiments/stage_01f5b_requalification_execution/results/spatial_analysis.json"
    mms_eval_src = "06_experiments/stage_01f5b_requalification_execution/results/stage01f5b_evaluation.json"
    v2_src = "06_experiments/stage_01g_validation_execution/results/stage01g_evaluation_reapplication_01.json"
    zero_src = "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c/results/zero_correction_results.json"
    rk2_src = "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c/results/independent_rk2_results.json"
    d0_diag_src = "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c/results/d0_reference_diagnostics.json"
    topo_src = "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03d/topology_event_scan/te1_dense_scan_results.json"
    cons_src = "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03d/conservation_over_time/conservation_results.json"
    ledger_src = "stage_08Z_Project_Closure_Publication/01_project_status/project_final_status_ledger.md"

    mms = load_json(mms_src)
    mms_eval = load_json(mms_eval_src)
    v2 = load_json(v2_src)
    zero = load_json(zero_src)
    rk2 = load_json(rk2_src)
    d0_diag = load_json(d0_diag_src)
    topo = load_json(topo_src)
    cons = load_json(cons_src)
    source_hash(ledger_src)

    fig = new_figure(236)
    gs = fig.add_gridspec(3, 3, height_ratios=[1.0, 1.05, 1.0])
    axes = [fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[0, 2]),
            fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1:]),
            fig.add_subplot(gs[2, 0:2]), fig.add_subplot(gs[2, 2])]
    _title(fig, FIGURES["fig03"]["title"])
    titles = ["Reference hierarchy", "MMS consistency path", "Zero correction", "Independent D0 RK2", "Topology birth/death", "Conservation over time", "Verification boundary"]
    for ax, label, title in zip(axes, list("abcdefg"), titles):
        _annotate_panel(ax, label, title)

    ax = axes[0]; hide_axis(ax)
    refs = [("analytic closure", "VERIFIED"), ("exact trajectory", "QUALIFIED"), ("DOP853 tolerance audit", "QUALIFIED"), ("finite-resolution V2", "NOT QUALIFIED")]
    for i, (lab, stat) in enumerate(refs):
        y = .78 - i * .20
        status_card(ax, (.08, y), .84, .14, lab, stat, transform=ax.transAxes, fontsize=6.7)
        if i < len(refs)-1: arrow(ax, (.50, y), (.50, y-.04), transform=ax.transAxes)

    ax = axes[1]
    ns = np.asarray([row["N"] for row in mms["cases"]["MMS_A"]["rows"]], dtype=float)
    for case, color, marker in [("MMS_A", COLORS["blue"], "o"), ("MMS_B", COLORS["orange"], "s")]:
        rows = mms["cases"][case]["rows"]
        for field, ls in [("velocity", "-"), ("position", "--")]:
            vals = [row["errors"][field] for row in rows]
            ax.plot(ns, vals, color=color, marker=marker, linestyle=ls, label=f"{case} {field}")
    ax.set_yscale("log"); ax.set_xlabel("particles per axis, N"); ax.set_ylabel("registered error")
    ax.legend(fontsize=5.7, ncol=2); style_axis(ax, grid=True)
    ax.text(.02,.03,"consistency path only • GCI not qualified",transform=ax.transAxes,fontsize=6.2,color=COLORS["vermillion"])

    ax = axes[2]
    bars = ax.bar([0, 1], [zero["passed"], zero["required"]], color=[COLORS["teal"], COLORS["gray_light"]], edgecolor=COLORS["ink"], width=.58)
    ax.set_xticks([0,1],["passed","required"]); ax.set_ylim(0, zero["required"]*1.14); style_axis(ax, grid=True)
    ax.text(.5,.88,f"{zero['passed']}/{zero['required']}\nbitwise",ha="center",transform=ax.transAxes,fontweight="bold",color=COLORS["teal"])
    ax.set_ylabel("registered cases")

    ax = axes[3]
    d0_vals = [row["D0_vs_D_R2_DOP853"]["maximum_normalized_l2"] for row in d0_diag["rows"] if "D0_vs_D_R2_DOP853" in row]
    ax.scatter(np.arange(len(d0_vals)), _log_positive(d0_vals), s=10, c=COLORS["blue"], alpha=.75, label="D0 vs D-R2/DOP853")
    ax.set_yscale("log"); ax.set_xlabel("registered diagnostic row"); ax.set_ylabel("maximum normalized $L_2$")
    style_axis(ax, grid=True); ax.legend(fontsize=5.8)
    ax.text(.98,.04,f"implementation checks {rk2['passed']}/{rk2['required']} PASS\nnot a V2 recovery claim",ha="right",transform=ax.transAxes,fontsize=6.0,color=COLORS["vermillion"])

    ax = axes[4]
    rows = topo["rows"]
    s = np.asarray([row["s"] for row in rows])
    margin = np.asarray([row["cutoff_margin"] for row in rows])
    active = np.asarray([row["active_unordered_pair_count"] for row in rows])
    ax.plot(s, margin, color=COLORS["blue"], label="cutoff margin")
    ax.axhline(0, color=COLORS["vermillion"], ls="--", lw=.9)
    ax.set_xlabel("registered scan coordinate, s"); ax.set_ylabel("cutoff margin")
    ax2 = ax.twinx(); ax2.step(s, active, where="mid", color=COLORS["orange"], lw=.9, alpha=.8); ax2.set_ylabel("active unordered pairs", color=COLORS["orange"])
    style_axis(ax, grid=True); ax.text(.02,.04,"dense scan; topology component only",transform=ax.transAxes,fontsize=6.2,color=COLORS["gray"])

    ax = axes[5]
    cons_rows=[]
    for row in cons["rows"]:
        for stage in row["audit"]["conservation"]:
            cons_rows.append((row["arm"], stage["baseline_force_residual"], stage["correction_force_residual"], stage["total_force_residual"]))
    for j,(field,label,color,marker) in enumerate([(1,"baseline",COLORS["gray"],"o"),(2,"correction",COLORS["teal"],"s"),(3,"total",COLORS["purple"],"^")]):
        vals=[r[field] for r in cons_rows]
        ax.scatter(np.arange(len(vals)), _log_positive(vals), s=7, alpha=.55, color=color, marker=marker, label=label)
    ax.set_yscale("log"); ax.set_xlabel("registered RK2 stage record"); ax.set_ylabel("force residual")
    style_axis(ax, grid=True); ax.legend(ncol=3, fontsize=6)
    ax.text(.99,.04,f"{cons['per_stage_pass_count']}/{cons['per_stage_count']} PASS",ha="right",transform=ax.transAxes,fontweight="bold",color=COLORS["teal"])

    ax = axes[6]; hide_axis(ax)
    boundary=[("dynamic implementation","VERIFIED"),("topology/conservation scope","QUALIFIED"),("finite-resolution V2","NOT QUALIFIED"),("complete Stage03 route","NOT QUALIFIED")]
    for i,(lab,stat) in enumerate(boundary):
        status_card(ax,(.08,.76-i*.21),.84,.15,lab,stat,transform=ax.transAxes,fontsize=6.3)

    evidence = [
        ev("Figure 3", "a,g", "Reference roles retain the failed finite-resolution V2 boundary.", v2_src, "unique_status/acoustic_gates/shear_gates/next_stage_qualified", "NEGATIVE_CONFIRMATORY", "Frozen status rendered as role cards."),
        ev("Figure 3", "b", "Registered MMS errors decrease along the plateau-aware consistency path.", mms_src, "cases.*.rows[].N/errors", "CONFIRMATORY", "Raw frozen errors plotted on log axis; no new fit."),
        ev("Figure 3", "b", "No GCI claim is supported.", mms_eval_src, "gci and unique_status", "NEGATIVE_CONFIRMATORY", "Boundary annotation only."),
        ev("Figure 3", "c", "Zero correction passed all 288 registered bitwise cases.", zero_src, "passed/required/rows[].gates", "CONFIRMATORY", "Direct counts."),
        ev("Figure 3", "d", "Independent D0 RK2 implementation passed 48/48 checks.", rk2_src, "passed/required/rows[].metrics", "CONFIRMATORY", "Direct counts in annotation."),
        ev("Figure 3", "d", "D0-reference differences are diagnostic and do not recover V2.", d0_diag_src, "rows[].D0_vs_D_R2_DOP853.maximum_normalized_l2/performance_gate", "DIAGNOSTIC_ONLY", "Raw diagnostics plotted in registered row order."),
        ev("Figure 3", "e", "Dense topology scan records birth/death transitions.", topo_src, "rows[].s/cutoff_margin/active_unordered_pair_count", "CONFIRMATORY", "Raw scan order; zero-margin reference line."),
        ev("Figure 3", "f", "All registered structural conservation stages passed.", cons_src, "rows[].audit.conservation/per_stage_count/per_stage_pass_count", "CONFIRMATORY", "Raw positive residuals displayed on log axis."),
        ev("Figure 3", "g", "The complete route remained not qualified despite implementation verification.", ledger_src, "Stage03 and final flags", "NEGATIVE_CONFIRMATORY", "Frozen statuses grouped by claim layer."),
    ]
    data = {"reference_roles": refs, "mms": {k: mms["cases"][k]["rows"] for k in ["MMS_A","MMS_B"]}, "zero_counts": {k:zero[k] for k in ["passed","required","pass"]}, "rk2_counts": {k:rk2[k] for k in ["passed","required","pass"]}, "d0_diagnostic_max_l2": d0_vals, "topology": {"s":s,"cutoff_margin":margin,"active_pairs":active}, "conservation_rows": cons_rows, "boundary": boundary, "v2_status": v2.get("unique_status"), "gci": mms_eval.get("gci")}
    return write_bundle("fig03", fig, data, evidence)


def _static_histories() -> tuple[list[dict[str, Any]], list[str]]:
    rows=[]; sources=[]
    for version, seeds in [("v0_1", [20261201,20261202,20261203]), ("v0_2", [20261211,20261212,20261213])]:
        for arm in ["K0","K1","K2"]:
            for seed in seeds:
                rel=f"stage_02_Particle_Interaction_Operator/06_model/pair_force_pio_static_fitting_{version}/runs/{arm}/seed_{seed}/training_history.json"
                data=load_json(rel); sources.append(rel)
                for row in data["rows"]:
                    rows.append({"version":version,"arm":arm,"seed":seed,"update":row["update"],"loss":row["graph_balanced_loss"]})
    return rows, sources


def build_fig04() -> dict[str, Any]:
    gate1_src = "stage_02_Particle_Interaction_Operator/06_model/pair_force_pio_static_fitting_v0_1/results/frozen_success_gate_evaluation.json"
    gate2_src = "stage_02_Particle_Interaction_Operator/06_model/pair_force_pio_static_fitting_v0_2/results/stage02mq_frozen_success_gate_evaluation.json"
    dir_src = "stage_04_Local_Causal_Dynamic_Training/05_task_aligned_gradient/stage04cr/directional_projection/directional_projection_and_factors.json"
    residual_src = "stage_04_Local_Causal_Dynamic_Training/05_task_aligned_gradient/stage04cr/state_residual/state_residual_and_D0_comparison.json"
    rk2_src = "stage_04_Local_Causal_Dynamic_Training/05_task_aligned_gradient/stage04cr/rk2_attenuation/rk2_attenuation.json"
    summary_src = "stage_04_Local_Causal_Dynamic_Training/05_task_aligned_gradient/stage04cr/qualification/stage04cr_summary.json"
    defect_src = "stage_05_Scale_Aware_Discrete_Defect_Training/01_defect_target_qualification/stage05b/qualification/stage05b_qualification_summary.json"
    histories, history_sources = _static_histories()
    gates=[load_json(gate1_src),load_json(gate2_src)]
    dirs=load_json(dir_src); residuals=load_json(residual_src); attenuation=load_json(rk2_src); summary=load_json(summary_src); defect=load_json(defect_src)

    fig=new_figure(250)
    gs=fig.add_gridspec(3,3,height_ratios=[1.1,1,1])
    axes=[fig.add_subplot(gs[0,:2]),fig.add_subplot(gs[0,2]),fig.add_subplot(gs[1,:2]),fig.add_subplot(gs[1,2]),fig.add_subplot(gs[2,0]),fig.add_subplot(gs[2,1]),fig.add_subplot(gs[2,2])]
    _title(fig,FIGURES["fig04"]["title"])
    titles=["All static TRAIN runs","Frozen static gates","2,592 directional entries","State-residual magnitudes","Registered attributions","RK2 attenuation factors","Authorized transition"]
    for ax,label,title in zip(axes,list("abcdefg"),titles):_annotate_panel(ax,label,title)

    ax=axes[0]
    for (version,arm,seed), grp in _group_rows(histories,["version","arm","seed"]):
        style={"K0":ARM_STYLE["D0"],"K1":ARM_STYLE["D1"],"K2":ARM_STYLE["D2"]}[arm]
        ax.plot([r["update"] for r in grp],_log_positive([r["loss"] for r in grp]),color=style["color"],ls="-" if version=="v0_1" else "--",alpha=.66,lw=.85)
    ax.set_yscale("log");ax.set_xlabel("optimizer update");ax.set_ylabel("graph-balanced TRAIN loss");style_axis(ax,grid=True)
    handles=[Line2D([0],[0],color=ARM_STYLE["D0"]["color"],label="K0"),Line2D([0],[0],color=ARM_STYLE["D1"]["color"],label="K1"),Line2D([0],[0],color=ARM_STYLE["D2"]["color"],label="K2"),Line2D([0],[0],color=COLORS["ink"],ls="-",label="v0.1"),Line2D([0],[0],color=COLORS["ink"],ls="--",label="v0.2")]
    ax.legend(handles=handles,ncol=5,fontsize=5.8)

    ax=axes[1]
    matrix=[]; ylabels=[]
    for vi,g in enumerate(gates):
        archs=g.get("architectures",{})
        for arm in ["K0","K1","K2"]:
            d=archs.get(arm,{})
            matrix.append([bool(d.get(k,False)) for k in ["A_numerical_stability","B_train_fit","C_validation_transfer","E_conservation"]]); ylabels.append(f"v0.{vi+1} {arm}")
    _heatmap(ax,np.asarray(matrix,dtype=int),["A safe","B TRAIN","C val","E cons"],ylabels,vmin=0,vmax=1,cmap="RdYlGn")
    ax.text(.98,.02,"red = gate not passed",ha="right",transform=ax.transAxes,fontsize=6,color=COLORS["vermillion"])

    components=["L_x","L_v","L_rho"]
    mat=np.asarray([[math.log10(max(abs(c["historical_reverse"]),1e-30)) for c in row["components"]] for row in dirs["rows"]])
    ax=axes[2]; image=_heatmap(ax,mat,components,[str(i) for i in range(mat.shape[0])],cmap="magma")
    ax.set_yticks([.5,215.5,431.5,647.5,863.5],["1","216","432","648","864"]);ax.set_ylabel("registered context");_vector_colorbar(fig,image,ax=ax,label=r"$\log_{10}|$directional derivative$|$",fraction=.025,pad=.02)

    ax=axes[3]
    for comp,color in [("x",COLORS["blue"]),("v",COLORS["teal"]),("rho",COLORS["orange"])]:
        vals=[r["D0_dimensionless_state_residual_RMS"][comp] for r in residuals["rows"]]
        ax.hist(_log_positive(vals),bins=20,histtype="step",lw=1.1,label=comp,color=color)
    ax.set_xscale("log");ax.set_xlabel("D0 dimensionless residual RMS");ax.set_ylabel("count");style_axis(ax,grid=True);ax.legend(fontsize=6)

    ax=axes[4]
    reasons=list(dirs["reason_counts"]);vals=[dirs["reason_counts"][k] for k in reasons]
    bars=ax.barh(np.arange(len(vals)),vals,color=[COLORS["orange"],COLORS["blue"],COLORS["gray_mid"]],edgecolor=COLORS["ink"])
    ax.set_yticks(np.arange(len(vals)),["projection\ndilution","residual\ntoo small","unresolved"]);ax.set_xlabel("directional components");style_axis(ax,grid=True)
    for bar,v in zip(bars,vals):ax.text(v,bar.get_y()+bar.get_height()/2,f" {v}",va="center",fontsize=6)

    ax=axes[5]
    vel=[r["V_over_dt_A_mid"] for r in attenuation["rows"]];pos=[r["X_over_dt2_A_mid"] for r in attenuation["rows"]]
    ax.scatter(np.arange(len(vel)),vel,s=6,color=COLORS["blue"],alpha=.45,label=r"$v/(\Delta t a_{mid})$")
    ax.scatter(np.arange(len(pos)),pos,s=6,color=COLORS["orange"],alpha=.45,label=r"$x/(\Delta t^2 a_{mid})$")
    ax.axhline(1,color=COLORS["blue"],ls="--",lw=.8);ax.axhline(.5,color=COLORS["orange"],ls="--",lw=.8)
    ax.set_xlabel("registered context");ax.set_ylabel("frozen ratio");style_axis(ax,grid=True);ax.legend(fontsize=5.8)

    ax=axes[6];hide_axis(ax)
    status_card(ax,(.10,.66),.80,.18,"raw next-state target","NOT QUALIFIED",subtitle=summary["final_status"],transform=ax.transAxes,fontsize=6.2)
    arrow(ax,(.5,.64),(.5,.48),transform=ax.transAxes,color=COLORS["orange"])
    status_card(ax,(.10,.24),.80,.20,"scale-aware discrete defect","QUALIFIED",subtitle=defect.get("status","Stage05B"),transform=ax.transAxes,fontsize=6.2)
    ax.text(.5,.08,"methodological response ≠ training success",ha="center",fontsize=6.2,color=COLORS["vermillion"])

    evidence=[
        ev("Figure 4","a","All 18 frozen static TRAIN histories are retained.",history_sources[0],"rows[].update/graph_balanced_loss (plus 17 listed in source_data)","NEGATIVE_CONFIRMATORY","All histories plotted; source_data records every source hash."),
        ev("Figure 4","b","Registered static learning gates did not establish the route.",gate1_src,"architectures.* A/B/C/E","NEGATIVE_CONFIRMATORY","Boolean gate matrix; sealed-test gate D intentionally excluded."),
        ev("Figure 4","b","The second static campaign remained below its seed gate.",gate2_src,"architectures.* A/B/C/E","NEGATIVE_CONFIRMATORY","Boolean gate matrix; sealed-test gate D intentionally excluded."),
        ev("Figure 4","c,e","Complete task-aligned directional evidence is mixed or unresolved.",dir_src,"rows[].components and reason_counts","DIAGNOSTIC_ONLY","Historical derivatives log-scaled; 864 rows × three components; frozen counts."),
        ev("Figure 4","d","D0 next-state residual magnitudes are small in registered coordinates.",residual_src,"rows[].D0_dimensionless_state_residual_RMS","DIAGNOSTIC_ONLY","Deterministic fixed-bin histogram on log x-axis."),
        ev("Figure 4","f","RK2 maps acceleration into velocity as Δt and position as Δt²/2.",rk2_src,"rows[].V_over_dt_A_mid/X_over_dt2_A_mid","DIAGNOSTIC_ONLY","Raw registered ratios; theoretical guide lines at 1 and 0.5."),
        ev("Figure 4","g","Stage04 attribution was mixed or unresolved.",summary_src,"final_status/reason_counts","NEGATIVE_CONFIRMATORY","Status card."),
        ev("Figure 4","g","The scale-aware defect target subsequently qualified.",defect_src,"status/gates","CONFIRMATORY","Authorization transition only; no success inference."),
    ]
    for rel in history_sources[1:]:
        evidence.append(ev("Figure 4","a","Frozen static TRAIN history included without selection.",rel,"rows[].update/graph_balanced_loss","NEGATIVE_CONFIRMATORY","Raw history plotted in file row order."))
    data={"static_histories":histories,"static_gate_matrix":matrix,"static_gate_labels":ylabels,"directional_log_abs":mat,"reason_counts":dirs["reason_counts"],"D0_residuals":{c:[r["D0_dimensionless_state_residual_RMS"][c] for r in residuals["rows"]] for c in ["x","v","rho"]},"rk2_ratios":{"velocity":vel,"position":pos},"stage04_summary":summary,"stage05_status":defect.get("status")}
    return write_bundle("fig04",fig,data,evidence,source_rows=histories)


def _group_rows(rows: list[dict[str, Any]], keys: list[str]):
    groups: dict[tuple[Any,...],list[dict[str,Any]]]={}
    for row in rows: groups.setdefault(tuple(row[k] for k in keys),[]).append(row)
    return groups.items()


def build_fig05() -> dict[str, Any]:
    record_npz_src="stage_05_Scale_Aware_Discrete_Defect_Training/01_defect_target_qualification/stage05b/target_records/LCDF_01_VARIANT_LOW_N8_O00.npz"
    record_json_src="stage_05_Scale_Aware_Discrete_Defect_Training/01_defect_target_qualification/stage05b/target_records/LCDF_01_VARIANT_LOW_N8_O00.json"
    origins_src="stage_05_Scale_Aware_Discrete_Defect_Training/01_defect_target_qualification/stage05b/results/formal_origin_results.json"
    scale_src="stage_05_Scale_Aware_Discrete_Defect_Training/01_defect_target_qualification/stage05b/scale_calculation/stage05b_scale.json"
    compat_src="stage_05_Scale_Aware_Discrete_Defect_Training/01_defect_target_qualification/stage05b/conservative_decomposition/conservative_compatibility.json"
    unbounded_src="stage_05_Scale_Aware_Discrete_Defect_Training/01_defect_target_qualification/stage05b/pair_basis_representability/unbounded_representability.json"
    bounded_src="stage_05_Scale_Aware_Discrete_Defect_Training/01_defect_target_qualification/stage05b/bounded_head_feasibility/bounded_feasibility.json"
    shift_src="stage_07_Heterogeneous_Development_Pool/02_defect_scale_requalification/stage07b/distribution_shift/scale_distribution_shift.json"
    summary_src="stage_05_Scale_Aware_Discrete_Defect_Training/01_defect_target_qualification/stage05b/qualification/stage05b_qualification_summary.json"
    arrays=load_npz(record_npz_src); record=load_json(record_json_src); origins=load_json(origins_src)["rows"]
    scale=load_json(scale_src);compat=load_json(compat_src);unbounded=load_json(unbounded_src);bounded=load_json(bounded_src);shift=load_json(shift_src);summary=load_json(summary_src)

    fig=new_figure(252);axes=fig.subplots(3,3);_title(fig,FIGURES["fig05"]["title"])
    titles=["Same-origin transition","Velocity-defect geometry","Conservative decomposition","Signal / uncertainty","Incompatible fraction","Pair-basis residuals","Target-scale shift","Zero identity"]
    for ax,label,title in zip(axes.flat[:8],list("abcdefgh"),titles):_annotate_panel(ax,label,title)
    axes[2,2].set_title("Claim boundary",loc="left",pad=5)

    ax=axes[0,0];hide_axis(ax)
    status_card(ax,(.07,.58),.34,.23,r"reference $y_{n+1}$","QUALIFIED",transform=ax.transAxes,fontsize=6.5)
    status_card(ax,(.59,.58),.34,.23,r"D0 $y_{n+1}^{0}$","VERIFIED",transform=ax.transAxes,fontsize=6.5)
    arrow(ax,(.41,.69),(.58,.69),transform=ax.transAxes)
    ax.text(.5,.37,r"$\Delta v=v_{ref}-v_{D0}$",ha="center",fontsize=9,fontweight="bold")
    ax.text(.5,.17,"same origin / same accepted step\ngeometry schematic; no full D0 trajectory claimed",ha="center",fontsize=6.1,color=COLORS["gray"])

    ax=axes[0,1]
    dv=record["dt"]*arrays["a_def"][:,0]
    ax.plot(np.arange(len(dv)),dv,color=COLORS["blue"],marker="o",ms=2,label=r"$\Delta v_x=\Delta t\,a_{def,x}$")
    ax.axhline(0,color=COLORS["gray_mid"],lw=.7);ax.set_xlabel("flattened particle index");ax.set_ylabel(r"$\Delta v_x$");style_axis(ax,grid=True);ax.legend(fontsize=5.8)

    ax=axes[0,2]
    idx=np.arange(arrays["a_def"].shape[0])
    ax.plot(idx,arrays["a_def"][:,0],color=COLORS["ink"],label=r"$a_{def,x}$")
    ax.plot(idx,arrays["a_cons"][:,0],color=COLORS["teal"],ls="--",label=r"$a_{cons,x}$")
    ax.plot(idx,arrays["a_incompatible"][:,0],color=COLORS["vermillion"],ls=":",label=r"$a_{cm,x}$")
    ax.set_xlabel("flattened particle index");ax.set_ylabel("acceleration");style_axis(ax,grid=True);ax.legend(fontsize=5.5)

    ax=axes[1,0]
    vals=[scale["u_a"],scale["s_a"]]
    bars=ax.bar([0,1],vals,color=[COLORS["gray_mid"],COLORS["teal"]],edgecolor=COLORS["ink"])
    ax.set_yscale("log");ax.set_xticks([0,1],[r"$u_a$",r"$s_a$"]);ax.set_ylabel("acceleration scale");style_axis(ax,grid=True)
    ax.text(.5,.92,f"ratio = {scale['s_a_over_u_a']:.3e}",ha="center",transform=ax.transAxes,fontweight="bold",fontsize=6.5)

    ax=axes[1,1]
    frac=[r["incompatible_fraction"] for r in origins]
    ax.hist(_log_positive(frac,1e-35),bins=24,color=COLORS["orange_light"],edgecolor=COLORS["orange"],lw=.7)
    ax.set_xscale("log");ax.set_xlabel("incompatible fraction");ax.set_ylabel("origins");style_axis(ax,grid=True)
    ax.text(.98,.93,"384 frozen origins",ha="right",transform=ax.transAxes,fontsize=6.3)

    ax=axes[1,2]
    labels=["unbounded\nmean","unbounded\np95","bounded\nmean","bounded\np95"]
    values=[unbounded["family_balanced_mean"],unbounded["percentile95"],bounded["family_balanced_mean"],bounded["percentile95"]]
    ax.bar(np.arange(4),values,color=[COLORS["blue"],COLORS["blue_light"],COLORS["teal"],COLORS["teal_light"]],edgecolor=COLORS["ink"])
    ax.set_yscale("log");ax.set_xticks(np.arange(4),labels);ax.set_ylabel("normalized residual");style_axis(ax,grid=True)

    ax=axes[2,0]
    lineages=list(scale["lineage_scale"])
    x=np.arange(len(lineages));ax.bar(x,[scale["lineage_scale"][k] for k in lineages],color=COLORS["blue_light"],edgecolor=COLORS["blue"],label="v1 lineage")
    ax.axhline(shift["s_a_v1"],color=COLORS["blue"],ls="--",label=f"v1={shift['s_a_v1']:.3g}")
    ax.axhline(shift["s_a_v2"],color=COLORS["orange"],ls="-.",label=f"v2={shift['s_a_v2']:.3g}")
    ax.set_xticks(x,lineages,rotation=45,ha="right");ax.set_ylabel(r"$s_a$ / lineage RMS");style_axis(ax,grid=True);ax.legend(fontsize=5.4)

    ax=axes[2,1]
    vals=[scale["zero_baseline_loss"],scale["zero_baseline_absolute_error"],compat["compatibility"]["zero_force_max"]]
    ax.bar(np.arange(3),_log_positive(vals),color=[COLORS["gray"],COLORS["teal"],COLORS["teal_light"]],edgecolor=COLORS["ink"])
    ax.set_yscale("log");ax.set_xticks(np.arange(3),["zero loss","|loss−1|","zero-force\nresidual"]);ax.set_ylabel("registered value");style_axis(ax,grid=True)

    ax=axes[2,2];hide_axis(ax)
    status_card(ax,(.10,.58),.80,.22,"discrete-defect target","QUALIFIED",subtitle=f"{summary.get('formal_origin_count',384)} origins",transform=ax.transAxes,fontsize=6.5)
    status_card(ax,(.10,.22),.80,.20,"training / target truth","NOT QUALIFIED",subtitle="separate downstream claims",transform=ax.transAxes,fontsize=6.3)

    evidence=[
        ev("Figure 5","a,b","The velocity defect is defined at one frozen origin and accepted step.",record_json_src,"dt/source identities/reference and D0 hashes","CONFIRMATORY","Panel a is schematic; panel b multiplies frozen a_def by frozen dt as an explicitly declared deterministic display transform."),
        ev("Figure 5","b,c","The frozen defect decomposes into conservative and incompatible components.",record_npz_src,"a_def/a_cons/a_incompatible","CONFIRMATORY","Frozen arrays flattened in stored row-major order; Δv=dt·a_def."),
        ev("Figure 5","d,g,h","The registered target signal exceeds frozen uncertainty and preserves the zero identity.",scale_src,"s_a/u_a/s_a_over_u_a/lineage_scale/zero_baseline_*","CONFIRMATORY","Direct frozen scalars and lineage values; log axis."),
        ev("Figure 5","e","The incompatible fraction is recorded across all 384 origins.",origins_src,"rows[].incompatible_fraction","CONFIRMATORY","Deterministic fixed-bin histogram; no row exclusion."),
        ev("Figure 5","f","Both bounded and unbounded pair-basis representability gates passed.",unbounded_src,"family_balanced_mean/percentile95/pass","CONFIRMATORY","Direct frozen summary scalars."),
        ev("Figure 5","f","Bounded head feasibility passed at the registered bound.",bounded_src,"family_balanced_mean/percentile95/physical_head_bound/pass","CONFIRMATORY","Direct frozen summary scalars."),
        ev("Figure 5","h","The conservative decomposition retains the zero-force identity.",compat_src,"compatibility.zero_force_max/gates","CONFIRMATORY","Direct frozen scalar."),
        ev("Figure 5","g","The prospectively requalified v2 scale differs from v1.",shift_src,"s_a_v1/s_a_v2/lineage_RMS","DIAGNOSTIC_ONLY","v1 lineage values plus frozen global v1/v2 reference lines; no cross-stage performance inference."),
        ev("Figure 5","h","Target qualification is distinct from training and target-truth claims.",summary_src,"status/formal_origin_count/gates","NEGATIVE_CONFIRMATORY","Unlabelled scope card adjoining panel h."),
    ]
    data={"record":record,"a_def":arrays["a_def"],"a_cons":arrays["a_cons"],"a_incompatible":arrays["a_incompatible"],"delta_v":record["dt"]*arrays["a_def"],"scale":scale,"incompatible_fraction":frac,"compatibility":compat,"unbounded":unbounded,"bounded":bounded,"scale_shift":shift,"qualification":summary}
    return write_bundle("fig05",fig,data,evidence)


def build_fig06() -> dict[str, Any]:
    full_src="stage_05_Scale_Aware_Discrete_Defect_Training/02_optimizer_gradient_qualification/stage05c/full_gradient/full_gradient_evidence.json"
    reverse_src="stage_05_Scale_Aware_Discrete_Defect_Training/02_optimizer_gradient_qualification/stage05c/reverse_jvp/reverse_jvp_evidence.json"
    coord_src="stage_05_Scale_Aware_Discrete_Defect_Training/02_optimizer_gradient_qualification/stage05c/coordinate_fd/coordinate_and_block_fd_evidence.json"
    blind_src="stage_05_Scale_Aware_Discrete_Defect_Training/02_optimizer_gradient_qualification/stage05cq/coordinate_block_sampling/coordinate_block_evidence.json"
    path_src="stage_05_Scale_Aware_Discrete_Defect_Training/02_optimizer_gradient_qualification/stage05cq/optimizer_path_fd/optimizer_path_fd_evidence.json"
    descent_src="stage_05_Scale_Aware_Discrete_Defect_Training/02_optimizer_gradient_qualification/stage05c/local_descent/local_descent_evidence.json"
    summary_src="stage_06_Optimizer_Update_Dynamics_Training/01_update_map_qualification/qualification/stage06a_qualification_summary.json"
    full=load_json(full_src);reverse=load_json(reverse_src);coord=load_json(coord_src);blind=load_json(blind_src);path=load_json(path_src);descent=load_json(descent_src);summary=load_json(summary_src)
    globals_data=[];global_sources=[]
    for arm in ["D1","D2","D3"]:
        for seed in [20600601,20600602,20600603]:
            rel=f"stage_06_Optimizer_Update_Dynamics_Training/01_update_map_qualification/results/{arm.lower()}/{arm}_{seed}_GLOBAL.json"
            globals_data.append(load_json(rel));global_sources.append(rel)

    fig=new_figure(252);axes=fig.subplots(3,3);_title(fig,FIGURES["fig06"]["title"])
    titles=["Full-gradient activity","Reverse / JVP identity","Coordinate/block boundary","Optimizer-path FD","No-writeback descent","AdamW one step","2/4-step micro-trajectories","Qualification ladder"]
    for ax,label,title in zip(axes.flat[:8],list("abcdefgh"),titles):_annotate_panel(ax,label,title)
    axes[2,2].set_title("Claim scope",loc="left",pad=5)

    ax=axes[0,0]
    cats=["active","finite","group-seed\npass"]
    vals=[full["active_rows"],full["finite_rows"],full["group_lineage_seed_pass_count"]]
    req=[full["observed_rows"],full["observed_rows"],full["group_lineage_seed_count"]]
    ax.bar(np.arange(3),req,color=COLORS["gray_light"],edgecolor=COLORS["gray"],label="required")
    ax.bar(np.arange(3),vals,color=COLORS["teal"],edgecolor=COLORS["ink"],label="pass")
    ax.set_xticks(np.arange(3),cats);ax.set_ylabel("registered rows");style_axis(ax,grid=True);ax.legend(fontsize=5.7)

    ax=axes[0,1]
    ax.bar([0,1],[reverse["pass_count"],reverse["required_probe_count"]],color=[COLORS["teal"],COLORS["gray_light"]],edgecolor=COLORS["ink"])
    ax.set_xticks([0,1],["pass","required"]);ax.set_ylabel("reverse/JVP probes");style_axis(ax,grid=True)
    ax.text(.5,.88,f"{reverse['pass_count']}/{reverse['required_probe_count']}",ha="center",transform=ax.transAxes,fontweight="bold",color=COLORS["teal"])

    ax=axes[0,2]
    labels=["historical\nStage05C","prospective\nStage05CQ"]
    stable=[coord["stable_probe_count"],blind["pass_or_consistent_count"]];required=[coord["required_probe_count"],blind["required_probe_count"]]
    x=np.arange(2);ax.bar(x,required,color=COLORS["gray_light"],edgecolor=COLORS["gray"],label="required");ax.bar(x,stable,color=COLORS["orange"],edgecolor=COLORS["ink"],label="qualified/consistent")
    ax.set_xticks(x,labels);ax.set_ylabel("coordinate/block probes");style_axis(ax,grid=True);ax.legend(fontsize=5.5)
    ax.text(.5,.03,f"misses retained: {coord['failed_probe_count']} + {blind['failure_count']}",ha="center",transform=ax.transAxes,color=COLORS["vermillion"],fontsize=6.2)

    ax=axes[1,0]
    vals=[path["reverse_jvp_pass_rows"],path["fd_stable_rows"],path["path_pass_rows"]]
    ax.bar(np.arange(3),vals,color=[COLORS["blue"],COLORS["orange"],COLORS["teal"]],edgecolor=COLORS["ink"])
    ax.axhline(path["required_rows"],color=COLORS["ink"],ls="--",lw=.8);ax.set_xticks(np.arange(3),["reverse","FD stable","path pass"]);ax.set_ylabel("of 216 paths");style_axis(ax,grid=True)

    ax=axes[1,1]
    vals=[descent["lineage_window_count"],descent["global_window_count"],int(descent["all_radii_restored"])]
    ax.bar(np.arange(3),vals,color=[COLORS["blue"],COLORS["teal"],COLORS["gray"]],edgecolor=COLORS["ink"])
    ax.set_xticks(np.arange(3),["lineage\nwindows","global\nwindows","writeback\nviolations"]);ax.set_ylabel("registered count");style_axis(ax,grid=True)
    ax.text(.98,.92,"parameters restored; writeback=false",ha="right",transform=ax.transAxes,fontsize=6,color=COLORS["teal"])

    one_rows=[]
    for d in globals_data:
        for row in d["one_step_learning_rates"]:
            one_rows.append({"arm":d["arm"],"seed":d["seed"],"learning_rate":row["learning_rate"],"Delta_L":row["Delta_L"],"pass":row["pass"]})
    ax=axes[1,2]
    for arm in ["D1","D2","D3"]:
        rr=[r for r in one_rows if r["arm"]==arm]
        ax.scatter([r["learning_rate"] for r in rr],[r["Delta_L"] for r in rr],color=ARM_STYLE[arm]["color"],marker=ARM_STYLE[arm]["marker"],s=15,label=arm)
    ax.axhline(0,color=COLORS["vermillion"],ls="--",lw=.8);ax.set_xscale("log");ax.set_xlabel("learning rate");ax.set_ylabel(r"one-step $\Delta L$");style_axis(ax,grid=True);ax.legend(fontsize=5.8)

    micro_rows=[]
    ax=axes[2,0]
    for d in globals_data:
        arm=d["arm"]
        for micro in d["micro_updates"]:
            for hkey in ["horizon2","horizon4"]:
                seq=micro[hkey]["loss_sequence"]
                micro_rows.append({"arm":arm,"seed":d["seed"],"horizon":micro[hkey]["horizon"],"learning_rate":micro["learning_rate"],"loss_sequence":seq})
                ax.plot(np.arange(len(seq)),seq,color=ARM_STYLE[arm]["color"],ls="-" if hkey=="horizon2" else "--",alpha=.42,lw=.8)
    ax.set_xlabel("micro-update step");ax.set_ylabel("frozen loss");style_axis(ax,grid=True)
    ax.legend(handles=[Line2D([0],[0],color=COLORS["ink"],ls="-",label="2-step"),Line2D([0],[0],color=COLORS["ink"],ls="--",label="4-step")],fontsize=5.8)

    ax=axes[2,1];hide_axis(ax)
    ladder=[("full gradient","QUALIFIED"),("reverse/JVP","QUALIFIED"),("all-coordinate FD","NOT QUALIFIED"),("optimizer-path FD","QUALIFIED"),("actual AdamW update","QUALIFIED")]
    for i,(lab,stat) in enumerate(ladder):status_card(ax,(.10,.82-i*.17),.80,.13,lab,stat,transform=ax.transAxes,fontsize=6.2)

    ax=axes[2,2];hide_axis(ax)
    status_card(ax,(.08,.58),.84,.22,"actual update path","QUALIFIED",subtitle=summary["terminal_status"],transform=ax.transAxes,fontsize=6.2)
    status_card(ax,(.08,.20),.84,.20,"every coordinate","NOT QUALIFIED",subtitle="historical + blind misses retained",transform=ax.transAxes,fontsize=6.2)

    evidence=[
        ev("Figure 6","a","Full-gradient activity was present in the registered scope.",full_src,"active_rows/finite_rows/group_lineage_seed_pass_count","CONFIRMATORY","Direct frozen counts."),
        ev("Figure 6","b","Reverse/JVP identity passed all registered probes.",reverse_src,"pass_count/required_probe_count","CONFIRMATORY","Direct frozen counts."),
        ev("Figure 6","c,h","Coordinate/block FD coverage retained documented misses.",coord_src,"stable_probe_count/required_probe_count/failed_probes","NEGATIVE_CONFIRMATORY","Direct frozen counts; misses not repaired or dropped."),
        ev("Figure 6","c,h","Prospective blind coordinate/block coverage also retained misses.",blind_src,"pass_or_consistent_count/required_probe_count/failures","NEGATIVE_CONFIRMATORY","Direct frozen counts."),
        ev("Figure 6","d,h","Optimizer-path directional FD passed all 216 registered paths.",path_src,"path_pass_rows/reverse_jvp_pass_rows/fd_stable_rows","CONFIRMATORY","Direct frozen counts."),
        ev("Figure 6","e","Registered descent radii restored parameters with no writeback.",descent_src,"lineage_window_count/global_window_count/all_radii_restored/writeback","CONFIRMATORY","Direct frozen counts and boolean boundary."),
        ev("Figure 6","h","Actual AdamW update dynamics qualified without implying training success.",summary_src,"gates/terminal_status/counts","CONFIRMATORY","Frozen status cards; adjoining scope card has no new panel label."),
    ]
    for rel in global_sources:
        evidence.append(ev("Figure 6","f,g","Frozen actual AdamW one-step and micro-update paths are displayed.",rel,"one_step_learning_rates[].learning_rate/Delta_L; micro_updates[].horizon*.loss_sequence","CONFIRMATORY","All stored learning-rate rows and 2/4-step sequences plotted without fitting."))
    data={"full_gradient":full,"reverse_jvp":reverse,"coordinate_historical":coord,"coordinate_blind":blind,"optimizer_path":path,"local_descent":descent,"one_step_rows":one_rows,"micro_rows":micro_rows,"ladder":ladder,"stage06a":summary}
    return write_bundle("fig06",fig,data,evidence)


def _campaign_data(stage: int) -> dict[str, Any]:
    """Load every public frozen history/summary for Stage06 or Stage07."""
    if stage == 6:
        base="stage_06_Optimizer_Update_Dynamics_Training/03_formal_training/stage06c"
        seeds=[20600611,20600612,20600613]
    elif stage == 7:
        base="stage_07_Heterogeneous_Development_Pool/05_formal_retraining/stage07d"
        seeds=[20700711,20700712,20700713]
    else:
        raise ValueError(stage)
    training={};validation={};summaries={};sources=[]
    for arm in ["D1","D2","D3"]:
        for seed in seeds:
            run=f"{arm}_seed{seed}"
            t=f"{base}/training_histories/{run}.jsonl"
            v=f"{base}/validation_histories/{run}.jsonl"
            s=f"{base}/runs/{run}/run_summary.json"
            training[run]=load_jsonl(t);validation[run]=load_jsonl(v);summaries[run]=load_json(s);sources.extend([t,v,s])
    return {"training":training,"validation":validation,"summaries":summaries,"sources":sources,"seeds":seeds}


def _campaign_evidence(figure: str, campaign: dict[str, Any], panels: str) -> list[dict[str,str]]:
    out=[]
    for rel in campaign["sources"]:
        if "training_histories" in rel:
            fields="update/Q_def/L_def"
            claim="Every frozen TRAIN trajectory is included."
        elif "validation_histories" in rel:
            fields="update/TRAIN.global_balanced_Q_def/VALIDATION.global_balanced_Q_def/per_lineage_Q_def"
            claim="Every frozen scheduled validation evaluation is included."
        else:
            fields="selected_update/selected_metrics/seed_pass/terminal_reason"
            claim="Every frozen terminal run and selected checkpoint is included."
        out.append(ev(figure,panels,claim,rel,fields,"NEGATIVE_CONFIRMATORY","Raw rows in stored order; no seed or run omitted."))
    return out


def build_fig07() -> dict[str, Any]:
    scan_src="stage_06_Optimizer_Update_Dynamics_Training/03_formal_training/stage06cr/checkpoint_trajectory/all_590_checkpoint_metrics.jsonl"
    campaign_src="stage_06_Optimizer_Update_Dynamics_Training/03_formal_training/stage06c/results/stage06c_results.json"
    campaign=_campaign_data(6);scan=load_jsonl(scan_src);result=load_json(campaign_src)
    fig=new_figure(252)
    gs=fig.add_gridspec(3,3,height_ratios=[1,1,1])
    axes=[fig.add_subplot(gs[0,0]),fig.add_subplot(gs[0,1]),fig.add_subplot(gs[0,2]),fig.add_subplot(gs[1,0]),fig.add_subplot(gs[1,1]),fig.add_subplot(gs[1,2]),fig.add_subplot(gs[2,:2]),fig.add_subplot(gs[2,2])]
    _title(fig,FIGURES["fig07"]["title"])
    titles=["D1 TRAIN","D2 TRAIN","D3 TRAIN","Scheduled validation","Selected global Q","Six TRAIN lineages","All 590 checkpoints","Frozen verdict"]
    for ax,label,title in zip(axes,list("abcdefgh"),titles):_annotate_panel(ax,label,title)
    for ax,arm in zip(axes[:3],["D1","D2","D3"]):
        for run,rows in campaign["training"].items():
            if run.startswith(arm):ax.plot([r["update"] for r in rows],[r["Q_def"] for r in rows],color=ARM_STYLE[arm]["color"],alpha=.65,lw=.8,label=run.split("seed")[-1])
        direct_threshold(ax,.50,"TRAIN gate = 0.50");ax.set_xlabel("update");ax.set_ylabel(r"TRAIN $Q_{def}$");style_axis(ax,grid=True);ax.legend(fontsize=5.1)

    ax=axes[3]
    for run,rows in campaign["validation"].items():
        arm=run[:2]
        ax.plot([r["update"] for r in rows],[r["VALIDATION"]["global_balanced_Q_def"] for r in rows],color=ARM_STYLE[arm]["color"],alpha=.43,lw=.75,ls="--")
    direct_threshold(ax,.50,"displayed gate reference");ax.set_xlabel("update");ax.set_ylabel(r"VALIDATION $Q_{def}$");style_axis(ax,grid=True)
    ax.text(.02,.03,"validation does not replace TRAIN gate",transform=ax.transAxes,fontsize=6,color=COLORS["vermillion"])

    run_ids=sorted(campaign["summaries"])
    train_sel=[campaign["summaries"][r]["selected_metrics"]["TRAIN"]["global_balanced_Q_def"] for r in run_ids]
    val_sel=[campaign["summaries"][r]["selected_metrics"]["VALIDATION"]["global_balanced_Q_def"] for r in run_ids]
    ax=axes[4];x=np.arange(len(run_ids));w=.36
    ax.bar(x-w/2,train_sel,w,color=ROLE_STYLE["TRAIN"]["color"],label="TRAIN",edgecolor=COLORS["ink"])
    ax.bar(x+w/2,val_sel,w,color=ROLE_STYLE["VALIDATION"]["color"],label="VALIDATION",edgecolor=COLORS["ink"])
    direct_threshold(ax,.50,"Q=0.50");ax.set_xticks(x,[r.replace("_seed","\n") for r in run_ids],rotation=45,ha="right");ax.set_ylabel("selected Q");style_axis(ax,grid=True);ax.legend(fontsize=5.7)

    lineages=list(next(iter(campaign["summaries"].values()))["selected_metrics"]["TRAIN"]["per_lineage_Q_def"])
    mat=np.asarray([[campaign["summaries"][r]["selected_metrics"]["TRAIN"]["per_lineage_Q_def"][lin] for lin in lineages] for r in run_ids])
    ax=axes[5];im=_heatmap(ax,mat,lineages,[r.replace("_seed"," ") for r in run_ids],cmap="viridis");_vector_colorbar(fig,im,ax=ax,label=r"selected TRAIN $Q_{def}$",fraction=.04,pad=.02)

    ax=axes[6]
    for arm in ["D1","D2","D3"]:
        rows=[r for r in scan if r["arm"]==arm]
        ax.scatter([r["inventory_index"] for r in rows],[r["TRAIN_Q_def"] for r in rows],s=9,alpha=.55,color=ARM_STYLE[arm]["color"],marker=ARM_STYLE[arm]["marker"],label=arm)
    direct_threshold(ax,.50,"TRAIN gate = 0.50");ax.set_xlabel("frozen checkpoint inventory index");ax.set_ylabel(r"TRAIN $Q_{def}$");style_axis(ax,grid=True);ax.legend(fontsize=5.8)
    ax.text(.98,.92,"0 / 590 checkpoints passed TRAIN B",ha="right",transform=ax.transAxes,fontweight="bold",color=COLORS["vermillion"],fontsize=6.6)

    ax=axes[7];hide_axis(ax)
    for i,arm in enumerate(["D1","D2","D3"]):status_card(ax,(.10,.72-i*.23),.80,.17,f"{arm}: 0/3 seeds","NOT QUALIFIED",transform=ax.transAxes,fontsize=6.8)
    ax.text(.5,.08,"no trained solver • no superiority claim",ha="center",fontsize=6.2,color=COLORS["vermillion"])

    evidence=_campaign_evidence("Figure 7",campaign,"a--f,h")
    evidence.extend([
        ev("Figure 7","g","None of the complete 590-checkpoint inventory passed the TRAIN gate.",scan_src,"inventory_index/arm/TRAIN_Q_def","NEGATIVE_CONFIRMATORY","All rows plotted in frozen inventory order with preregistered Q=0.50 line."),
        ev("Figure 7","h","All nine formal runs executed and all arms finished at 0/3 seed passes.",campaign_src,"run_count/arm results/seed passes","NEGATIVE_CONFIRMATORY","Frozen terminal verdict cards."),
    ])
    train_display={run:[{"update":r["update"],"Q_def":r["Q_def"]} for r in rows] for run,rows in campaign["training"].items()}
    validation_display={run:[{"update":r["update"],"VALIDATION_Q_def":r["VALIDATION"]["global_balanced_Q_def"]} for r in rows] for run,rows in campaign["validation"].items()}
    scan_display=[{"inventory_index":r["inventory_index"],"run_id":r["run_id"],"arm":r["arm"],"update":r["update"],"TRAIN_Q_def":r["TRAIN_Q_def"]} for r in scan]
    data={"training_histories":train_display,"validation_histories":validation_display,"selected":{"run_ids":run_ids,"TRAIN_Q":train_sel,"VALIDATION_Q":val_sel,"lineages":lineages,"lineage_Q":mat},"checkpoint_scan":scan_display,"verdict":{"D1":"0/3","D2":"0/3","D3":"0/3"},"train_gate":.50,"campaign_result":{"run_count":result.get("run_count",9),"seed_passes":result.get("seed_passes",0),"status":result.get("status")}}
    source_rows=[]
    for run,rows in train_display.items():source_rows.extend({"panel":"a--c","run_id":run,"role":"TRAIN","update":r["update"],"Q_def":r["Q_def"]} for r in rows)
    for run,rows in validation_display.items():source_rows.extend({"panel":"d","run_id":run,"role":"VALIDATION","update":r["update"],"Q_def":r["VALIDATION_Q_def"]} for r in rows)
    source_rows.extend({"panel":"g","run_id":r["run_id"],"role":"TRAIN_CHECKPOINT","update":r["update"],"Q_def":r["TRAIN_Q_def"],"inventory_index":r["inventory_index"]} for r in scan_display)
    return write_bundle("fig07",fig,data,evidence,source_rows=source_rows)


def build_fig08() -> dict[str, Any]:
    pool_src="stage_07_Heterogeneous_Development_Pool/01_pool_generation/results/heterogeneity_descriptor_audit.json"
    formula_src="stage_07_Heterogeneous_Development_Pool/01_pool_generation/heterogeneity_strata/formula_identity_library.json"
    scale_src="stage_07_Heterogeneous_Development_Pool/02_defect_scale_requalification/stage07b/distribution_shift/scale_distribution_shift.json"
    scan_src="stage_07_Heterogeneous_Development_Pool/05_formal_retraining/stage07dr/checkpoint_scan/all_652_checkpoint_gate_scan.json"
    result_src="stage_07_Heterogeneous_Development_Pool/05_formal_retraining/stage07dr/results/stage07dr_results.json"
    pool=load_json(pool_src);formula=load_json(formula_src);scale=load_json(scale_src);scan=load_json(scan_src);result=load_json(result_src);campaign=_campaign_data(7)
    fig=new_figure(270);axes=fig.subplots(3,3);_title(fig,FIGURES["fig08"]["title"])
    titles=["Six → fourteen TRAIN lineages","Prospective H1–H4 strata","Target-scale shift","TRAIN_V2 trajectories","Fresh-validation trajectories","Fourteen TRAIN lineages","Four validation lineages","Common-anchor raw RMSE","Branch B"]
    for ax,label,title in zip(axes.flat,list("abcdefghi"),titles):_annotate_panel(ax,label,title)

    ax=axes[0,0]
    ax.bar([0,1],[pool["old_train_count"],pool["old_train_count"]+pool["new_train_count"]],color=[COLORS["gray_mid"],COLORS["teal"]],edgecolor=COLORS["ink"])
    ax.set_xticks([0,1],["Stage06\nTRAIN","Stage07\nTRAIN_V2"]);ax.set_ylabel("lineages");style_axis(ax,grid=True)
    ax.text(.5,.9,"prospective +8",ha="center",transform=ax.transAxes,fontweight="bold",color=COLORS["teal"])

    ax=axes[0,1];hide_axis(ax)
    strata={s:[] for s in ["H1","H2","H3","H4"]}
    for row in formula["lineages"]:strata[row["stratum"]].append(row["lineage_id"])
    for i,s in enumerate(strata):
        x=.04+(i%2)*.49;y=.62-(i//2)*.36
        status_card(ax,(x,y),.43,.25,s,"DIAGNOSTIC",subtitle=f"{len(strata[s])} frozen formulas",transform=ax.transAxes,fontsize=6.8)

    ax=axes[0,2]
    ax.bar([0,1],[scale["s_a_v1"],scale["s_a_v2"]],color=[COLORS["blue"],COLORS["orange"]],edgecolor=COLORS["ink"])
    ax.set_xticks([0,1],["v1","v2"]);ax.set_ylabel(r"frozen $s_a$");style_axis(ax,grid=True)
    ax.text(.5,.9,f"×{scale['s_a_v2_over_s_a_v1']:.3f}",ha="center",transform=ax.transAxes,fontweight="bold")

    ax=axes[1,0]
    for run,rows in campaign["training"].items():
        arm=run[:2];ax.plot([r["update"] for r in rows],[r["Q_def"] for r in rows],color=ARM_STYLE[arm]["color"],alpha=.48,lw=.75)
    direct_threshold(ax,.50,"TRAIN gate = 0.50");ax.set_xlabel("update");ax.set_ylabel(r"TRAIN_V2 $Q_{def}$");style_axis(ax,grid=True)

    ax=axes[1,1]
    for run,rows in campaign["validation"].items():
        arm=run[:2];ax.plot([r["update"] for r in rows],[r["VALIDATION"]["global_balanced_Q_def"] for r in rows],color=ARM_STYLE[arm]["color"],alpha=.48,lw=.75,ls="--")
    ax.set_xlabel("update");ax.set_ylabel(r"fresh validation $Q_{def}$");style_axis(ax,grid=True)
    ax.text(.02,.03,"fresh role • no qualification established",transform=ax.transAxes,fontsize=6,color=COLORS["vermillion"])

    run_ids=sorted(campaign["summaries"])
    train_lineages=list(next(iter(campaign["summaries"].values()))["selected_metrics"]["TRAIN"]["per_lineage_Q_def"])
    train_mat=np.asarray([[campaign["summaries"][r]["selected_metrics"]["TRAIN"]["per_lineage_Q_def"][lin] for lin in train_lineages] for r in run_ids])
    ax=axes[1,2];im=_heatmap(ax,train_mat,train_lineages,[r.replace("_seed"," ") for r in run_ids],cmap="viridis");ax.set_xticklabels(train_lineages,rotation=75,ha="right",fontsize=5.2);_vector_colorbar(fig,im,ax=ax,label="selected TRAIN Q",fraction=.04,pad=.02)

    validation_lineages=list(next(iter(campaign["summaries"].values()))["selected_metrics"]["VALIDATION"]["per_lineage_Q_def"])
    val_mat=np.asarray([[campaign["summaries"][r]["selected_metrics"]["VALIDATION"]["per_lineage_Q_def"][lin] for lin in validation_lineages] for r in run_ids])
    ax=axes[2,0];im=_heatmap(ax,val_mat,validation_lineages,[r.replace("_seed"," ") for r in run_ids],cmap="magma");_vector_colorbar(fig,im,ax=ax,label="fresh-validation Q",fraction=.04,pad=.02)

    anchor_rows=result["branch_B"]["rows"]
    ax=axes[2,1]
    x=np.arange(len(anchor_rows));ax.scatter(x,[r["stage06_raw_RMSE"] for r in anchor_rows],s=10,color=COLORS["blue"],label="Stage06");ax.scatter(x,[r["stage07_raw_RMSE"] for r in anchor_rows],s=10,color=COLORS["orange"],marker="s",label="Stage07")
    ax.set_yscale("log");ax.set_xlabel("common-anchor row");ax.set_ylabel("raw acceleration RMSE");style_axis(ax,grid=True);ax.legend(fontsize=5.8)
    ax.text(.02,.03,"scale-independent diagnostic; not a solver ranking",transform=ax.transAxes,fontsize=5.8,color=COLORS["gray"])

    ax=axes[2,2];hide_axis(ax)
    status_card(ax,(.10,.62),.80,.22,"Branch B","NOT QUALIFIED",subtitle=result["branch_B"]["BRANCH_B_OUTCOME"],transform=ax.transAxes,fontsize=7)
    status_card(ax,(.10,.26),.80,.19,"all 652 checkpoints","NOT QUALIFIED",subtitle="no TRAIN / validation / HET closure",transform=ax.transAxes,fontsize=6.2)

    evidence=_campaign_evidence("Figure 8",campaign,"d--g")
    evidence.extend([
        ev("Figure 8","a","The prospective TRAIN pool expanded from six to fourteen lineages.",pool_src,"old_train_count/new_train_count/fresh_validation_count","CONFIRMATORY","Direct frozen counts."),
        ev("Figure 8","b","H1--H4 are registered formula strata.",formula_src,"lineages[].stratum/lineage_id/role","CONFIRMATORY","Formula identities grouped by preregistered stratum."),
        ev("Figure 8","c","Prospective heterogeneity changed the frozen target scale.",scale_src,"s_a_v1/s_a_v2/s_a_v2_over_s_a_v1","DIAGNOSTIC_ONLY","Direct frozen scalars; no performance inference."),
        ev("Figure 8","h,i","Common-anchor raw RMSE does not support Branch B.",result_src,"branch_B.rows/BRANCH_B_OUTCOME","NEGATIVE_CONFIRMATORY","All 54 frozen common-anchor rows plotted; log axis."),
        ev("Figure 8","i","No checkpoint among the complete 652 inventory passed all registered gates.",scan_src,"checkpoint_count/gates_global/gates_by_arm","NEGATIVE_CONFIRMATORY","Frozen gate status card; detailed scan in Supplementary S10."),
    ])
    train_display={run:[{"update":r["update"],"Q_def":r["Q_def"]} for r in rows] for run,rows in campaign["training"].items()}
    validation_display={run:[{"update":r["update"],"VALIDATION_Q_def":r["VALIDATION"]["global_balanced_Q_def"]} for r in rows] for run,rows in campaign["validation"].items()}
    data={"pool_counts":{"old_train":pool["old_train_count"],"new_train":pool["new_train_count"],"fresh_validation":pool["fresh_validation_count"]},"strata":strata,"scale":scale,"training_histories":train_display,"validation_histories":validation_display,"run_ids":run_ids,"train_lineages":train_lineages,"train_lineage_Q":train_mat,"validation_lineages":validation_lineages,"validation_lineage_Q":val_mat,"common_anchor_rows":anchor_rows,"checkpoint_gates":{"checkpoint_count":scan["checkpoint_count"],"gates_global":scan["gates_global"],"gates_by_arm":scan["gates_by_arm"]},"branch_B":{"outcome":result["branch_B"]["BRANCH_B_OUTCOME"],"common_anchor_count":result["branch_B"]["common_anchor_count"]}}
    source_rows=[]
    for run,rows in train_display.items():source_rows.extend({"panel":"d","run_id":run,"role":"TRAIN","update":r["update"],"Q_def":r["Q_def"]} for r in rows)
    for run,rows in validation_display.items():source_rows.extend({"panel":"e","run_id":run,"role":"VALIDATION","update":r["update"],"Q_def":r["VALIDATION_Q_def"]} for r in rows)
    source_rows.extend({"panel":"h","run_id":r.get("stage07_run"),"role":"COMMON_ANCHOR","lineage":r["lineage"],"stage06_raw_RMSE":r["stage06_raw_RMSE"],"stage07_raw_RMSE":r["stage07_raw_RMSE"]} for r in anchor_rows)
    return write_bundle("fig08",fig,data,evidence,source_rows=source_rows)


def build_fig09() -> dict[str, Any]:
    formula_src="stage_07_Heterogeneous_Development_Pool/01_pool_generation/heterogeneity_strata/formula_identity_library.json"
    descriptor_src="stage_07_Heterogeneous_Development_Pool/05_formal_retraining/stage07dr/descriptor_geometry/descriptor_support_geometry.json"
    target_src="stage_07_Heterogeneous_Development_Pool/05_formal_retraining/stage07dr/target_geometry/target_manifold_geometry.json"
    gradient_src="stage_07_Heterogeneous_Development_Pool/05_formal_retraining/stage07dr/gradient_geometry/d3_cross_lineage_gradient_geometry.json"
    tangent_src="stage_07_Heterogeneous_Development_Pool/05_formal_retraining/stage07dr/tangent_reducibility/d3_tangent_reducibility.json"
    origin_src="stage_07_Heterogeneous_Development_Pool/05_formal_retraining/stage07dr/het_s2_02_support_analysis/h2_origin_level_analysis.json"
    basis_src="stage_07_Heterogeneous_Development_Pool/02_defect_scale_requalification/stage07b/pair_basis_representability/pair_basis_summary.json"
    formula=load_json(formula_src);descriptor=load_json(descriptor_src);target=load_json(target_src);gradient=load_json(gradient_src);tangent=load_json(tangent_src);origin=load_json(origin_src);basis=load_json(basis_src)
    h2=[r for r in formula["lineages"] if r["stratum"]=="H2"]

    fig=new_figure(274);axes=fig.subplots(3,3);_title(fig,FIGURES["fig09"]["title"])
    titles=["H2 formulas and modes","Robust descriptor distances","Exceeded descriptor envelopes","TRAIN-only target PCA","Target residual / gate","D3 15×15 gradient cosines","Three-seed conflict","Local tangent reducibility","Origin consistency"]
    for ax,label,title in zip(axes.flat,list("abcdefghi"),titles):_annotate_panel(ax,label,title)

    ax=axes[0,0];hide_axis(ax)
    for i,row in enumerate(h2):
        y=.75-i*.25;stat="DIAGNOSTIC" if row["role"]!="FRESH_VALIDATION_V2" else "NOT QUALIFIED"
        status_card(ax,(.05,y),.90,.18,row["lineage_id"],stat,subtitle=f"{row['role']} • k={row['wavevectors']}",transform=ax.transAxes,fontsize=6.1)
    ax.text(.5,.06,"same formula class; distinct frozen identity",ha="center",fontsize=6.1,color=COLORS["gray"])

    ax=axes[0,1]
    dist=[descriptor["robust_standardized_Euclidean_to_HET_S2_01"],descriptor["robust_standardized_Euclidean_to_HET_S2_03"]]
    ax.bar([0,1],dist,color=[COLORS["blue"],COLORS["orange"]],edgecolor=COLORS["ink"])
    direct_threshold(ax,descriptor["TRAIN_LOO_NN_p95_threshold"],"TRAIN LOO p95")
    ax.set_xticks([0,1],["to HET_S2_01","to HET_S2_03"]);ax.set_ylabel("robust standardized distance");style_axis(ax,grid=True)
    ax.text(.98,.96,f"nearest = {descriptor['nearest_neighbor_distance']:.4f}\nOUTSIDE TRAIN SUPPORT",ha="right",va="top",transform=ax.transAxes,fontsize=6.1,color=COLORS["vermillion"])

    ax=axes[0,2]
    exceeded=descriptor["envelope_exceeded_features"];x=np.arange(len(exceeded));width=.24
    for j,lineage in enumerate(["HET_S2_01","HET_S2_02","HET_S2_03"]):
        ax.bar(x+(j-1)*width,[descriptor["H2_frozen_descriptors"][lineage][f] for f in exceeded],width,label=lineage,color=[COLORS["blue"],COLORS["vermillion"],COLORS["orange"]][j],edgecolor=COLORS["ink"])
    ax.set_yscale("log");ax.set_xticks(x,["source RMS","target-defect RMS","bounded coeff. RMS"],rotation=18,ha="right");ax.set_ylabel("frozen descriptor value");style_axis(ax,grid=True);ax.legend(fontsize=5.1)

    lineages=list(target["nodal_correction_PCA_coefficients"])
    coeff=np.asarray([target["nodal_correction_PCA_coefficients"][k] for k in lineages])
    ax=axes[1,0];im=_heatmap(ax,coeff,[f"PC{i+1}" for i in range(coeff.shape[1])],lineages,cmap="coolwarm");ax.set_yticklabels(lineages,fontsize=5.1);_vector_colorbar(fig,im,ax=ax,label="frozen PCA coefficient",fraction=.04,pad=.02)
    ax.text(.99,.02,f"TRAIN-only basis • explained={target['TRAIN_explained_fraction']:.3f}",ha="right",transform=ax.transAxes,fontsize=5.8,color=COLORS["gray"])

    ax=axes[1,1]
    vals=[target["HET_S2_02_reconstruction_residual"],target["TRAIN_reconstruction_residual_p95"]]
    ax.bar([0,1],vals,color=[COLORS["vermillion"],COLORS["gray_light"]],edgecolor=COLORS["ink"])
    ax.set_xticks([0,1],["HET_S2_02","TRAIN p95"]);ax.set_ylabel("target reconstruction residual");style_axis(ax,grid=True)
    ax.text(.5,.91,"TARGET OUTSIDE SUPPORT",ha="center",transform=ax.transAxes,fontweight="bold",color=COLORS["vermillion"],fontsize=5.9)

    seed0="D3_seed20700711";cos_dict=gradient[seed0]["cosine_matrix_15x15"];cos_names=list(cos_dict);cos_mat=np.asarray([[cos_dict[a][b] for b in cos_names] for a in cos_names])
    ax=axes[1,2];im=_heatmap(ax,cos_mat,cos_names,cos_names,vmin=-1,vmax=1,cmap="coolwarm");ax.set_xticklabels(cos_names,rotation=90,fontsize=4.6);ax.set_yticklabels(cos_names,fontsize=4.6);_vector_colorbar(fig,im,ax=ax,label="cosine",fraction=.04,pad=.02)

    ax=axes[2,0]
    seeds=list(gradient);x=np.arange(3)
    means=[gradient[s]["mean_cosine_vs_14_TRAIN"] for s in seeds];mins=[gradient[s]["minimum"] for s in seeds];negs=[gradient[s]["negative_fraction"] for s in seeds]
    ax.bar(x-.18,means,.36,color=COLORS["blue"],label="mean cosine",edgecolor=COLORS["ink"]);ax.bar(x+.18,mins,.36,color=COLORS["vermillion"],label="minimum",edgecolor=COLORS["ink"])
    ax.plot(x,negs,color=COLORS["orange"],marker="D",label="negative fraction")
    ax.axhline(0,color=COLORS["gray"],lw=.8);ax.set_xticks(x,[s.split("seed")[-1] for s in seeds]);ax.set_ylabel("cosine / fraction");style_axis(ax,grid=True);ax.legend(fontsize=5.2)

    ax=axes[2,1]
    tangent_rows=[]
    for s in tangent:
        row=tangent[s]["lineages"]["HET_S2_02"]
        tangent_rows.append({"seed":s,"full":row["full_network"]["TANGENT_REDUCIBLE_FRACTION"],"pair":row["pair_head"]["TANGENT_REDUCIBLE_FRACTION"],"classification":row["classification"]})
    x=np.arange(3);ax.bar(x-.18,[r["full"] for r in tangent_rows],.36,color=COLORS["teal"],label="full network",edgecolor=COLORS["ink"]);ax.bar(x+.18,[r["pair"] for r in tangent_rows],.36,color=COLORS["blue"],label="pair head",edgecolor=COLORS["ink"])
    ax.set_xticks(x,[r["seed"].split("seed")[-1] for r in tangent_rows]);ax.set_ylim(.995,1.0002);ax.set_ylabel("tangent-reducible fraction");style_axis(ax,grid=True);ax.legend(fontsize=5.3)
    ax.text(.02,.93,"HIGH ≠ target supported",ha="left",va="top",transform=ax.transAxes,fontsize=6,color=COLORS["vermillion"])

    ax=axes[2,2]
    origin_rows=origin["rows"]
    for variant,color,marker in [("LOW",COLORS["blue"],"o"),("MAIN",COLORS["orange"],"s")]:
        rr=[r for r in origin_rows if r["variant"]==variant]
        ax.scatter([r["temporal_phase_fraction"] for r in rr],[r["model_residual_raw_RMSE"] for r in rr],s=7,alpha=.45,color=color,marker=marker,label=variant)
    ax.set_xlabel("temporal phase fraction");ax.set_ylabel("origin-level raw RMSE");style_axis(ax,grid=True);ax.legend(fontsize=5.5)
    ax.text(.98,.97,f"basis representability: {'PASS' if basis.get('pass',False) else 'see source'}\ntarget support: FAIL",ha="right",va="top",transform=ax.transAxes,fontsize=5.8,color=COLORS["vermillion"])

    evidence=[
        ev("Figure 9","a","HET_S2_01/02/03 share the H2 formula class but have distinct roles and identities.",formula_src,"lineages[stratum=H2].material_map/wavevectors/role/formula_sha256","CONFIRMATORY","Frozen identity cards; formula text is not numerically re-evaluated."),
        ev("Figure 9","b,c","HET_S2_02 lies outside robust descriptor support and exceeds three registered envelopes.",descriptor_src,"nearest_neighbor_distance/TRAIN_LOO_NN_p95_threshold/envelope_exceeded_features/H2_frozen_descriptors","DIAGNOSTIC_ONLY","Direct frozen distances and raw H2 descriptor values; no invented 2-D embedding."),
        ev("Figure 9","d,e","TRAIN-only target PCA places HET_S2_02 outside correction-target support.",target_src,"nodal_correction_PCA_coefficients/HET_S2_02_reconstruction_residual/TRAIN_reconstruction_residual_p95/classification","CONFIRMATORY","Precomputed frozen PCA coordinates and residuals only; no refit."),
        ev("Figure 9","f,g","D3 frozen gradients show systematic cross-lineage conflict in all three seeds.",gradient_src,"*.cosine_matrix_15x15/mean_cosine_vs_14_TRAIN/minimum/negative_fraction/classification","DIAGNOSTIC_ONLY","One complete precomputed cosine matrix plus direct three-seed summary values."),
        ev("Figure 9","h","HET_S2_02 is highly locally tangent-reducible in the registered diagnostic.",tangent_src,"*.lineages.HET_S2_02.*.TANGENT_REDUCIBLE_FRACTION/classification","DIAGNOSTIC_ONLY","Direct frozen values; no optimizer or writeback."),
        ev("Figure 9","i","Origin-level residual patterns are retained for both variants.",origin_src,"rows[].temporal_phase_fraction/model_residual_raw_RMSE/variant","DIAGNOSTIC_ONLY","All 576 frozen rows plotted without regression."),
        ev("Figure 9","i","Pair-basis representability is distinct from target support.",basis_src,"pass and bounded/unbounded summary","CONFIRMATORY","Boundary annotation only."),
    ]
    data={"H2_lineages":h2,"descriptor":{"distances":dist,"threshold":descriptor["TRAIN_LOO_NN_p95_threshold"],"classification":descriptor["classification"],"exceeded_features":exceeded,"raw_H2":descriptor["H2_frozen_descriptors"]},"target":{"lineages":lineages,"coefficients":coeff,"residual":target["HET_S2_02_reconstruction_residual"],"threshold":target["TRAIN_reconstruction_residual_p95"],"classification":target["classification"]},"cosine_seed":seed0,"cosine_names":cos_names,"cosine_matrix":cos_mat,"gradient_seed_summary":[{"seed":s,"mean":gradient[s]["mean_cosine_vs_14_TRAIN"],"minimum":gradient[s]["minimum"],"negative_fraction":gradient[s]["negative_fraction"],"classification":gradient[s]["classification"]} for s in seeds],"tangent":tangent_rows,"origin_rows":origin_rows,"basis":basis}
    return write_bundle("fig09",fig,data,evidence,source_rows=origin_rows)


def build_fig10() -> dict[str, Any]:
    candidate_src="stage_08_Systematic_Coverage_V3/01_systematic_coverage_design/qualification/candidate_level_qualification.json"
    selection_src="stage_08_Systematic_Coverage_V3/01_systematic_coverage_design/coverage_optimizer/lexicographic_selection_trace.json"
    train_src="stage_08_Systematic_Coverage_V3/01_systematic_coverage_design/train_selection/train_v3_coverage_qualification.json"
    validation_src="stage_08_Systematic_Coverage_V3/01_systematic_coverage_design/validation_selection/fresh_validation_v3_selection.json"
    summary_src="stage_08_Systematic_Coverage_V3/01_systematic_coverage_design/qualification/stage08a_qualification_summary.json"
    claim_src="stage_08Z_Project_Closure_Publication/03_claim_matrix/final_claim_support_matrix.json"
    stage07_descriptor_src="stage_07_Heterogeneous_Development_Pool/05_formal_retraining/stage07dr/descriptor_geometry/descriptor_support_geometry.json"
    candidate=load_json(candidate_src);selection=load_json(selection_src);train=load_json(train_src);validation=load_json(validation_src);summary=load_json(summary_src);claims=load_json(claim_src);stage07_descriptor=load_json(stage07_descriptor_src)
    templates=sorted({row["template"] for row in candidate["rows"]})
    fig=new_figure(285)
    gs=fig.add_gridspec(4,3,height_ratios=[1.05,1,1,1])
    axes=[fig.add_subplot(gs[0,0]),fig.add_subplot(gs[0,1]),fig.add_subplot(gs[0,2]),fig.add_subplot(gs[1,0]),fig.add_subplot(gs[1,1]),fig.add_subplot(gs[1,2]),fig.add_subplot(gs[2,0]),fig.add_subplot(gs[2,1]),fig.add_subplot(gs[2,2]),fig.add_subplot(gs[3,:])]
    _title(fig,FIGURES["fig10"]["title"])
    titles=["Sixteen templates","Frozen candidate banks","Eight selected TRAIN candidates","Descriptor distance","Target residual / gate","Descriptor vs target","Validation macro groups","Formal fresh closure","Zero prediction reads","Final qualification ladder"]
    for ax,label,title in zip(axes,list("abcdefghij"),titles):_annotate_panel(ax,label,title)

    ax=axes[0];hide_axis(ax)
    for i,t in enumerate(templates):
        col=i%4;row=i//4;x=.03+col*.245;y=.78-row*.20
        status_card(ax,(x,y),.20,.14,str(t),"DIAGNOSTIC",transform=ax.transAxes,fontsize=5.8)
    ax.text(.5,.04,"structural coverage templates • schematic registry",ha="center",fontsize=5.8,color=COLORS["gray"])

    ax=axes[1]
    ax.bar([0,1],[summary["counts"]["train_candidates"],summary["counts"]["validation_candidates"]],color=[ROLE_STYLE["TRAIN"]["color"],ROLE_STYLE["VALIDATION"]["color"]],edgecolor=COLORS["ink"])
    ax.set_xticks([0,1],["TRAIN bank","validation bank"]);ax.set_ylabel("candidates");style_axis(ax,grid=True)
    ax.text(.5,.90,f"{candidate['passed']}/{candidate['required']} candidate-level PASS",ha="center",transform=ax.transAxes,fontweight="bold",fontsize=6.1)

    ax=axes[2];hide_axis(ax)
    selected=selection["result"]
    for i,item in enumerate(selected):
        x=.03+(i%2)*.49;y=.78-(i//2)*.20
        status_card(ax,(x,y),.44,.14,item,"QUALIFIED",subtitle=f"slot {i+1}",transform=ax.transAxes,fontsize=5.8)

    ax=axes[3]
    before=stage07_descriptor["nearest_neighbor_distance"];after=train["HET_S2_02"]["Stage08_descriptor_distance"]
    ax.bar([0,1],[before,after],color=[COLORS["gray_mid"],COLORS["teal"]],edgecolor=COLORS["ink"])
    ax.set_xticks([0,1],["Stage07","Stage08"]);ax.set_ylabel("descriptor NN distance");style_axis(ax,grid=True)
    ax.text(.5,.90,f"{before:.3f} → {after:.3f}",ha="center",transform=ax.transAxes,fontweight="bold")
    ax.text(.5,.04,"proximity improved; global coverage not qualified",ha="center",transform=ax.transAxes,fontsize=5.9,color=COLORS["vermillion"])

    ax=axes[4]
    residual=train["HET_S2_02"]["Stage08_target_PCA_residual"];threshold=train["HET_S2_02"]["Stage08_target_threshold"]
    ax.bar([0,1],[residual,threshold],color=[COLORS["vermillion"],COLORS["gray_light"]],edgecolor=COLORS["ink"])
    ax.set_xticks([0,1],["HET_S2_02","TRAIN p95"]);ax.set_ylabel("target residual");style_axis(ax,grid=True)
    ax.text(.5,.90,f"{residual:.3f} > {threshold:.3f}",ha="center",transform=ax.transAxes,fontweight="bold",color=COLORS["vermillion"])

    ax=axes[5];hide_axis(ax)
    status_card(ax,(.10,.61),.80,.20,"descriptor gate J","QUALIFIED",subtitle=f"distance {after:.3f}",transform=ax.transAxes,fontsize=6.3)
    status_card(ax,(.10,.25),.80,.20,"target gate K","NOT QUALIFIED",subtitle=f"residual {residual:.3f}",transform=ax.transAxes,fontsize=6.3)

    ax=axes[6]
    groups=[r["macro_group"] for r in validation["audit"]];counts=[r["candidate_count"] for r in validation["audit"]];eligible=[r["eligible_count"] for r in validation["audit"]]
    x=np.arange(4);ax.bar(x,counts,color=COLORS["gray_light"],edgecolor=COLORS["gray"],label="candidates");ax.bar(x,eligible,color=COLORS["orange"],edgecolor=COLORS["ink"],label="provisional eligible")
    short_groups=[g.replace("spatial_frequency_","spatial-freq.\n").replace("frequency_heterogeneous","frequency\nheterogeneous").replace("multi_temporal","multi-\ntemporal").replace("rotating_anisotropic","rotating\nanisotropic").replace("mixed_LT","mixed\nL/T") for g in groups]
    ax.set_xticks(x,short_groups);ax.set_ylabel("candidates");style_axis(ax,grid=True);ax.legend(fontsize=5.3)

    ax=axes[7];hide_axis(ax)
    status_card(ax,(.12,.54),.76,.28,"0 / 4 formal","NOT QUALIFIED",subtitle=f"provisional winners={len(validation['provisional_eligible_group_winners'])}; selected={len(validation['selected'])}",transform=ax.transAxes,fontsize=7)
    ax.text(.5,.20,f"formal role closure = {str(validation['formal_role_closure']).lower()}",ha="center",fontsize=6.2,color=COLORS["vermillion"])

    ax=axes[8];hide_axis(ax)
    zero_counts=[("model predictions",summary["counts"]["model_predictions_read"]),("model forwards",summary["counts"]["model_forwards"]),("training runs",summary["counts"]["training_runs"])]
    for i,(lab,val) in enumerate(zero_counts):status_card(ax,(.10,.72-i*.22),.80,.16,f"{lab}: {val}","NOT ACCESSED" if i<2 else "DIAGNOSTIC",transform=ax.transAxes,fontsize=6.2)

    ax=axes[9];hide_axis(ax)
    ladder=[("dynamic architecture","QUALIFIED"),("zero correction","VERIFIED"),("defect target","QUALIFIED"),("actual updates","QUALIFIED"),("formal training","NOT QUALIFIED"),("validation closure","NOT QUALIFIED"),("target support","NOT QUALIFIED"),("autonomous rollout","NOT QUALIFIED"),("sealed test","NOT ACCESSED"),("full-solver route","NOT QUALIFIED")]
    xs=np.linspace(.02,.98,len(ladder))
    for i,((lab,stat),x) in enumerate(zip(ladder,xs)):
        status_card(ax,(x-.045,.34),.09,.35,lab.replace(" ","\n"),stat,transform=ax.transAxes,fontsize=5.8)
        if i<len(ladder)-1:arrow(ax,(x+.045,.515),(xs[i+1]-.045,.515),transform=ax.transAxes)
    ax.text(.5,.12,"PROJECT_FULL_SOLVER_ROUTE_CLOSED_PUBLICATION_EVIDENCE_FROZEN",ha="center",fontweight="bold",fontsize=7,color=COLORS["vermillion"])

    evidence=[
        ev("Figure 10","a,b","The systematic bank contains 16 templates and 128+64 frozen candidates; all 192 passed candidate-level physics checks.",candidate_src,"rows[].template/bank/qualification; passed/required","CONFIRMATORY","Unique template registry and direct frozen bank counts; candidate generation not rerun."),
        ev("Figure 10","c","Eight systematic TRAIN candidates were selected by the frozen lexicographic trace.",selection_src,"result/trace","CONFIRMATORY","Selected IDs rendered in frozen slot order; no reselection."),
        ev("Figure 10","d","Stage07 HET_S2_02 descriptor distance is the frozen pre-design reference.",stage07_descriptor_src,"nearest_neighbor_distance/classification","DIAGNOSTIC_ONLY","Direct frozen scalar; no embedding or recomputation."),
        ev("Figure 10","d--f","Descriptor proximity improved, but HET_S2_02 target support failed.",train_src,"HET_S2_02.Stage08_descriptor_distance/Stage08_target_PCA_residual/Stage08_target_threshold/gates","NEGATIVE_CONFIRMATORY","Direct frozen scalars; paired status cards prevent descriptor-pass/target-fail conflation."),
        ev("Figure 10","g,h","Formal fresh-validation closure remained 0/4.",validation_src,"audit[].macro_group/candidate_count/eligible_count/provisional_eligible_group_winners/selected/formal_role_closure","NEGATIVE_CONFIRMATORY","Direct counts for all four macro groups; provisional and formal states separated."),
        ev("Figure 10","i,j","The coverage cycle used zero model-prediction reads and did not authorize training.",summary_src,"counts/model predictions/model forwards/training runs/final_status/gates","NEGATIVE_CONFIRMATORY","Direct frozen counters and final qualification cards."),
        ev("Figure 10","j","Qualified lower layers and prohibited full-solver claims remain separated.",claim_src,"allowed_claims/prohibited_claims","NEGATIVE_CONFIRMATORY","Final ladder organized by claim layer."),
    ]
    data={"templates":templates,"candidate_counts":summary["counts"],"candidate_qualification":{"passed":candidate["passed"],"required":candidate["required"]},"selected":selected,"selection_trace":selection["trace"],"HET_S2_02":train["HET_S2_02"],"train_gates":train["gates"],"validation_audit":validation["audit"],"validation_provisional":validation["provisional_eligible_group_winners"],"validation_selected":validation["selected"],"formal_role_closure":validation["formal_role_closure"],"zero_counts":zero_counts,"ladder":ladder,"final_status":summary["final_status"],"claim_matrix_keys":list(claims) if isinstance(claims,dict) else []}
    return write_bundle("fig10",fig,data,evidence,source_rows=candidate["rows"])


BUILDERS = {
    "graphical_abstract": build_graphical_abstract,
    "fig01": build_fig01,
    "fig02": build_fig02,
    "fig03": build_fig03,
    "fig04": build_fig04,
    "fig05": build_fig05,
    "fig06": build_fig06,
    "fig07": build_fig07,
    "fig08": build_fig08,
    "fig09": build_fig09,
    "fig10": build_fig10,
}


def build_all() -> list[dict[str, Any]]:
    return [BUILDERS[key]() for key in FIGURES]


def parse_args() -> argparse.Namespace:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--figure",choices=list(BUILDERS),help="Build one figure; default builds all.")
    return parser.parse_args()


def main() -> None:
    args=parse_args()
    if args.figure:
        BUILDERS[args.figure]()
    else:
        build_all()


if __name__ == "__main__":
    main()
