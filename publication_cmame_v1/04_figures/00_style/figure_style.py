"""Shared matplotlib style for the frozen CMAME figure suite.

This module contains display helpers only.  It does not import project solver, model,
training, optimization, or candidate-generation code.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


MM_PER_INCH = 25.4
FULL_WIDTH_MM = 190.0
PNG_DPI = 600

COLORS = {
    "black": "#111111",
    "ink": "#2B2B2B",
    "gray": "#6B6B6B",
    "gray_mid": "#9A9A9A",
    "gray_light": "#D7D7D7",
    "gray_pale": "#F2F2F2",
    "blue": "#0072B2",
    "blue_light": "#DCEEF8",
    "sky": "#56B4E9",
    "teal": "#009E73",
    "teal_light": "#DDF3EC",
    "orange": "#E69F00",
    "orange_light": "#FAEDCF",
    "vermillion": "#D55E00",
    "vermillion_light": "#F7E3D8",
    "purple": "#CC79A7",
    "purple_light": "#F3E4EC",
    "yellow": "#F0E442",
    "train": "#2B4C7E",
    "validation": "#E69F00",
    "sealed": "#111111",
}

ARM_STYLE = {
    "D0": {"color": COLORS["gray"], "marker": "o", "linestyle": "-", "hatch": ".."},
    "D1": {"color": COLORS["blue"], "marker": "o", "linestyle": "-", "hatch": ""},
    "D2": {"color": COLORS["teal"], "marker": "s", "linestyle": "--", "hatch": "\\\\"},
    "D3": {"color": COLORS["purple"], "marker": "D", "linestyle": "-.", "hatch": "xx"},
}

ROLE_STYLE = {
    "TRAIN": {"color": COLORS["train"], "marker": "o", "linestyle": "-"},
    "VALIDATION": {"color": COLORS["validation"], "marker": "s", "linestyle": "--"},
    "SEALED": {"color": COLORS["sealed"], "marker": "X", "linestyle": ":"},
}

STATUS_STYLE = {
    "VERIFIED": {
        "edgecolor": COLORS["blue"],
        "facecolor": COLORS["blue_light"],
        "marker": "o",
        "linestyle": "-",
        "hatch": "",
    },
    "QUALIFIED": {
        "edgecolor": COLORS["teal"],
        "facecolor": COLORS["teal_light"],
        "marker": "s",
        "linestyle": "-",
        "hatch": "",
    },
    "NOT QUALIFIED": {
        "edgecolor": COLORS["vermillion"],
        "facecolor": COLORS["vermillion_light"],
        "marker": "x",
        "linestyle": "--",
        "hatch": "////",
    },
    "DIAGNOSTIC": {
        "edgecolor": COLORS["orange"],
        "facecolor": COLORS["orange_light"],
        "marker": "^",
        "linestyle": ":",
        "hatch": "..",
    },
    "NOT ACCESSED": {
        "edgecolor": COLORS["gray"],
        "facecolor": COLORS["gray_pale"],
        "marker": "X",
        "linestyle": ":",
        "hatch": "xx",
    },
}


def apply_style(base_font_size: float = 7.4) -> None:
    """Apply the suite-wide publication style before creating figures."""

    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = [
        "Arial",
        "Helvetica",
        "DejaVu Sans",
        "Liberation Sans",
    ]
    plt.rcParams["svg.fonttype"] = "none"
    plt.rcParams["pdf.fonttype"] = 42
    plt.rcParams["ps.fonttype"] = 42
    plt.rcParams["font.size"] = base_font_size
    plt.rcParams["axes.titlesize"] = 8.5
    plt.rcParams["axes.titleweight"] = "bold"
    plt.rcParams["axes.labelsize"] = 8.0
    plt.rcParams["axes.linewidth"] = 0.65
    plt.rcParams["axes.spines.top"] = False
    plt.rcParams["axes.spines.right"] = False
    plt.rcParams["xtick.labelsize"] = 7.2
    plt.rcParams["ytick.labelsize"] = 7.2
    plt.rcParams["xtick.major.width"] = 0.6
    plt.rcParams["ytick.major.width"] = 0.6
    plt.rcParams["xtick.major.size"] = 2.8
    plt.rcParams["ytick.major.size"] = 2.8
    plt.rcParams["lines.linewidth"] = 1.25
    plt.rcParams["lines.markersize"] = 4.0
    plt.rcParams["legend.fontsize"] = 7.0
    plt.rcParams["legend.frameon"] = False
    plt.rcParams["figure.facecolor"] = "white"
    plt.rcParams["axes.facecolor"] = "white"
    plt.rcParams["savefig.facecolor"] = "white"
    plt.rcParams["savefig.transparent"] = False


def mm_to_inch(value_mm: float) -> float:
    return value_mm / MM_PER_INCH


def new_figure(height_mm: float, *, constrained_layout: bool = True):
    """Create a full-width CMAME figure at its intended print dimensions."""

    apply_style()
    return plt.figure(
        figsize=(mm_to_inch(FULL_WIDTH_MM), mm_to_inch(height_mm)),
        constrained_layout=constrained_layout,
    )


def style_axis(ax, *, grid: bool = False) -> None:
    ax.spines["left"].set_color(COLORS["ink"])
    ax.spines["bottom"].set_color(COLORS["ink"])
    ax.tick_params(colors=COLORS["ink"])
    if grid:
        ax.grid(axis="y", color=COLORS["gray_light"], linewidth=0.45, alpha=0.75)
        ax.set_axisbelow(True)


def panel_label(ax, label: str, *, x: float = -0.08, y: float = 1.04) -> None:
    ax.text(
        x,
        y,
        label,
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=10.0,
        fontweight="bold",
        color=COLORS["black"],
        clip_on=False,
    )


def provenance_tag(ax, text: str, *, x: float = 0.99, y: float = 0.01) -> None:
    ax.text(
        x,
        y,
        text,
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=6.2,
        color=COLORS["gray"],
    )


def status_card(
    ax,
    xy: tuple[float, float],
    width: float,
    height: float,
    text: str,
    status: str,
    *,
    subtitle: str | None = None,
    transform=None,
    fontsize: float = 7.2,
    zorder: int = 2,
):
    """Draw a print-safe status card in data or axes coordinates."""

    transform = transform or ax.transData
    style = STATUS_STYLE[status]
    patch = FancyBboxPatch(
        xy,
        width,
        height,
        boxstyle="round,pad=0.012,rounding_size=0.018",
        linewidth=1.0,
        edgecolor=style["edgecolor"],
        facecolor=style["facecolor"],
        linestyle=style["linestyle"],
        hatch=style["hatch"],
        transform=transform,
        zorder=zorder,
    )
    ax.add_patch(patch)
    x, y = xy
    ax.text(
        x + width / 2,
        y + height * (0.58 if subtitle else 0.5),
        text,
        transform=transform,
        ha="center",
        va="center",
        fontsize=fontsize,
        fontweight="bold",
        color=COLORS["ink"],
        zorder=zorder + 1,
    )
    if subtitle:
        ax.text(
            x + width / 2,
            y + height * 0.25,
            subtitle,
            transform=transform,
            ha="center",
            va="center",
            fontsize=max(fontsize - 1.0, 5.8),
            color=COLORS["gray"],
            zorder=zorder + 1,
        )
    return patch


def arrow(
    ax,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    transform=None,
    color: str = COLORS["gray"],
    linestyle: str = "-",
    mutation_scale: float = 8.0,
    zorder: int = 1,
):
    transform = transform or ax.transData
    patch = FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>",
        mutation_scale=mutation_scale,
        linewidth=0.9,
        linestyle=linestyle,
        color=color,
        transform=transform,
        zorder=zorder,
    )
    ax.add_patch(patch)
    return patch


def direct_threshold(
    ax,
    value: float,
    label: str,
    *,
    orientation: str = "horizontal",
    color: str = COLORS["vermillion"],
):
    if orientation == "horizontal":
        ax.axhline(value, color=color, linestyle="--", linewidth=0.95, zorder=1)
        ax.annotate(
            label,
            xy=(1.0, value),
            xycoords=("axes fraction", "data"),
            xytext=(-2, 2),
            textcoords="offset points",
            ha="right",
            va="bottom",
            fontsize=6.5,
            color=color,
        )
    else:
        ax.axvline(value, color=color, linestyle="--", linewidth=0.95, zorder=1)
        ax.annotate(
            label,
            xy=(value, 1.0),
            xycoords=("data", "axes fraction"),
            xytext=(2, -2),
            textcoords="offset points",
            ha="left",
            va="top",
            fontsize=6.5,
            color=color,
            rotation=90,
        )


def shared_legend(fig, handles: Iterable, labels: Sequence[str], *, ncol: int = 4):
    return fig.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.995),
        ncol=ncol,
        frameon=False,
        columnspacing=1.2,
        handlelength=2.0,
    )


def save_figure(fig, output_base: str | Path, *, dpi: int = PNG_DPI) -> Mapping[str, str]:
    """Save editable SVG/PDF and a 600 dpi PNG review preview."""

    base = Path(output_base)
    base.parent.mkdir(parents=True, exist_ok=True)
    paths = {
        "svg": str(base.with_suffix(".svg")),
        "pdf": str(base.with_suffix(".pdf")),
        "png": str(base.with_suffix(".png")),
    }
    fig.savefig(paths["svg"], metadata={"Creator": "Python/matplotlib"})
    fig.savefig(paths["pdf"], metadata={"Creator": "Python/matplotlib"})
    fig.savefig(paths["png"], dpi=dpi)
    plt.close(fig)
    return paths


def hide_axis(ax) -> None:
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)


def annotate_bars(ax, bars, *, fmt: str = "{:.2f}", fontsize: float = 6.5) -> None:
    for bar in bars:
        value = bar.get_height()
        ax.annotate(
            fmt.format(value),
            xy=(bar.get_x() + bar.get_width() / 2, value),
            xytext=(0, 2),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=fontsize,
            color=COLORS["ink"],
        )


__all__ = [
    "ARM_STYLE",
    "COLORS",
    "FULL_WIDTH_MM",
    "PNG_DPI",
    "ROLE_STYLE",
    "STATUS_STYLE",
    "annotate_bars",
    "apply_style",
    "arrow",
    "direct_threshold",
    "hide_axis",
    "mm_to_inch",
    "new_figure",
    "panel_label",
    "provenance_tag",
    "save_figure",
    "shared_legend",
    "status_card",
    "style_axis",
]
