"""Deterministic Markdown renderer for evaluator summaries."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def render_qualification_summary(
    shear_gates: Mapping[str, Any],
    acoustic_gates: Mapping[str, Any],
    uncertainty: Mapping[str, Any],
    provenance_complete: bool,
) -> str:
    lines = ["# Independent validation qualification summary", ""]
    for title, block in (("Shear gates", shear_gates), ("Acoustic gates", acoustic_gates)):
        lines.extend((f"## {title}", "", "| Gate | Status |", "|---|---|"))
        for name, evidence in sorted(block.get("gates", {}).items()):
            lines.append(f"| {name} | {evidence['status']} |")
        lines.append("")
    lines.extend(
        (
            "## Evidence completeness",
            "",
            f"- Uncertainty complete: `{bool(uncertainty.get('complete'))}`",
            f"- Provenance complete: `{bool(provenance_complete)}`",
            "- Single total GCI: `not generated`",
            "",
        )
    )
    return "\n".join(lines)
