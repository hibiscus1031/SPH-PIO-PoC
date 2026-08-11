#!/usr/bin/env python3
"""Assemble indexes, evidence registries, and submission exports for figure suite v1."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any

from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
SUITE = ROOT / "publication_cmame_v1" / "04_figures"
EVIDENCE_DIR = SUITE / "13_evidence_maps"
EXPORT_DIR = SUITE / "14_exports"


MAIN = [
    ("Graphical abstract", "01_graphical_abstract", "graphical_abstract", "route"),
    ("Figure 1", "02_fig01_framework", "fig01_framework", "a--e"),
    ("Figure 2", "03_fig02_architecture", "fig02_architecture", "a--i"),
    ("Figure 3", "04_fig03_verification", "fig03_verification", "a--g"),
    ("Figure 4", "05_fig04_failed_learning_routes", "fig04_failed_learning_routes", "a--g"),
    ("Figure 5", "06_fig05_discrete_defect", "fig05_discrete_defect", "a--h"),
    ("Figure 6", "07_fig06_optimizer_qualification", "fig06_optimizer_qualification", "a--h"),
    ("Figure 7", "08_fig07_formal_training_v1", "fig07_formal_training_v1", "a--h"),
    ("Figure 8", "09_fig08_heterogeneous_retraining", "fig08_heterogeneous_retraining", "a--i"),
    ("Figure 9", "10_fig09_support_gap", "fig09_support_gap", "a--i"),
    ("Figure 10", "11_fig10_systematic_coverage", "fig10_systematic_coverage", "a--j"),
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return f"sha256:{digest.hexdigest()}"


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def supplementary_bundles() -> list[tuple[str, str, str, str]]:
    bundles = []
    for directory in sorted((SUITE / "12_supplementary").glob("S[0-9][0-9]_*")):
        pngs = sorted(directory.glob("figS*.png"))
        if len(pngs) != 1:
            raise RuntimeError(f"Expected one supplementary PNG in {directory}")
        base = pngs[0].stem
        number = directory.name[:3]
        panel_spec = (directory / "panel_spec.md").read_text(encoding="utf-8")
        panel_letters = sorted(set(re.findall(r"\(([a-z])\)", panel_spec.lower())))
        panels = f"{panel_letters[0]}--{panel_letters[-1]}" if len(panel_letters) > 1 else (panel_letters[0] if panel_letters else "see panel_spec.md")
        bundles.append((f"Supplementary Figure {number}", str(directory.relative_to(SUITE)), base, panels))
    if len(bundles) != 14:
        raise RuntimeError(f"Expected 14 supplementary bundles, found {len(bundles)}")
    return bundles


def bundle_inventory() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    inventory = []
    evidence_rows = []
    for label, relative_dir, base, panels in MAIN + supplementary_bundles():
        directory = SUITE / relative_dir
        required = [
            directory / f"{base}.svg",
            directory / f"{base}.pdf",
            directory / f"{base}.png",
            directory / "source_data.json",
            directory / "source_data.csv",
            directory / "caption.md",
            directory / "panel_spec.md",
            directory / "evidence_map.json",
            directory / "evidence_map.csv",
        ]
        missing = [str(p) for p in required if not p.is_file()]
        if missing:
            raise FileNotFoundError("; ".join(missing))
        scripts = list(directory.glob("*_plot.py"))
        if len(scripts) != 1:
            raise RuntimeError(f"Expected one plot wrapper in {directory}")
        png = directory / f"{base}.png"
        with Image.open(png) as image:
            dpi = image.info.get("dpi", (0, 0))
            dimensions = f"{image.width}×{image.height}"
        local_evidence = json.loads((directory / "evidence_map.json").read_text(encoding="utf-8"))
        evidence_rows.extend(local_evidence)
        inventory.append(
            {
                "figure": label,
                "panels": panels,
                "directory": str(directory.relative_to(ROOT)),
                "basename": base,
                "svg": str((directory / f"{base}.svg").relative_to(ROOT)),
                "pdf": str((directory / f"{base}.pdf").relative_to(ROOT)),
                "png": str(png.relative_to(ROOT)),
                "png_dimensions": dimensions,
                "png_dpi_x": round(float(dpi[0]), 3),
                "png_dpi_y": round(float(dpi[1]), 3),
                "evidence_rows": len(local_evidence),
                "source_data_json_sha256": sha256(directory / "source_data.json"),
                "status": "FROZEN_EVIDENCE_BUNDLE_COMPLETE",
            }
        )
    return inventory, evidence_rows


def write_master_index(inventory: list[dict[str, Any]]) -> None:
    lines = [
        "# Figure master index — CMAME publication suite v1",
        "",
        "All entries were generated from frozen public evidence or explanatory vector geometry. "
        "No project solver, model, optimizer, training, candidate-generation, rollout, or protected-data process was executed.",
        "",
        "| Figure | Panels | SVG | PDF | 600 dpi PNG | Evidence rows | Status |",
        "|---|---:|---|---|---|---:|---|",
    ]
    for row in inventory:
        suite_prefix = Path("publication_cmame_v1") / "04_figures"
        svg_link = Path(row["svg"]).relative_to(suite_prefix)
        pdf_link = Path(row["pdf"]).relative_to(suite_prefix)
        png_link = Path(row["png"]).relative_to(suite_prefix)
        lines.append(
            f"| {row['figure']} | {row['panels']} | [{row['basename']}.svg]({svg_link}) | "
            f"[{row['basename']}.pdf]({pdf_link}) | [{row['basename']}.png]({png_link}) | "
            f"{row['evidence_rows']} | {row['status']} |"
        )
    lines.extend(
        [
            "",
            "## Submission notes",
            "",
            "- SVG is the editable vector master; PDF is the submission vector alternative.",
            "- PNG is a 600 dpi review/export derivative at 190 mm figure width.",
            "- Quantitative source values are in each bundle's `source_data.json` and `source_data.csv`.",
            "- Every panel-to-source link is registered in `evidence_map.json` and the aggregate registry.",
            "- Claim boundaries and diagnostic-only transformations are audited separately.",
        ]
    )
    (SUITE / "figure_master_index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (SUITE / "figure_master_index.json").write_text(json.dumps(inventory, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_evidence_registry(evidence_rows: list[dict[str, Any]]) -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    (EVIDENCE_DIR / "figure_evidence_registry.json").write_text(
        json.dumps(evidence_rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    write_csv(EVIDENCE_DIR / "figure_evidence_registry.csv", evidence_rows)

    sources: dict[tuple[str, str], dict[str, Any]] = {}
    for row in evidence_rows:
        key = (row["source_file"], row["source_hash"])
        item = sources.setdefault(
            key,
            {
                "source_file": row["source_file"],
                "source_hash": row["source_hash"],
                "figures": set(),
                "panels": set(),
                "fields": set(),
                "evidence_classes": set(),
            },
        )
        item["figures"].add(row["figure"])
        item["panels"].add(f"{row['figure']}:{row['panel']}")
        item["fields"].add(row["source_field"])
        item["evidence_classes"].add(row["confirmatory_or_diagnostic"])
    manifest = []
    for item in sources.values():
        manifest.append(
            {
                "source_file": item["source_file"],
                "source_hash": item["source_hash"],
                "figures": sorted(item["figures"]),
                "panels": sorted(item["panels"]),
                "fields": sorted(item["fields"]),
                "evidence_classes": sorted(item["evidence_classes"]),
            }
        )
    manifest.sort(key=lambda row: row["source_file"])
    (EVIDENCE_DIR / "source_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv(
        EVIDENCE_DIR / "source_manifest.csv",
        [
            {
                "source_file": row["source_file"],
                "source_hash": row["source_hash"],
                "figures": ";".join(row["figures"]),
                "panels": ";".join(row["panels"]),
                "fields": ";".join(row["fields"]),
                "evidence_classes": ";".join(row["evidence_classes"]),
            }
            for row in manifest
        ],
    )


def write_claim_audit() -> None:
    source = "stage_08Z_Project_Closure_Publication/03_claim_matrix/final_claim_support_matrix.json"
    source_path = ROOT / source
    audit = [
        {"claim": "Conservative dynamic architecture verified in audited scope", "classification": "SUPPORTED", "figures": "GA; Fig1--3; Fig10"},
        {"claim": "Scale-aware discrete-defect target qualified", "classification": "SUPPORTED", "figures": "Fig4--6; Fig10"},
        {"claim": "Actual frozen optimizer update path qualified", "classification": "SUPPORTED", "figures": "Fig6; Fig10"},
        {"claim": "Two formal campaigns executed and failed their frozen TRAIN criteria", "classification": "SUPPORTED", "figures": "Fig7--8"},
        {"claim": "Held-out H2 support-gap attribution", "classification": "DIAGNOSTIC_ONLY", "figures": "Fig9; S12"},
        {"claim": "Transformer superiority", "classification": "PROHIBITED", "figures": "none"},
        {"claim": "Qualified trained solver", "classification": "PROHIBITED", "figures": "none"},
        {"claim": "Autonomous rollout improvement", "classification": "PROHIBITED", "figures": "none"},
        {"claim": "Protected-test performance", "classification": "PROHIBITED", "figures": "none"},
        {"claim": "Finite-resolution V2 qualification", "classification": "PROHIBITED", "figures": "none"},
        {"claim": "GCI qualification", "classification": "PROHIBITED", "figures": "none"},
        {"claim": "Correction target as physical truth", "classification": "PROHIBITED", "figures": "none"},
        {"claim": "All-coordinate finite-difference qualification", "classification": "PROHIBITED", "figures": "none"},
        {"claim": "Descriptor coverage proves target coverage", "classification": "PROHIBITED", "figures": "none"},
    ]
    payload = {"frozen_boundary_source": source, "source_hash": sha256(source_path), "audit": audit}
    (EVIDENCE_DIR / "claim_boundary_audit.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# Claim-boundary audit",
        "",
        f"Frozen source: `{source}`  ",
        f"SHA-256: `{payload['source_hash']}`",
        "",
        "| Claim | Classification | Figure handling |",
        "|---|---|---|",
    ]
    lines.extend(f"| {r['claim']} | **{r['classification']}** | {r['figures']} |" for r in audit)
    lines.extend(
        [
            "",
            "`DIAGNOSTIC_ONLY` panels are visually and textually separated from confirmatory qualification claims. "
            "`PROHIBITED` rows are exclusion checks: no positive version of those claims may appear in the suite.",
        ]
    )
    (EVIDENCE_DIR / "claim_boundary_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_transform_audit(evidence_rows: list[dict[str, Any]]) -> None:
    by_class: dict[str, int] = defaultdict(int)
    for row in evidence_rows:
        by_class[row["confirmatory_or_diagnostic"]] += 1
    payload = {
        "new_scientific_computation": False,
        "permitted_operations": [
            "direct plotting of frozen values",
            "log-axis display",
            "deterministic binning",
            "deterministic sorting and row placement",
            "flattening stored arrays in stored order",
            "declared algebraic display identities",
            "conceptual vector schematics traced to frozen contracts",
        ],
        "prohibited_operations": [
            "new model or solver execution",
            "new optimizer or training execution",
            "candidate regeneration or reselection",
            "new threshold, fit, inferential statistic, or scientific aggregate",
            "protected performance access",
        ],
        "evidence_class_counts": dict(sorted(by_class.items())),
    }
    (EVIDENCE_DIR / "display_transformation_audit.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def export_files(inventory: list[dict[str, Any]]) -> None:
    if EXPORT_DIR.exists():
        for child in EXPORT_DIR.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    main_dir = EXPORT_DIR / "main"
    supp_dir = EXPORT_DIR / "supplementary"
    main_dir.mkdir(parents=True, exist_ok=True)
    supp_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for index, item in enumerate(inventory):
        target_dir = main_dir if index < len(MAIN) else supp_dir
        for extension in ["svg", "pdf", "png"]:
            source = ROOT / item[extension]
            target = target_dir / source.name
            shutil.copy2(source, target)
            rows.append(
                {
                    "figure": item["figure"],
                    "format": extension.upper(),
                    "export_file": str(target.relative_to(ROOT)),
                    "bytes": target.stat().st_size,
                    "sha256": sha256(target),
                }
            )
    (EXPORT_DIR / "figure_files_manifest.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv(EXPORT_DIR / "figure_files_manifest.csv", rows)
    (EXPORT_DIR / "README.md").write_text(
        "# CMAME figure exports\n\n"
        "- `main/`: graphical abstract and Figures 1--10.\n"
        "- `supplementary/`: Supplementary Figures S1--S14.\n"
        "- SVG is the editable master, PDF is the vector submission alternative, and PNG is 600 dpi.\n"
        "- File hashes are recorded in `figure_files_manifest.json` and `.csv`.\n",
        encoding="utf-8",
    )


def main() -> None:
    inventory, evidence_rows = bundle_inventory()
    write_master_index(inventory)
    write_evidence_registry(evidence_rows)
    write_claim_audit()
    write_transform_audit(evidence_rows)
    export_files(inventory)


if __name__ == "__main__":
    main()
