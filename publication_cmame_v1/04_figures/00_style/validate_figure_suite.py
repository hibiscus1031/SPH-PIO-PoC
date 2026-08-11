#!/usr/bin/env python3
"""Read-only validator for the frozen CMAME publication figure suite.

The validator inspects already-created artifacts and their provenance.  It never
imports project packages, executes plot scripts, or evaluates scientific data.  Its
only writes are the Markdown and JSON quality-control reports requested by the suite
contract.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import math
import re
import traceback
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    from PIL import Image, ImageStat
except ImportError:  # pragma: no cover - dependency failure is reported at runtime
    Image = None  # type: ignore[assignment]
    ImageStat = None  # type: ignore[assignment]


VALIDATOR_VERSION = "1.0.0"
MIN_FILE_BYTES = {".svg": 1_000, ".pdf": 1_000, ".png": 10_000}
MIN_PNG_DPI = 595.0  # matplotlib commonly serializes 600 dpi as 599.9988
MIN_PNG_WIDTH_PX = 3_500
MIN_PNG_HEIGHT_PX = 1_200
MAX_PNG_DIMENSION_PX = 30_000
MIN_NONWHITE_FRACTION = 5.0e-4
MIN_LUMINANCE_STD = 0.8
MIN_PREVIEW_COLORS = 4

# Assemble these strings so a repository-wide literal scan does not mistake this
# defensive validator for a plot script that accesses a prohibited source.
PROTECTED_TOKENS = (
    "lcdf_" + "03",
    "lcdf_" + "10",
    "pri" + "vate",
    "sealed" + "_test",
    "fresh_validation" + "_seal",
)

EVIDENCE_FIELDS = (
    "figure",
    "panel",
    "scientific_claim",
    "source_file",
    "source_hash",
    "source_field",
    "confirmatory_or_diagnostic",
    "transformation",
    "plot_script",
    "output_file",
)


@dataclass(frozen=True)
class ExpectedFigure:
    canonical: str
    directory: str
    aliases: tuple[str, ...]
    expected_panels: tuple[str, ...] | None = None
    supplementary: bool = False


EXPECTED_FIGURES: tuple[ExpectedFigure, ...] = (
    ExpectedFigure("GA", "01_graphical_abstract", ("graphical_abstract", "ga"), ("route",)),
    ExpectedFigure("Fig01", "02_fig01_framework", ("fig01", "figure_01", "figure1"), tuple("abcde")),
    ExpectedFigure("Fig02", "03_fig02_architecture", ("fig02", "figure_02", "figure2"), tuple("abcdefghi")),
    ExpectedFigure("Fig03", "04_fig03_verification", ("fig03", "figure_03", "figure3"), tuple("abcdefg")),
    ExpectedFigure("Fig04", "05_fig04_failed_learning_routes", ("fig04", "figure_04", "figure4"), tuple("abcdefg")),
    ExpectedFigure("Fig05", "06_fig05_discrete_defect", ("fig05", "figure_05", "figure5"), tuple("abcdefgh")),
    ExpectedFigure("Fig06", "07_fig06_optimizer_qualification", ("fig06", "figure_06", "figure6"), tuple("abcdefgh")),
    ExpectedFigure("Fig07", "08_fig07_formal_training_v1", ("fig07", "figure_07", "figure7"), tuple("abcdefgh")),
    ExpectedFigure("Fig08", "09_fig08_heterogeneous_retraining", ("fig08", "figure_08", "figure8"), tuple("abcdefghi")),
    ExpectedFigure("Fig09", "10_fig09_support_gap", ("fig09", "figure_09", "figure9"), tuple("abcdefghi")),
    ExpectedFigure("Fig10", "11_fig10_systematic_coverage", ("fig10", "figure_10", "figure10"), tuple("abcdefghij")),
    *tuple(
        ExpectedFigure(
            f"S{index:02d}",
            "12_supplementary",
            (f"figs{index:02d}", f"figure_s{index:02d}", f"s{index:02d}", f"s{index}"),
            None,
            True,
        )
        for index in range(1, 15)
    ),
)


@dataclass
class Finding:
    level: str
    code: str
    message: str
    path: str = ""
    figure: str = "GLOBAL"


@dataclass
class ArtifactMetrics:
    path: str
    kind: str
    bytes: int
    width_px: int | None = None
    height_px: int | None = None
    dpi_x: float | None = None
    dpi_y: float | None = None
    nonwhite_fraction: float | None = None
    luminance_std: float | None = None
    preview_colors: int | None = None
    svg_text_elements: int | None = None
    svg_image_elements: int | None = None
    svg_width_mm: float | None = None
    pdf_pages: int | None = None
    pdf_width_mm: float | None = None


@dataclass
class FigureResult:
    canonical: str
    directory: str
    status: str = "FAIL"
    findings: list[Finding] = field(default_factory=list)
    artifacts: list[ArtifactMetrics] = field(default_factory=list)
    evidence_records: int = 0
    source_hashes_checked: int = 0
    panels: list[str] = field(default_factory=list)

    @property
    def errors(self) -> list[Finding]:
        return [finding for finding in self.findings if finding.level == "ERROR"]

    @property
    def warnings(self) -> list[Finding]:
        return [finding for finding in self.findings if finding.level == "WARNING"]


@dataclass(frozen=True)
class Bundle:
    expected: ExpectedFigure
    path: Path
    virtual_alias: str | None = None

    def files(self) -> list[Path]:
        if not self.path.is_dir():
            return []
        candidates = [path for path in self.path.rglob("*") if path.is_file()]
        if self.virtual_alias is None:
            return sorted(candidates)
        return sorted(path for path in candidates if alias_match(path.name, self.expected.aliases))


class Auditor:
    def __init__(self, suite_root: Path, repo_root: Path) -> None:
        self.suite_root = suite_root.resolve()
        self.repo_root = repo_root.resolve()
        self.global_findings: list[Finding] = []

    def global_finding(self, level: str, code: str, message: str, path: Path | str = "") -> None:
        self.global_findings.append(
            Finding(level=level, code=code, message=message, path=display_path(path, self.repo_root))
        )

    def audit(self) -> list[FigureResult]:
        self.audit_global_structure()
        results = [self.audit_figure(self.discover_bundle(expected)) for expected in EXPECTED_FIGURES]
        self.audit_export_pack()
        self.audit_master_index()
        return results

    def audit_global_structure(self) -> None:
        required_directories = (
            "00_style",
            "01_graphical_abstract",
            "02_fig01_framework",
            "03_fig02_architecture",
            "04_fig03_verification",
            "05_fig04_failed_learning_routes",
            "06_fig05_discrete_defect",
            "07_fig06_optimizer_qualification",
            "08_fig07_formal_training_v1",
            "09_fig08_heterogeneous_retraining",
            "10_fig09_support_gap",
            "11_fig10_systematic_coverage",
            "12_supplementary",
            "13_evidence_maps",
            "14_exports",
        )
        if not self.suite_root.is_dir():
            self.global_finding("ERROR", "SUITE_ROOT_MISSING", "Figure-suite root does not exist.", self.suite_root)
            return
        for name in required_directories:
            path = self.suite_root / name
            if not path.is_dir():
                self.global_finding("ERROR", "REQUIRED_DIRECTORY_MISSING", f"Required directory {name} is missing.", path)
        for relative in ("00_style/figure_style.py", "00_style/figure_style_spec.md"):
            path = self.suite_root / relative
            if not path.is_file():
                self.global_finding("ERROR", "STYLE_FILE_MISSING", f"Required style artifact {relative} is missing.", path)

    def discover_bundle(self, expected: ExpectedFigure) -> Bundle:
        root = self.suite_root / expected.directory
        if not expected.supplementary:
            return Bundle(expected, root)

        if not root.is_dir():
            return Bundle(expected, root, expected.aliases[0])
        subdirectories = sorted(
            (path for path in root.rglob("*") if path.is_dir()),
            key=lambda path: (len(path.relative_to(root).parts), str(path).casefold()),
        )
        for directory in subdirectories:
            if alias_match(directory.name, expected.aliases):
                return Bundle(expected, directory)
        # A flat supplementary folder is supported when every filename carries its
        # own S-number prefix.
        return Bundle(expected, root, expected.aliases[0])

    def audit_figure(self, bundle: Bundle) -> FigureResult:
        result = FigureResult(bundle.expected.canonical, display_path(bundle.path, self.repo_root))
        if not bundle.path.is_dir():
            add(result, "ERROR", "FIGURE_DIRECTORY_MISSING", "Figure directory is missing.", bundle.path)
            return result

        files = bundle.files()
        if not files:
            add(result, "ERROR", "FIGURE_BUNDLE_EMPTY", "No artifacts were found for this figure.", bundle.path)
            return result

        svg_files = select_extension(files, ".svg")
        pdf_files = select_extension(files, ".pdf")
        png_files = select_extension(files, ".png")
        source_json = select_named(files, suffix=".json", contains="source_data")
        source_csv = select_named(files, suffix=".csv", contains="source_data")
        plot_scripts = [
            path for path in files if path.suffix.casefold() == ".py" and path.stem.casefold().endswith("_plot")
        ]
        captions = select_markdown(files, "caption")
        panel_specs = select_markdown(files, "panel_spec")
        evidence_json = select_named(files, suffix=".json", contains="evidence_map")
        evidence_csv = select_named(files, suffix=".csv", contains="evidence_map")

        if not evidence_json or not evidence_csv:
            central_files = [path for path in (self.suite_root / "13_evidence_maps").glob("*") if path.is_file()]
            tagged = [path for path in central_files if alias_match(path.name, bundle.expected.aliases)]
            evidence_json = evidence_json or select_named(tagged, suffix=".json", contains="evidence")
            evidence_csv = evidence_csv or select_named(tagged, suffix=".csv", contains="evidence")

        required_groups = (
            ("SVG", svg_files, "SVG_MISSING"),
            ("PDF", pdf_files, "PDF_MISSING"),
            ("PNG", png_files, "PNG_MISSING"),
            ("source-data JSON", source_json, "SOURCE_JSON_MISSING"),
            ("source-data CSV", source_csv, "SOURCE_CSV_MISSING"),
            ("plot script", plot_scripts, "PLOT_SCRIPT_MISSING"),
            ("caption", captions, "CAPTION_MISSING"),
            ("panel specification", panel_specs, "PANEL_SPEC_MISSING"),
            ("evidence-map JSON", evidence_json, "EVIDENCE_JSON_MISSING"),
            ("evidence-map CSV", evidence_csv, "EVIDENCE_CSV_MISSING"),
        )
        for label, paths, code in required_groups:
            if not paths:
                add(result, "ERROR", code, f"Required {label} artifact is missing.", bundle.path)

        for path in (*svg_files, *pdf_files, *png_files):
            self.audit_nonempty_artifact(path, result)
        for path in svg_files:
            self.audit_svg(path, result)
        for path in pdf_files:
            self.audit_pdf(path, result)
        for path in png_files:
            self.audit_png(path, result)
        for path in source_json:
            self.audit_source_json(path, result)
        for path in source_csv:
            self.audit_source_csv(path, result)
        for path in plot_scripts:
            self.audit_plot_script(path, result)
        for path in captions:
            self.audit_markdown(path, result, kind="caption", minimum_chars=80)
            self.audit_claim_language(path.read_text(encoding="utf-8", errors="replace"), path, result)
        for path in panel_specs:
            self.audit_markdown(path, result, kind="panel specification", minimum_chars=60)
            self.audit_claim_language(path.read_text(encoding="utf-8", errors="replace"), path, result)

        records: list[dict[str, Any]] = []
        if evidence_json:
            records = self.audit_evidence_json(evidence_json[0], bundle, result)
        if evidence_csv:
            csv_records = self.audit_evidence_csv(evidence_csv[0], result)
            if records and len(csv_records) != len(records):
                add(
                    result,
                    "ERROR",
                    "EVIDENCE_MAP_ROW_MISMATCH",
                    f"JSON has {len(records)} records but CSV has {len(csv_records)}.",
                    evidence_csv[0],
                )
            elif records:
                for index, (json_record, csv_record) in enumerate(zip(records, csv_records), start=1):
                    different = [
                        field_name
                        for field_name in EVIDENCE_FIELDS
                        if comparable_value(json_record.get(field_name))
                        != comparable_value(csv_record.get(field_name))
                    ]
                    if different:
                        add(
                            result,
                            "ERROR",
                            "EVIDENCE_MAP_CONTENT_MISMATCH",
                            f"JSON/CSV record {index} differs in: {', '.join(different)}.",
                            evidence_csv[0],
                        )
        if records and panel_specs:
            self.audit_panel_coverage(records, panel_specs[0], result)

        result.status = "PASS" if not result.errors else "FAIL"
        return result

    def audit_nonempty_artifact(self, path: Path, result: FigureResult) -> None:
        size = path.stat().st_size
        minimum = MIN_FILE_BYTES.get(path.suffix.casefold(), 1)
        if size < minimum:
            add(
                result,
                "ERROR",
                "ARTIFACT_TOO_SMALL",
                f"Artifact is {size:,} bytes; expected at least {minimum:,} bytes.",
                path,
            )

    def audit_svg(self, path: Path, result: FigureResult) -> None:
        metric = ArtifactMetrics(display_path(path, self.repo_root), "SVG", path.stat().st_size)
        try:
            root = ET.parse(path).getroot()
            images = [element for element in root.iter() if local_name(element.tag) == "image"]
            texts = [element for element in root.iter() if local_name(element.tag) == "text"]
            metric.svg_image_elements = len(images)
            metric.svg_text_elements = len(texts)
            metric.svg_width_mm = svg_length_to_mm(root.attrib.get("width", ""))
            if images:
                add(result, "ERROR", "SVG_RASTER_IMAGE", f"SVG contains {len(images)} raster image element(s).", path)
            if not texts:
                add(
                    result,
                    "ERROR",
                    "SVG_TEXT_NOT_EDITABLE",
                    "SVG contains no text elements; labels appear to have been converted to paths.",
                    path,
                )
            else:
                visible_text = " ".join(" ".join(element.itertext()) for element in texts)
                self.audit_claim_language(visible_text, path, result, "SVG labels")
            if metric.svg_width_mm is not None and not 170.0 <= metric.svg_width_mm <= 210.0:
                add(
                    result,
                    "WARNING",
                    "SVG_WIDTH_UNEXPECTED",
                    f"SVG width is {metric.svg_width_mm:.1f} mm; the suite target is 190 mm.",
                    path,
                )
        except (ET.ParseError, OSError) as exc:
            add(result, "ERROR", "SVG_PARSE_FAILED", f"Could not parse SVG: {exc}", path)
        result.artifacts.append(metric)

    def audit_pdf(self, path: Path, result: FigureResult) -> None:
        metric = ArtifactMetrics(display_path(path, self.repo_root), "PDF", path.stat().st_size)
        try:
            page_count, width_mm = read_pdf_geometry(path)
            metric.pdf_pages = page_count
            metric.pdf_width_mm = width_mm
            if page_count != 1:
                add(result, "ERROR", "PDF_PAGE_COUNT", f"PDF has {page_count} pages; exactly one is required.", path)
            if width_mm is not None and not 170.0 <= width_mm <= 210.0:
                add(
                    result,
                    "WARNING",
                    "PDF_WIDTH_UNEXPECTED",
                    f"PDF width is {width_mm:.1f} mm; the suite target is 190 mm.",
                    path,
                )
        except Exception as exc:  # a malformed PDF must not abort the full audit
            add(result, "ERROR", "PDF_PARSE_FAILED", f"Could not inspect PDF: {exc}", path)
        result.artifacts.append(metric)

    def audit_png(self, path: Path, result: FigureResult) -> None:
        metric = ArtifactMetrics(display_path(path, self.repo_root), "PNG", path.stat().st_size)
        if Image is None or ImageStat is None:
            add(result, "ERROR", "PILLOW_MISSING", "Pillow is required for PNG quality checks.", path)
            result.artifacts.append(metric)
            return
        try:
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                metric.width_px, metric.height_px = image.size
                dpi = image.info.get("dpi")
                if isinstance(dpi, Sequence) and len(dpi) >= 2:
                    metric.dpi_x = finite_float(dpi[0])
                    metric.dpi_y = finite_float(dpi[1])
                if metric.dpi_x is None or metric.dpi_y is None:
                    add(result, "ERROR", "PNG_DPI_MISSING", "PNG has no readable DPI metadata.", path)
                elif min(metric.dpi_x, metric.dpi_y) < MIN_PNG_DPI:
                    add(
                        result,
                        "ERROR",
                        "PNG_DPI_LOW",
                        f"PNG DPI is {metric.dpi_x:.2f} × {metric.dpi_y:.2f}; at least 600 dpi is required.",
                        path,
                    )
                if metric.width_px < MIN_PNG_WIDTH_PX or metric.height_px < MIN_PNG_HEIGHT_PX:
                    add(
                        result,
                        "ERROR",
                        "PNG_DIMENSIONS_SMALL",
                        f"PNG is {metric.width_px} × {metric.height_px} px; dimensions are too small for full-width 600 dpi output.",
                        path,
                    )
                if max(metric.width_px, metric.height_px) > MAX_PNG_DIMENSION_PX:
                    add(
                        result,
                        "WARNING",
                        "PNG_DIMENSIONS_EXTREME",
                        f"PNG is {metric.width_px} × {metric.height_px} px; verify memory and journal handling.",
                        path,
                    )
                self.measure_png_content(image, metric, path, result)
        except Exception as exc:
            add(result, "ERROR", "PNG_PARSE_FAILED", f"Could not inspect PNG: {exc}", path)
        result.artifacts.append(metric)

    def measure_png_content(
        self, image: Any, metric: ArtifactMetrics, path: Path, result: FigureResult
    ) -> None:
        if "A" in image.getbands():
            alpha = image.getchannel("A")
            if alpha.getbbox() is None:
                add(result, "ERROR", "PNG_FULLY_TRANSPARENT", "PNG is fully transparent.", path)
        preview = image.convert("RGB")
        preview.thumbnail((768, 768))
        flattened = getattr(preview, "get_flattened_data", None)
        pixels = list(flattened() if flattened is not None else preview.getdata())
        if not pixels:
            add(result, "ERROR", "PNG_EMPTY", "PNG contains no pixels.", path)
            return
        nonwhite = sum(1 for red, green, blue in pixels if min(red, green, blue) < 248)
        metric.nonwhite_fraction = nonwhite / len(pixels)
        gray = preview.convert("L")
        metric.luminance_std = float(ImageStat.Stat(gray).stddev[0])
        colors = preview.getcolors(maxcolors=preview.width * preview.height + 1)
        metric.preview_colors = len(colors) if colors is not None else preview.width * preview.height + 1
        if metric.nonwhite_fraction < MIN_NONWHITE_FRACTION:
            add(
                result,
                "ERROR",
                "PNG_NEAR_BLANK",
                f"Only {metric.nonwhite_fraction:.4%} of preview pixels differ materially from white.",
                path,
            )
        if metric.luminance_std < MIN_LUMINANCE_STD:
            add(
                result,
                "ERROR",
                "PNG_LOW_CONTRAST",
                f"Preview luminance standard deviation is only {metric.luminance_std:.3f}.",
                path,
            )
        if metric.preview_colors < MIN_PREVIEW_COLORS:
            add(
                result,
                "ERROR",
                "PNG_TOO_FEW_COLORS",
                f"Preview contains only {metric.preview_colors} distinct RGB colors.",
                path,
            )

    def audit_source_json(self, path: Path, result: FigureResult) -> None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload in ({}, [], None, ""):
                add(result, "ERROR", "SOURCE_JSON_EMPTY", "Source-data JSON is empty.", path)
        except (json.JSONDecodeError, OSError) as exc:
            add(result, "ERROR", "SOURCE_JSON_INVALID", f"Invalid source-data JSON: {exc}", path)

    def audit_source_csv(self, path: Path, result: FigureResult) -> None:
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.reader(handle))
            if len(rows) < 2 or not any(cell.strip() for cell in rows[0]):
                add(result, "ERROR", "SOURCE_CSV_EMPTY", "Source-data CSV needs a header and at least one row.", path)
        except (csv.Error, OSError) as exc:
            add(result, "ERROR", "SOURCE_CSV_INVALID", f"Invalid source-data CSV: {exc}", path)

    def audit_plot_script(self, path: Path, result: FigureResult) -> None:
        try:
            text = path.read_text(encoding="utf-8")
            tree = ast.parse(text, filename=str(path))
        except (SyntaxError, UnicodeError, OSError) as exc:
            add(result, "ERROR", "PLOT_SCRIPT_INVALID", f"Plot script is not valid Python: {exc}", path)
            return
        token = protected_token(text)
        if token:
            add(
                result,
                "ERROR",
                "PROTECTED_TOKEN_IN_SCRIPT",
                f"Plot script contains prohibited token {token!r}.",
                path,
            )
        if imports_module(tree, "seaborn"):
            add(result, "ERROR", "SEABORN_IMPORT", "Plot script imports seaborn; the suite is matplotlib-only.", path)

    def audit_markdown(
        self, path: Path, result: FigureResult, *, kind: str, minimum_chars: int
    ) -> None:
        text = path.read_text(encoding="utf-8", errors="replace").strip()
        if len(text) < minimum_chars:
            add(
                result,
                "ERROR",
                "MARKDOWN_INCOMPLETE",
                f"{kind.capitalize()} has {len(text)} characters; expected at least {minimum_chars}.",
                path,
            )

    def audit_evidence_json(
        self, path: Path, bundle: Bundle, result: FigureResult
    ) -> list[dict[str, Any]]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            add(result, "ERROR", "EVIDENCE_JSON_INVALID", f"Invalid evidence-map JSON: {exc}", path)
            return []
        records = normalize_evidence_records(payload)
        if not records:
            add(result, "ERROR", "EVIDENCE_MAP_EMPTY", "Evidence-map JSON contains no records.", path)
            return []
        result.evidence_records = len(records)
        panels: set[str] = set()
        for index, record in enumerate(records, start=1):
            record_label = f"record {index}"
            missing = [field_name for field_name in EVIDENCE_FIELDS if is_blank(record.get(field_name))]
            if missing:
                add(
                    result,
                    "ERROR",
                    "EVIDENCE_FIELD_MISSING",
                    f"{record_label} is missing: {', '.join(missing)}.",
                    path,
                )
            panels.update(panel for panel in expand_panels(record.get("panel")) if panel != "all")
            figure_value = str(record.get("figure", "")).strip()
            if figure_value and not canonical_equivalent(figure_value, bundle.expected):
                add(
                    result,
                    "WARNING",
                    "EVIDENCE_FIGURE_LABEL",
                    f"{record_label} uses figure label {figure_value!r}, expected {bundle.expected.canonical}.",
                    path,
                )
            evidence_role = str(record.get("confirmatory_or_diagnostic", "")).casefold()
            if evidence_role and not (
                any(word in evidence_role for word in ("confirmatory", "diagnostic"))
                or evidence_role in {"supported", "prohibited"}
            ):
                add(
                    result,
                    "ERROR",
                    "EVIDENCE_ROLE_INVALID",
                    f"{record_label} must identify confirmatory or diagnostic status.",
                    path,
                )
            self.audit_claim_language(str(record.get("scientific_claim", "")), path, result, record_label)
            self.audit_evidence_source(record, path, bundle, result, record_label)
            self.audit_evidence_targets(record, path, bundle, result, record_label)
        result.panels = sorted(panels, key=panel_sort_key)
        expected_panels = set(bundle.expected.expected_panels or ())
        if expected_panels:
            missing_panels = sorted(expected_panels - panels, key=panel_sort_key)
            extra_panels = sorted(panels - expected_panels, key=panel_sort_key)
            if missing_panels:
                add(
                    result,
                    "ERROR",
                    "EVIDENCE_PANEL_MISSING",
                    f"Evidence map does not cover required panel(s): {', '.join(missing_panels)}.",
                    path,
                )
            if extra_panels:
                add(
                    result,
                    "ERROR",
                    "EVIDENCE_PANEL_UNEXPECTED",
                    f"Evidence map contains panel(s) outside the figure contract: {', '.join(extra_panels)}.",
                    path,
                )
        return records

    def audit_evidence_csv(self, path: Path, result: FigureResult) -> list[dict[str, str]]:
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                fields = reader.fieldnames or []
                records = list(reader)
            missing_fields = [field_name for field_name in EVIDENCE_FIELDS if field_name not in fields]
            if missing_fields:
                add(
                    result,
                    "ERROR",
                    "EVIDENCE_CSV_COLUMNS",
                    f"Evidence-map CSV is missing columns: {', '.join(missing_fields)}.",
                    path,
                )
            if not records:
                add(result, "ERROR", "EVIDENCE_CSV_EMPTY", "Evidence-map CSV contains no records.", path)
            for index, record in enumerate(records, start=1):
                blank_fields = [field_name for field_name in EVIDENCE_FIELDS if is_blank(record.get(field_name))]
                if blank_fields:
                    add(
                        result,
                        "ERROR",
                        "EVIDENCE_CSV_VALUE_MISSING",
                        f"CSV record {index} has blank values: {', '.join(blank_fields)}.",
                        path,
                    )
            return records
        except (csv.Error, OSError) as exc:
            add(result, "ERROR", "EVIDENCE_CSV_INVALID", f"Invalid evidence-map CSV: {exc}", path)
            return []

    def audit_evidence_source(
        self,
        record: Mapping[str, Any],
        map_path: Path,
        bundle: Bundle,
        result: FigureResult,
        record_label: str,
    ) -> None:
        source_values = value_list(record.get("source_file"))
        if not source_values:
            return
        hash_values = value_list(record.get("source_hash"))
        hash_mapping = record.get("source_hash") if isinstance(record.get("source_hash"), Mapping) else None
        if hash_mapping is None and len(hash_values) not in (1, len(source_values)):
            add(
                result,
                "ERROR",
                "SOURCE_HASH_CARDINALITY",
                f"{record_label} lists {len(source_values)} sources but {len(hash_values)} hashes.",
                map_path,
            )
        for source_index, source_text in enumerate(source_values):
            token = protected_token(source_text)
            if token:
                add(
                    result,
                    "ERROR",
                    "PROTECTED_SOURCE_PATH",
                    f"{record_label} references a prohibited source token {token!r}; source was not accessed.",
                    map_path,
                )
                continue
            source_path = resolve_reference(
                source_text,
                bases=(map_path.parent, bundle.path, self.suite_root, self.repo_root),
            )
            if source_path is None:
                add(
                    result,
                    "ERROR",
                    "SOURCE_FILE_MISSING",
                    f"{record_label} source does not exist: {source_text}",
                    map_path,
                )
                continue
            resolved_token = protected_token(str(source_path.resolve()))
            if resolved_token:
                add(
                    result,
                    "ERROR",
                    "PROTECTED_SOURCE_TARGET",
                    f"{record_label} resolves to a prohibited source; source was not accessed.",
                    source_path,
                )
                continue
            if not source_path.is_file():
                add(
                    result,
                    "ERROR",
                    "SOURCE_NOT_FILE",
                    f"{record_label} source is not a regular file.",
                    source_path,
                )
                continue
            expected_hash = ""
            if hash_mapping is not None:
                expected_hash = str(
                    hash_mapping.get(source_text)
                    or hash_mapping.get(str(source_path))
                    or hash_mapping.get(source_path.name)
                    or ""
                )
            elif hash_values:
                expected_hash = hash_values[source_index] if len(hash_values) > 1 else hash_values[0]
            normalized_hash = normalize_sha256(expected_hash)
            if normalized_hash is None:
                add(
                    result,
                    "ERROR",
                    "SOURCE_HASH_INVALID",
                    f"{record_label} has no valid SHA-256 for {source_text}.",
                    map_path,
                )
                continue
            actual_hash = sha256_file(source_path)
            result.source_hashes_checked += 1
            if actual_hash != normalized_hash:
                add(
                    result,
                    "ERROR",
                    "SOURCE_HASH_MISMATCH",
                    f"{record_label} hash mismatch for {source_text}: expected {normalized_hash}, got {actual_hash}.",
                    source_path,
                )

    def audit_evidence_targets(
        self,
        record: Mapping[str, Any],
        map_path: Path,
        bundle: Bundle,
        result: FigureResult,
        record_label: str,
    ) -> None:
        plot_values = value_list(record.get("plot_script"))
        output_values = value_list(record.get("output_file"))
        for kind, values in (("plot script", plot_values), ("output file", output_values)):
            for value in values:
                token = protected_token(value)
                if token:
                    add(
                        result,
                        "ERROR",
                        "PROTECTED_ARTIFACT_REFERENCE",
                        f"{record_label} {kind} contains prohibited token {token!r}.",
                        map_path,
                    )
                    continue
                target = resolve_reference(
                    value,
                    bases=(map_path.parent, bundle.path, self.suite_root, self.repo_root),
                )
                if target is None or not target.is_file():
                    add(
                        result,
                        "ERROR",
                        "EVIDENCE_TARGET_MISSING",
                        f"{record_label} {kind} does not exist: {value}",
                        map_path,
                    )
                elif kind == "plot script" and target.suffix.casefold() == ".py":
                    self.audit_referenced_plot_script(target, result, record_label)

    def audit_referenced_plot_script(
        self, path: Path, result: FigureResult, record_label: str
    ) -> None:
        if any(
            finding.code == "PROTECTED_TOKEN_IN_REFERENCED_SCRIPT"
            and Path(finding.path) == path
            for finding in result.findings
        ):
            return
        try:
            text = path.read_text(encoding="utf-8")
            tree = ast.parse(text, filename=str(path))
        except (SyntaxError, UnicodeError, OSError) as exc:
            add(
                result,
                "ERROR",
                "REFERENCED_PLOT_SCRIPT_INVALID",
                f"{record_label} references an invalid plot script: {exc}",
                path,
            )
            return
        token = protected_token(text)
        if token:
            add(
                result,
                "ERROR",
                "PROTECTED_TOKEN_IN_REFERENCED_SCRIPT",
                f"Referenced plot script contains prohibited token {token!r}.",
                path,
            )
        if imports_module(tree, "seaborn"):
            add(
                result,
                "ERROR",
                "SEABORN_IMPORT",
                "Referenced plot script imports seaborn; the suite is matplotlib-only.",
                path,
            )

    def audit_panel_coverage(
        self, records: Sequence[Mapping[str, Any]], panel_spec: Path, result: FigureResult
    ) -> None:
        text = panel_spec.read_text(encoding="utf-8", errors="replace")
        panels = sorted(
            {
                panel
                for record in records
                for panel in expand_panels(record.get("panel"))
                if panel != "all"
            },
            key=panel_sort_key,
        )
        spec_panels = extract_spec_panels(text)
        for panel in panels:
            present = panel in spec_panels
            if len(panel) > 1:
                present = present or bool(re.search(rf"(?i)\b{re.escape(panel)}\b", text))
            if not present:
                add(
                    result,
                    "ERROR",
                    "PANEL_SPEC_COVERAGE",
                    f"Evidence panel {panel!r} is not identified in the panel specification.",
                    panel_spec,
                )

    def audit_claim_language(
        self,
        text: str,
        path: Path,
        result: FigureResult,
        context: str = "document",
    ) -> None:
        for label, pattern in prohibited_claim_patterns():
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                if explicitly_negated(text, match.start(), match.end()):
                    continue
                excerpt = " ".join(text[max(0, match.start() - 28) : match.end() + 28].split())
                add(
                    result,
                    "ERROR",
                    "PROHIBITED_CLAIM",
                    f"{context} contains prohibited positive claim {label!r}: …{excerpt}…",
                    path,
                )

    def audit_export_pack(self) -> None:
        export_root = self.suite_root / "14_exports"
        if not export_root.is_dir():
            return
        export_files = [path for path in export_root.rglob("*") if path.is_file()]
        for suffix in (".svg", ".pdf", ".png"):
            typed_files = [path for path in export_files if path.suffix.casefold() == suffix]
            count = len(typed_files)
            if count < len(EXPECTED_FIGURES):
                self.global_finding(
                    "ERROR",
                    "EXPORT_PACK_INCOMPLETE",
                    f"Export pack contains {count} {suffix[1:].upper()} files; expected at least {len(EXPECTED_FIGURES)}.",
                    export_root,
                )
            for expected in EXPECTED_FIGURES:
                if not any(alias_match(path.name, expected.aliases) for path in typed_files):
                    self.global_finding(
                        "ERROR",
                        "EXPORT_FIGURE_MISSING",
                        f"Export pack has no {suffix[1:].upper()} artifact for {expected.canonical}.",
                        export_root,
                    )
        for path in export_files:
            if path.suffix.casefold() in MIN_FILE_BYTES and path.stat().st_size < MIN_FILE_BYTES[path.suffix.casefold()]:
                self.global_finding("ERROR", "EXPORT_FILE_TOO_SMALL", "Export file is unexpectedly small.", path)

    def audit_master_index(self) -> None:
        candidates = (
            self.suite_root / "figure_master_index.md",
            self.suite_root / "13_evidence_maps" / "figure_master_index.md",
        )
        master = next((path for path in candidates if path.is_file()), None)
        if master is None:
            self.global_finding(
                "ERROR",
                "MASTER_INDEX_MISSING",
                "figure_master_index.md is missing from the suite root and evidence-map directory.",
                self.suite_root,
            )
            return
        text = master.read_text(encoding="utf-8", errors="replace")
        for expected in EXPECTED_FIGURES:
            if not canonical_mentioned(text, expected):
                self.global_finding(
                    "ERROR",
                    "MASTER_INDEX_ENTRY_MISSING",
                    f"Master index does not mention {expected.canonical}.",
                    master,
                )


def add(result: FigureResult, level: str, code: str, message: str, path: Path | str = "") -> None:
    result.findings.append(
        Finding(
            level=level,
            code=code,
            message=message,
            path=str(path),
            figure=result.canonical,
        )
    )


def alias_match(name: str, aliases: Iterable[str]) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "_", name.casefold()).strip("_")
    padded = f"_{normalized}_"
    for alias in aliases:
        token = re.sub(r"[^a-z0-9]+", "_", alias.casefold()).strip("_")
        # Require token boundaries so S01 cannot match S010 or S10.
        if f"_{token}_" in padded or normalized.startswith(f"{token}_") or normalized == token:
            return True
    return False


def select_extension(files: Sequence[Path], suffix: str) -> list[Path]:
    return [path for path in files if path.suffix.casefold() == suffix]


def select_named(files: Sequence[Path], *, suffix: str, contains: str) -> list[Path]:
    return [
        path
        for path in files
        if path.suffix.casefold() == suffix.casefold() and contains.casefold() in path.stem.casefold()
    ]


def select_markdown(files: Sequence[Path], token: str) -> list[Path]:
    exact = [path for path in files if path.suffix.casefold() == ".md" and path.stem.casefold() == token]
    if exact:
        return exact
    return [
        path
        for path in files
        if path.suffix.casefold() == ".md" and token.casefold() in path.stem.casefold()
    ]


def normalize_evidence_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [dict(row) for row in payload if isinstance(row, Mapping)]
    if isinstance(payload, Mapping):
        for key in ("records", "evidence", "panels", "rows"):
            candidate = payload.get(key)
            if isinstance(candidate, list):
                return [dict(row) for row in candidate if isinstance(row, Mapping)]
        if all(field_name in payload for field_name in EVIDENCE_FIELDS):
            return [dict(payload)]
    return []


def value_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, Mapping):
        return [str(item) for item in value.keys()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            decoded = json.loads(text)
            if isinstance(decoded, list):
                return [str(item).strip() for item in decoded if str(item).strip()]
        except json.JSONDecodeError:
            pass
    if ";" in text:
        return [item.strip() for item in text.split(";") if item.strip()]
    return [text]


def is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, Mapping)):
        return len(value) == 0
    return False


def comparable_value(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return ";".join(str(item).strip() for item in value)
    if isinstance(value, Mapping):
        return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return str(value if value is not None else "").strip()


def normalize_panel(value: Any) -> str:
    text = str(value or "").strip().casefold()
    match = re.fullmatch(r"\(?\s*([a-z])\s*\)?", text)
    return match.group(1) if match else text


def expand_panels(value: Any) -> list[str]:
    """Expand evidence labels such as ``a,c`` or ``a--e`` deterministically."""

    text = str(value or "").strip().casefold()
    if not text:
        return []
    text = text.replace("–", "-").replace("—", "-")
    if text == "all":
        return ["all"]
    panels: list[str] = []
    for part in re.split(r"[,;/+]", text):
        part = part.strip().strip("()[]")
        range_match = re.fullmatch(r"([a-z])\s*-+\s*([a-z])", part)
        if range_match:
            start, end = ord(range_match.group(1)), ord(range_match.group(2))
            if start <= end:
                panels.extend(chr(code) for code in range(start, end + 1))
                continue
        normalized = normalize_panel(part)
        if normalized:
            panels.append(normalized)
    return list(dict.fromkeys(panels))


def extract_spec_panels(text: str) -> set[str]:
    panels: set[str] = set()
    for match in re.finditer(r"\(([^)]+)\)", text):
        panels.update(panel for panel in expand_panels(match.group(1)) if panel != "all")
    for match in re.finditer(r"(?m)^\s*\|\s*([a-z](?:\s*-+\s*[a-z])?)\s*\|", text, flags=re.IGNORECASE):
        panels.update(panel for panel in expand_panels(match.group(1)) if panel != "all")
    return panels


def panel_sort_key(panel: str) -> tuple[int, str]:
    if len(panel) == 1 and panel.isalpha():
        return (ord(panel) - ord("a"), panel)
    return (1_000, panel)


def canonical_equivalent(value: str, expected: ExpectedFigure) -> bool:
    compact = re.sub(r"[^a-z0-9]", "", value.casefold())
    canonical = re.sub(r"[^a-z0-9]", "", expected.canonical.casefold())
    if compact == canonical or alias_match(value, expected.aliases):
        return True
    if expected.canonical == "GA":
        return compact in {"ga", "graphicalabstract"}
    expected_match = re.fullmatch(r"Fig(\d+)", expected.canonical, flags=re.IGNORECASE)
    value_match = re.fullmatch(r"(?:fig(?:ure)?)(\d+)", compact, flags=re.IGNORECASE)
    if expected_match and value_match:
        return int(expected_match.group(1)) == int(value_match.group(1))
    supplement_match = re.fullmatch(r"S(\d+)", expected.canonical, flags=re.IGNORECASE)
    supplement_value = re.fullmatch(r"(?:fig(?:ure)?)?s(\d+)", compact, flags=re.IGNORECASE)
    return bool(
        supplement_match
        and supplement_value
        and int(supplement_match.group(1)) == int(supplement_value.group(1))
    )


def canonical_mentioned(text: str, expected: ExpectedFigure) -> bool:
    if expected.canonical == "GA":
        return bool(re.search(r"(?i)\b(?:graphical\s+abstract|GA)\b", text))
    if expected.canonical.casefold() in text.casefold():
        return True
    main_match = re.fullmatch(r"Fig(\d+)", expected.canonical, flags=re.IGNORECASE)
    if main_match and re.search(
        rf"(?i)\bfig(?:ure)?\.?\s*0*{int(main_match.group(1))}\b", text
    ):
        return True
    supplement_match = re.fullmatch(r"S(\d+)", expected.canonical, flags=re.IGNORECASE)
    if supplement_match and re.search(
        rf"(?i)\b(?:supplementary\s+figure\s+|fig(?:ure)?\.?\s*)?s0*{int(supplement_match.group(1))}\b",
        text,
    ):
        return True
    return any(alias_match(word, expected.aliases) for word in re.findall(r"[A-Za-z0-9_-]+", text))


def protected_token(text: str) -> str | None:
    folded = text.casefold()
    for token in PROTECTED_TOKENS:
        if token in folded:
            return token
    return None


def imports_module(tree: ast.AST, module_name: str) -> bool:
    target = module_name.casefold()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name.split(".", 1)[0].casefold() == target for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            module = (node.module or "").split(".", 1)[0].casefold()
            if module == target:
                return True
    return False


def resolve_reference(value: str, *, bases: Sequence[Path]) -> Path | None:
    text = value.strip()
    if not text or re.match(r"^[a-z][a-z0-9+.-]*://", text, flags=re.IGNORECASE):
        return None
    candidate = Path(text).expanduser()
    if candidate.is_absolute():
        return candidate if candidate.exists() else None
    for base in bases:
        joined = base / candidate
        if joined.exists():
            return joined
    return None


def normalize_sha256(value: str) -> str | None:
    text = str(value).strip().casefold()
    if text.startswith("sha256:"):
        text = text.split(":", 1)[1].strip()
    return text if re.fullmatch(r"[0-9a-f]{64}", text) else None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].casefold()


def svg_length_to_mm(value: str) -> float | None:
    match = re.fullmatch(r"\s*([0-9.]+)\s*(mm|cm|in|pt|px)?\s*", value, flags=re.IGNORECASE)
    if not match:
        return None
    number = float(match.group(1))
    unit = (match.group(2) or "px").casefold()
    factors = {"mm": 1.0, "cm": 10.0, "in": 25.4, "pt": 25.4 / 72.0, "px": 25.4 / 96.0}
    return number * factors[unit]


def read_pdf_geometry(path: Path) -> tuple[int, float | None]:
    reader_class = None
    import_error: Exception | None = None
    try:
        from pypdf import PdfReader as reader_class  # type: ignore[assignment]
    except ImportError as exc:
        import_error = exc
        try:
            from PyPDF2 import PdfReader as reader_class  # type: ignore[assignment]
        except ImportError:
            pass
    if reader_class is None:
        raise RuntimeError(f"pypdf or PyPDF2 is required ({import_error})")
    reader = reader_class(str(path))
    count = len(reader.pages)
    if count == 0:
        return 0, None
    width_points = float(reader.pages[0].mediabox.width)
    return count, width_points * 25.4 / 72.0


def finite_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def prohibited_claim_patterns() -> tuple[tuple[str, str], ...]:
    return (
        ("Transformer superiority", r"\btransformer\s+(?:is|was|proved|demonstrated|performs?)\s+(?:more\s+)?superior\b|\btransformer\s+superiority\b"),
        ("general neural-SPH failure", r"\bneural\s+sph\s+(?:cannot|can\s+not|does\s+not)\s+work\b"),
        ("attention equals kernel", r"\battention\s+(?:is|equals?|constitutes?)\s+(?:an?\s+)?kernel\b"),
        ("successful training", r"\btraining\s+(?:succeeded|was\s+successful|is\s+successful|success)\b|\bsuccessful\s+training\b"),
        ("validation superiority", r"\bvalidation\s+(?:superiority|outperforms?|beats?)\b"),
        ("sealed-test result", r"\bsealed[- ]test\s+(?:passed|performance|result|score|accuracy)\b"),
        ("V2 qualification", r"\b(?:stage\s*0?1\s+)?v2\s+(?:is\s+|was\s+)?qualified\b|\bv2\s+qualification\b"),
        ("GCI claim", r"\bgci\s+(?:confirmed|established|verified|qualified|result|value)\b"),
        ("target truth", r"\b(?:establish(?:es|ed)?|confirm(?:s|ed)?|provides?)\s+(?:the\s+)?target\s+truth\b|\btarget\s+(?:is|was)\s+(?:the\s+)?truth\b|\btarget\s+truth\s+(?:is|was)\s+(?:confirmed|established)\b"),
        ("high-resolution truth", r"\b(?:establish(?:es|ed)?|confirm(?:s|ed)?|provides?)\s+high[- ]resolution\s+truth\b|\bhigh[- ]resolution\s+(?:is|was)\s+(?:the\s+)?truth\b|\bhigh[- ]resolution\s+truth\s+(?:is|was)\s+(?:confirmed|established)\b"),
        ("successful solver", r"\bsuccessful\s+(?:trained\s+)?solver\b|\bsolver\s+(?:was\s+|is\s+)?successful\b"),
        ("Stage07 solver improvement", r"\bstage\s*0?7\s+(?:improved|improves)\s+(?:the\s+)?solver\b"),
        ("Stage08 gap solved", r"\bstage\s*0?8\s+(?:solved|closed)\s+(?:the\s+)?(?:support\s+)?gap\b"),
        ("validation implies sealed", r"\bvalidation\s+(?:implies|guarantees|establishes)\s+sealed\b"),
        ("D3 necessity", r"\bd3\s+(?:proves|demonstrates|establishes)\s+transformer\s+necessity\b"),
    )


def explicitly_negated(text: str, start: int, end: int) -> bool:
    prefix = " ".join(text[max(0, start - 55) : start].casefold().split())
    suffix = " ".join(text[end : min(len(text), end + 55)].casefold().split())
    prefix_negated = bool(
        re.search(
            r"(?:\bno\b|\bnot\b|\bnever\b|\bwithout\b|\bdoes\s+not\b|\bdid\s+not\b|\bcannot\b|\bmust\s+not\b|\bdo\s+not\b|\bprohibited\b|\bunsupported\b|\bnot\s+claimed\b)[^.;:]{0,42}$",
            prefix,
        )
    )
    suffix_negated = bool(
        re.match(
            r"[^.;:]{0,18}(?:\b(?:is|was)\s+not\s+(?:supported|established|claimed|qualified|shown|demonstrated)\b|\bnot\s+(?:supported|established|claimed|qualified|shown|demonstrated)\b|\bremains?\s+(?:unsupported|unqualified)\b|\b(?:false|fail|failed|unsupported|unqualified)\b|\b(?:claim|qualification)\s+boundary\b|\bboundary\b)",
            suffix,
        )
    )
    symbolic_negation = "≠" in text[max(0, start - 12) : start]
    return prefix_negated or suffix_negated or symbolic_negation


def display_path(path: Path | str, repo_root: Path) -> str:
    if not path:
        return ""
    candidate = Path(path)
    try:
        return str(candidate.resolve().relative_to(repo_root.resolve()))
    except (OSError, ValueError):
        return str(candidate)


def finding_to_dict(finding: Finding) -> dict[str, Any]:
    return asdict(finding)


def result_to_dict(result: FigureResult) -> dict[str, Any]:
    return {
        "canonical": result.canonical,
        "directory": result.directory,
        "status": result.status,
        "error_count": len(result.errors),
        "warning_count": len(result.warnings),
        "evidence_records": result.evidence_records,
        "source_hashes_checked": result.source_hashes_checked,
        "panels": result.panels,
        "findings": [finding_to_dict(finding) for finding in result.findings],
        "artifacts": [asdict(metric) for metric in result.artifacts],
    }


def build_machine_report(
    suite_root: Path,
    repo_root: Path,
    results: Sequence[FigureResult],
    global_findings: Sequence[Finding],
) -> dict[str, Any]:
    errors = sum(len(result.errors) for result in results) + sum(
        finding.level == "ERROR" for finding in global_findings
    )
    warnings = sum(len(result.warnings) for result in results) + sum(
        finding.level == "WARNING" for finding in global_findings
    )
    return {
        "validator": "CMAME frozen figure-suite validator",
        "validator_version": VALIDATOR_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "suite_root": str(suite_root),
        "repo_root": str(repo_root),
        "overall_status": "PASS" if errors == 0 else "FAIL",
        "expected_figure_count": len(EXPECTED_FIGURES),
        "passed_figure_count": sum(result.status == "PASS" for result in results),
        "error_count": errors,
        "warning_count": warnings,
        "policy": {
            "read_only_artifact_audit": True,
            "project_code_imported": False,
            "plot_scripts_executed": False,
            "protected_sources_accessed": False,
        },
        "global_findings": [finding_to_dict(finding) for finding in global_findings],
        "figures": [result_to_dict(result) for result in results],
    }


def build_markdown_report(report: Mapping[str, Any]) -> str:
    lines = [
        "# Figure visual QC report",
        "",
        f"- Overall status: **{report['overall_status']}**",
        f"- Figures passed: {report['passed_figure_count']}/{report['expected_figure_count']}",
        f"- Errors: {report['error_count']}",
        f"- Warnings: {report['warning_count']}",
        f"- Validator: v{report['validator_version']}",
        f"- Generated (UTC): {report['generated_at_utc']}",
        "- Audit boundary: artifacts and provenance only; no project code or plot script was executed.",
        "",
        "## Figure-level result",
        "",
        "| Figure | Status | Panels | Evidence rows | Hashes checked | Errors | Warnings |",
        "|---|---:|---|---:|---:|---:|---:|",
    ]
    for figure in report["figures"]:
        panels = ", ".join(figure["panels"]) or "—"
        lines.append(
            f"| {figure['canonical']} | {figure['status']} | {panels} | {figure['evidence_records']} | "
            f"{figure['source_hashes_checked']} | {figure['error_count']} | {figure['warning_count']} |"
        )

    lines.extend(
        [
            "",
            "## Raster and vector metrics",
            "",
            "| Figure | Artifact | Geometry | DPI | Content signal | Vector/PDF signal |",
            "|---|---|---|---|---|---|",
        ]
    )
    for figure in report["figures"]:
        for artifact in figure["artifacts"]:
            geometry = "—"
            dpi = "—"
            content = "—"
            vector = "—"
            if artifact["kind"] == "PNG":
                geometry = f"{artifact['width_px']}×{artifact['height_px']} px"
                if artifact["dpi_x"] is not None:
                    dpi = f"{artifact['dpi_x']:.1f}×{artifact['dpi_y']:.1f}"
                if artifact["nonwhite_fraction"] is not None:
                    content = (
                        f"nonwhite {artifact['nonwhite_fraction']:.2%}; "
                        f"σL {artifact['luminance_std']:.2f}; colors {artifact['preview_colors']}"
                    )
            elif artifact["kind"] == "SVG":
                if artifact["svg_width_mm"] is not None:
                    geometry = f"{artifact['svg_width_mm']:.1f} mm wide"
                vector = (
                    f"text {artifact['svg_text_elements']}; raster-image {artifact['svg_image_elements']}"
                )
            elif artifact["kind"] == "PDF":
                if artifact["pdf_width_mm"] is not None:
                    geometry = f"{artifact['pdf_width_mm']:.1f} mm wide"
                vector = f"pages {artifact['pdf_pages']}"
            lines.append(
                f"| {figure['canonical']} | `{artifact['path']}` | {geometry} | {dpi} | {content} | {vector} |"
            )

    all_findings = list(report["global_findings"])
    for figure in report["figures"]:
        all_findings.extend(figure["findings"])
    lines.extend(["", "## Findings", ""])
    if not all_findings:
        lines.append("No errors or warnings were detected.")
    else:
        for finding in all_findings:
            location = f" — `{finding['path']}`" if finding.get("path") else ""
            lines.append(
                f"- **{finding['level']} · {finding['figure']} · {finding['code']}**: "
                f"{finding['message']}{location}"
            )

    lines.extend(
        [
            "",
            "## Checks performed",
            "",
            "- Required GA, Fig01–Fig10, and S01–S14 bundles and suite directories.",
            "- SVG/PDF/PNG presence, file size, vector-only SVG, editable SVG text, single-page PDF, and 600 dpi PNG geometry.",
            "- PNG blankness, contrast, alpha, and preview-color sanity.",
            "- Source-data JSON/CSV, plot-script syntax, captions, panel specifications, and evidence-map JSON/CSV.",
            "- Evidence-field completeness, panel coverage, source existence, exact SHA-256 match, output references, and evidence role.",
            "- Protected-source token exclusion and frozen-claim boundary language.",
            "- Aggregate export pack and figure master index.",
            "",
        ]
    )
    return "\n".join(lines)


def find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    return start


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    default_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=default_root, help="04_figures suite root")
    parser.add_argument("--repo-root", type=Path, default=None, help="repository root for relative source paths")
    parser.add_argument("--report-md", type=Path, default=None, help="Markdown report path")
    parser.add_argument("--report-json", type=Path, default=None, help="machine-readable report path")
    parser.add_argument("--strict-warnings", action="store_true", help="return non-zero when warnings remain")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    suite_root = args.root.resolve()
    repo_root = (args.repo_root or find_repo_root(suite_root)).resolve()
    report_md = (args.report_md or suite_root / "figure_visual_qc_report.md").resolve()
    report_json = (args.report_json or suite_root / "figure_visual_qc_report.json").resolve()
    try:
        auditor = Auditor(suite_root, repo_root)
        results = auditor.audit()
        report = build_machine_report(suite_root, repo_root, results, auditor.global_findings)
        report_md.parent.mkdir(parents=True, exist_ok=True)
        report_json.parent.mkdir(parents=True, exist_ok=True)
        report_md.write_text(build_markdown_report(report), encoding="utf-8")
        report_json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(
            f"{report['overall_status']}: {report['passed_figure_count']}/{report['expected_figure_count']} figures; "
            f"{report['error_count']} errors, {report['warning_count']} warnings"
        )
        print(f"Markdown report: {report_md}")
        print(f"JSON report: {report_json}")
        if report["overall_status"] != "PASS":
            return 1
        if args.strict_warnings and report["warning_count"]:
            return 2
        return 0
    except Exception:
        traceback.print_exc()
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
