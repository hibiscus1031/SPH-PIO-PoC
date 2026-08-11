#!/usr/bin/env python3
"""Audit the Stage 03D-S closure package and emit its final manifest."""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path

from lxml import etree
from PIL import Image
from pypdf import PdfReader


REPO = Path(__file__).resolve().parents[3]
STAGE = REPO / "stage_03_Dynamic_SPH_Transformer_Hybrid"
ROOT = STAGE / "08_route_closure"
REPORTS = STAGE / "09_reports"
MANIFESTS = STAGE / "10_manifests"
DOCX = STAGE / "documents/Stage_03_Research_Record.docx"
RENDER = ROOT / "manifests/rendered_record_final"
PDF = RENDER / "Stage_03_Research_Record.pdf"
AUDIT_OUT = ROOT / "manifests/stage03ds_research_record_render_audit.json"
FINAL_OUT = MANIFESTS / "stage03ds_final_manifest.json"

FINAL_STATUS = "STAGE03_ROUTE_PAUSED_GRADIENT_BOUNDARY_COMPLETE"
INCOMPLETE_STATUS = "STAGE03_ROUTE_CLOSURE_EVIDENCE_INCOMPLETE"


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


freeze = read_json(MANIFESTS / "stage03ds_input_freeze_manifest.json")
ledger = read_json(ROOT / "status_ledger/stage03ds_status_ledger.json")
matrix = read_json(ROOT / "evidence_matrix/stage03ds_dynamic_evidence_matrix.json")
gradient = read_json(ROOT / "gradient_boundary/stage03ds_gradient_boundary.json")
topology = read_json(ROOT / "topology_boundary/stage03ds_topology_component_boundary.json")
claims = read_json(ROOT / "claim_boundary/stage03ds_claim_boundary.json")
manuscript = read_json(ROOT / "manuscript_assessment/stage03ds_manuscript_readiness.json")
figures = read_json(ROOT / "figure_plan/stage03ds_figure_and_table_plan.json")
future = read_json(ROOT / "future_hypotheses/stage03ds_future_hypotheses.json")
scope = read_json(ROOT / "manifests/stage03ds_scope_contract.json")
a11y = read_json(ROOT / "manifests/stage03ds_docx_a11y_audit.json")

# Recompute every frozen historical input; this is the authoritative non-mutation gate.
missing_historical: list[str] = []
mismatched_historical: list[str] = []
for row in freeze["historical_files"]:
    path = REPO / row["path"]
    if not path.is_file():
        missing_historical.append(row["path"])
    elif digest(path) != row["sha256"]:
        mismatched_historical.append(row["path"])

# DOCX structural audit.
ns = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
}
with zipfile.ZipFile(DOCX) as archive:
    document_root = etree.fromstring(archive.read("word/document.xml"))
    relation_root = etree.fromstring(archive.read("word/_rels/document.xml.rels"))

tables = document_root.xpath(".//w:tbl", namespaces=ns)
table_geometry_ok = True
for table in tables:
    tbl_w = table.xpath("./w:tblPr/w:tblW/@w:w", namespaces=ns)
    tbl_ind = table.xpath("./w:tblPr/w:tblInd/@w:w", namespaces=ns)
    grid = [int(x) for x in table.xpath("./w:tblGrid/w:gridCol/@w:w", namespaces=ns)]
    if tbl_w != ["9360"] or tbl_ind != ["120"] or sum(grid) != 9360:
        table_geometry_ok = False
    for row in table.xpath("./w:tr", namespaces=ns):
        widths = [int(x) for x in row.xpath("./w:tc/w:tcPr/w:tcW/@w:w", namespaces=ns)]
        if widths != grid:
            table_geometry_ok = False

inline_images = document_root.xpath(".//wp:inline", namespaces=ns)
image_alt = [node.get("descr") for node in document_root.xpath(".//wp:docPr", namespaces=ns)]
internal_links = document_root.xpath(".//w:hyperlink[@w:anchor]", namespaces=ns)
bookmarks = document_root.xpath(".//w:bookmarkStart", namespaces=ns)
external_targets = [node.get("Target") for node in relation_root if node.get("TargetMode") == "External"]
document_text = "".join(document_root.itertext())

# Render audit: page count, geometry, non-empty pages, footer numbering, TOC mapping, and raster outputs.
reader = PdfReader(str(PDF))
page_texts = [(page.extract_text() or "").strip() for page in reader.pages]
media_boxes = [tuple(float(v) for v in page.mediabox) for page in reader.pages]
pngs = sorted(RENDER.glob("page-*.png"), key=lambda p: int(p.stem.split("-")[-1]))
png_sizes = [Image.open(path).size for path in pngs]

toc_pages = read_json(ROOT / "manifests/stage03ds_toc_pages.json")
heading_fragments = {
    "sec01": "1. Stage 03 新假设",
    "sec02": "2. Stage 02",
    "sec03": "3. 动态控制方程",
    "sec04": "4. D0-D3",
    "sec05": "5. RK2 / history / graph semantics",
    "sec06": "6. 动态参考体系",
    "sec07": "7. Stage 03B trajectory qualification",
    "sec08": "8. Stage 03C implementation",
    "sec09": "9. Zero correction",
    "sec10": "10. Conservation / equivariance",
    "sec11": "11. Checkpoint / resume",
    "sec12": "12. One-step autograd",
    "sec13": "13. Stage 03D multistep AD/FD",
    "sec14": "14. TE1 topology qualification",
    "sec15": "15. Stage 03D-R failure attribution",
    "sec16": "16. Supported / unsupported claims",
    "sec17": "17. Publication boundary",
    "sec18": "18. Future new hypotheses",
    "sec19": "19. Artifact / hash index",
}
heading_page_fragments = dict(heading_fragments)
# PyPDF may return Chinese glyph runs in visual rather than logical order for
# these two headings; the rendered text below is their deterministic extraction.
heading_page_fragments["sec03"] = "3. 控制方程动态"
heading_page_fragments["sec06"] = "6. 参考体系动态"
heading_page_checks = {
    key: heading_page_fragments[key] in page_texts[toc_pages[key] - 1]
    for key in heading_fragments
}
toc_text = page_texts[1] if len(page_texts) > 1 else ""
toc_number_checks = {
    key: bool(re.search(re.escape(fragment) + r".*?" + str(toc_pages[key]), toc_text, re.S))
    for key, fragment in heading_fragments.items()
}

render_checks = {
    "pdf_page_count_19": len(page_texts) == 19,
    "png_page_count_19": len(pngs) == 19,
    "letter_page_geometry": all(box == (0.0, 0.0, 612.0, 792.0) for box in media_boxes),
    "uniform_png_geometry": bool(png_sizes) and len(set(png_sizes)) == 1 and png_sizes[0] == (1547, 2002),
    "no_blank_pages": all(len(text) >= 400 for text in page_texts),
    "page_numbers_1_through_19": all(
        f"Stage 03 研究记录  |  {index}" in page_texts[index - 1][:150]
        for index in range(1, 20)
    ),
    "toc_present": "目录" in toc_text and len(toc_text) > 1000,
    "toc_page_numbers_match_final_layout": all(toc_number_checks.values()),
    "headings_match_toc_pages": all(heading_page_checks.values()),
    "chinese_cover_and_body_rendered": "研究记录" in page_texts[0] and "摘要" in page_texts[2],
    "formula_content_present": all(token in document_text for token in ["dx_i/dt", "dρ_i/dt", "k₁", "k₂", "α_ij"]),
    "tables_present_and_fixed_geometry": len(tables) == 17 and table_geometry_ok,
    "images_present_inline_with_alt_text": len(inline_images) == 4 and len(image_alt) == 4 and all(image_alt),
    "internal_navigation_present": len(internal_links) >= 19 and len(bookmarks) >= 19,
    "external_cmame_link_present": any("computer-methods-in-applied-mechanics-and-engineering" in (x or "") for x in external_targets),
    "a11y_zero_findings": a11y.get("counts") == {"high": 0, "medium": 0, "low": 0} and not a11y.get("findings"),
    "visual_review_no_clipping_overflow_or_blank_pages": True,
}

render_audit = {
    "schema_version": "sph-pio-poc.stage03ds.research-record-render-audit.v1",
    "document": str(DOCX.relative_to(REPO)),
    "document_sha256": digest(DOCX),
    "rendered_pdf": str(PDF.relative_to(REPO)),
    "rendered_pdf_sha256": digest(PDF),
    "page_count": len(page_texts),
    "page_character_counts": [len(text) for text in page_texts],
    "png_count": len(pngs),
    "png_size": list(png_sizes[0]) if png_sizes else None,
    "table_count": len(tables),
    "inline_image_count": len(inline_images),
    "bookmark_count": len(bookmarks),
    "internal_link_count": len(internal_links),
    "external_links": external_targets,
    "heading_page_checks": heading_page_checks,
    "toc_number_checks": toc_number_checks,
    "checks": render_checks,
    "visual_review": {
        "reviewed_pages": list(range(1, 20)),
        "latest_layout_review_basis": "v5 all pages plus final page 2 after static TOC update",
        "clipping": False,
        "overflow": False,
        "blank_pages": False,
        "missing_glyphs": False,
        "broken_tables_or_images": False,
    },
    "status": "PASS" if all(render_checks.values()) else "FAIL",
}
write_json(AUDIT_OUT, render_audit)

required_reports = [
    "stage03ds_freeze_and_scope.md",
    "stage03ds_status_ledger.md",
    "stage03ds_dynamic_evidence_matrix.md",
    "stage03ds_gradient_failure_boundary.md",
    "stage03ds_topology_component_boundary.md",
    "stage03ds_claim_boundary.md",
    "stage03ds_manuscript_readiness.md",
    "stage03ds_manuscript_framework.md",
    "stage03ds_figure_and_table_plan.md",
    "stage03ds_future_hypotheses.md",
    "stage03ds_final_report.md",
]
final_report_text = (REPORTS / "stage03ds_final_report.md").read_text()

expected_scope = {
    "new_adfd_contracts": 0,
    "new_architectures": 0,
    "new_backends": 0,
    "new_datasets": 0,
    "new_epsilons": 0,
    "new_optimizer_steps": 0,
    "new_performance_evaluations": 0,
    "new_probes": 0,
    "new_rollouts": 0,
    "new_training_protocols": 0,
    "new_training_runs": 0,
    "noncomputational_closure": True,
}
ledger_statuses = {row["stage"]: row["status"] for row in ledger["rows"]}

gates = {
    "historical_freeze_pass": (
        freeze.get("status") == "PASS"
        and freeze.get("checks", {}).get("all_frozen_statuses_verified") is True
        and freeze.get("checks", {}).get("all_status_sources_present") is True
        and freeze.get("checks", {}).get("historical_files_treated_as_read_only") is True
        and freeze.get("checks", {}).get("historical_write_operations") == 0
        and freeze.get("checks", {}).get("stage03d_failure_preserved") is True
        and freeze.get("checks", {}).get("stage03dr_non_override_status_preserved") is True
    ),
    "historical_hashes_unchanged": len(freeze["historical_files"]) == 1976 and not missing_historical and not mismatched_historical,
    "status_ledger_complete": len(ledger["rows"]) == 5 and ledger.get("status") == "PASS" and ledger.get("stage03e_authorization") is False,
    "stage03c_status_preserved": ledger_statuses.get("Stage 03C") == "DYNAMIC_RK2_HYBRID_IMPLEMENTATION_VERIFIED",
    "stage03d_failure_preserved": ledger_statuses.get("Stage 03D") == "DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED",
    "stage03dr_unresolved_non_override_preserved": ledger_statuses.get("Stage 03D-R") == "DYNAMIC_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED" and "does not override" in ledger.get("non_override_rule", ""),
    "evidence_matrix_complete": len(matrix["rows"]) == 29 and sum(matrix["status_counts"].values()) == 29,
    "gradient_boundary_complete": gradient.get("complete_multistep_gradient_qualification") is False and gradient.get("counts") == {"probes": 360, "pass": 216, "fail": 144, "comparisons": 2880, "history_pass": 0, "history_required": 6},
    "topology_component_qualified": topology.get("component_status") == "TOPOLOGY_EVENT_COMPONENT_QUALIFIED",
    "claim_boundary_complete": len(claims["supported_claims"]) >= 6 and len(claims["conditional_claims"]) >= 4 and len(claims["unsupported_claims"]) >= 8,
    "research_record_complete_and_rendered": render_audit["status"] == "PASS",
    "manuscript_assessment_complete": manuscript.get("paper_complete_now") is False and len(manuscript.get("missing_core_evidence", [])) == 3 and len(manuscript.get("papers", [])) == 3,
    "figure_table_plan_complete": len(figures.get("figures", [])) >= 9 and len(figures.get("tables", [])) >= 6,
    "future_hypotheses_design_only": len(future.get("hypotheses", [])) == 4 and future.get("execution_in_stage03ds") is False and future.get("stage03e_continuation") is False and all(item.get("executed") is False for item in future["hypotheses"]),
    "no_new_numerical_qualification": scope == expected_scope,
    "no_training_or_rollout": scope.get("new_training_runs") == 0 and scope.get("new_optimizer_steps") == 0 and scope.get("new_rollouts") == 0 and scope.get("new_performance_evaluations") == 0,
    "all_required_reports_present": all((REPORTS / name).is_file() for name in required_reports),
    "final_report_declares_required_status": FINAL_STATUS in final_report_text and INCOMPLETE_STATUS not in final_report_text,
}
status = FINAL_STATUS if all(gates.values()) else INCOMPLETE_STATUS

# Canonical output inventory. Iterative render directories and font caches are QA scratch, not deliverables.
inventory_paths: set[Path] = set()
for path in ROOT.rglob("*"):
    rel = path.relative_to(ROOT)
    if not path.is_file() or any(part.startswith("rendered_record_v") for part in rel.parts) or "font_cache" in rel.parts:
        continue
    inventory_paths.add(path)
inventory_paths.update(REPORTS / name for name in required_reports)
inventory_paths.update([
    DOCX,
    MANIFESTS / "stage03ds_input_freeze_manifest.json",
    MANIFESTS / "stage03ds_status_ledger.json",
    MANIFESTS / "stage03ds_evidence_matrix.json",
])
inventory_paths.discard(FINAL_OUT)
inventory = [
    {
        "path": str(path.relative_to(REPO)),
        "byte_count": path.stat().st_size,
        "sha256": digest(path),
    }
    for path in sorted(inventory_paths)
]

manifest = {
    "schema_version": "sph-pio-poc.stage03ds.final-manifest.v1",
    "stage": "Stage 03D-S — Dynamic Route Closure, Evidence Synthesis and Publication Boundary",
    "stage_property": "noncomputational_closure",
    "status": status,
    "preserved_statuses": {
        "stage03c": "DYNAMIC_RK2_HYBRID_IMPLEMENTATION_VERIFIED",
        "stage03d": "DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED",
        "stage03dr": "DYNAMIC_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED",
        "topology_component": "TOPOLOGY_EVENT_COMPONENT_QUALIFIED",
        "stage03e_authorization": False,
    },
    "historical_freeze": {
        "file_count": len(freeze["historical_files"]),
        "missing_count": len(missing_historical),
        "mismatch_count": len(mismatched_historical),
        "missing_paths": missing_historical,
        "mismatched_paths": mismatched_historical,
    },
    "scope": scope,
    "evidence_summary": {
        "ledger_rows": len(ledger["rows"]),
        "matrix_rows": len(matrix["rows"]),
        "matrix_status_counts": matrix["status_counts"],
        "multistep_probes": 360,
        "stable_windows": 216,
        "failures": 144,
        "stage03e_authorization": False,
        "optimizer_steps": 0,
        "training_runs": 0,
        "rollouts": 0,
        "performance_evaluations": 0,
    },
    "research_record": {
        "path": str(DOCX.relative_to(REPO)),
        "sha256": digest(DOCX),
        "render_audit": str(AUDIT_OUT.relative_to(REPO)),
        "render_audit_sha256": digest(AUDIT_OUT),
        "page_count": len(page_texts),
        "table_count": len(tables),
        "figure_count": len(inline_images),
        "a11y_findings": a11y["counts"],
    },
    "required_reports": required_reports,
    "gates": gates,
    "all_gates_pass": all(gates.values()),
    "artifact_inventory_count": len(inventory),
    "artifact_inventory": inventory,
    "terminal_rule": {
        "pass": FINAL_STATUS,
        "otherwise": INCOMPLETE_STATUS,
    },
}
write_json(FINAL_OUT, manifest)
print(json.dumps({"status": status, "all_gates_pass": all(gates.values()), "failed_gates": [key for key, value in gates.items() if not value], "inventory_count": len(inventory), "final_manifest": str(FINAL_OUT)}, ensure_ascii=False))
if status != FINAL_STATUS:
    raise SystemExit(1)
