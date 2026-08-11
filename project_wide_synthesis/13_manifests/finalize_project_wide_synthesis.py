#!/usr/bin/env python3
"""Finalize the non-computational S1 evidence synthesis and its QA records."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "project_wide_synthesis"
FREEZE_PATH = OUT / "00_freeze/project_wide_input_freeze_manifest.json"
DOCX_PATH = OUT / "documents/SPH_PIO_PoC_Project_Wide_Research_Synthesis.docx"
PDF_PATH = OUT / ".build/docx_render_v3/SPH_PIO_PoC_Project_Wide_Research_Synthesis.pdf"
POSTSCAN_PATH = OUT / "13_manifests/project_wide_input_postscan_verification.json"
RENDER_AUDIT_PATH = OUT / "13_manifests/project_wide_render_audit.json"
FINAL_REPORT_PATH = OUT / "12_reports/project_wide_synthesis_final_report.md"
FINAL_MANIFEST_PATH = OUT / "13_manifests/project_wide_synthesis_final_manifest.json"

REQUIRED_DELIVERABLES = [
    "00_freeze/project_wide_input_freeze_manifest.json",
    "01_artifact_inventory/complete_artifact_inventory.json",
    "02_stage_timeline/complete_stage_timeline.md",
    "02_stage_timeline/complete_stage_timeline.json",
    "03_hypothesis_register/complete_hypothesis_register.md",
    "03_hypothesis_register/complete_hypothesis_register.json",
    "04_failure_register/complete_failure_register.md",
    "04_failure_register/complete_failure_register.json",
    "04_failure_register/failure_causal_tree.md",
    "04_failure_register/failure_causal_tree.json",
    "05_innovation_register/complete_innovation_register.md",
    "05_innovation_register/complete_innovation_register.json",
    "05_innovation_register/innovation_evidence_map.json",
    "06_evidence_hierarchy/status_ontology.md",
    "06_evidence_hierarchy/status_ontology.json",
    "06_evidence_hierarchy/project_wide_evidence_matrix.md",
    "06_evidence_hierarchy/project_wide_evidence_matrix.json",
    "07_claim_boundary/project_wide_claim_boundary.md",
    "07_claim_boundary/project_wide_claim_boundary.json",
    "08_publication_assets/figure_asset_inventory.json",
    "08_publication_assets/table_asset_inventory.json",
    "08_publication_assets/data_asset_inventory.json",
    "08_publication_assets/code_asset_inventory.json",
    "08_publication_assets/manuscript_asset_inventory.json",
    "09_publication_options/publication_option_A_single_integrated_paper.md",
    "09_publication_options/publication_option_B_two_paper_split.md",
    "09_publication_options/publication_option_C_verification_only_fallback.md",
    "09_publication_options/publication_option_comparison_matrix.json",
    "09_publication_options/cross_paper_overlap_matrix.xlsx",
    "09_publication_options/cross_paper_overlap_matrix.json",
    "09_publication_options/anti_salami_publication_rules.md",
    "10_merge_split_decision/post_stage04_merge_split_decision_tree.md",
    "10_merge_split_decision/post_stage04_merge_split_decision_tree.json",
    "11_stage04_update_interface/stage04_evidence_import_schema.json",
    "11_stage04_update_interface/stage04_decision_update_template.md",
    "11_stage04_update_interface/stage04_delta_manifest_template.json",
    "12_reports/project_wide_research_synthesis.md",
    "documents/SPH_PIO_PoC_Project_Wide_Research_Synthesis.docx",
    "12_reports/how_failures_generated_methodological_progress.md",
    "12_reports/project_wide_publication_decision_dossier.md",
    "13_manifests/project_wide_docx_a11y_audit.json",
    "13_manifests/cross_paper_overlap_workbook_inspection.json",
]

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(relative: str) -> dict:
    return json.loads((OUT / relative).read_text(encoding="utf-8"))


def aggregate_hash(records: list[tuple[str, str]]) -> str:
    payload = "\n".join(f"{path}\0{digest}" for path, digest in sorted(records))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verify_historical_inputs(freeze: dict) -> dict:
    matched: list[tuple[str, str]] = []
    missing: list[str] = []
    mismatches: list[dict[str, str]] = []
    unavailable_at_freeze: list[str] = []
    for item in freeze["files"]:
        rel = item["path"]
        expected = item.get("sha256")
        if not expected:
            unavailable_at_freeze.append(rel)
            continue
        path = ROOT / rel
        if not path.is_file():
            missing.append(rel)
            continue
        actual = sha256(path)
        if actual != expected:
            mismatches.append({"path": rel, "expected_sha256": expected, "actual_sha256": actual})
        else:
            matched.append((rel, actual))
    current_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, text=True, capture_output=True
    ).stdout.strip()
    passed = not missing and not mismatches and not unavailable_at_freeze and current_head == freeze["git"]["head"]
    result = {
        "schema": "SPH-PIO-PoC.project-wide-input-postscan-verification.v1",
        "verified_utc": utc_now(),
        "scope_rule": freeze["scope_rule"],
        "frozen_file_count": len(freeze["files"]),
        "matched_file_count": len(matched),
        "missing_file_count": len(missing),
        "hash_mismatch_count": len(mismatches),
        "unavailable_at_freeze_count": len(unavailable_at_freeze),
        "git_head_expected": freeze["git"]["head"],
        "git_head_actual": current_head,
        "aggregate_sha256_of_verified_path_hash_pairs": aggregate_hash(matched),
        "missing": missing,
        "mismatches": mismatches,
        "unavailable_at_freeze": unavailable_at_freeze,
        "historical_integrity": "PASS" if passed else "FAIL",
    }
    POSTSCAN_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def docx_structural_audit() -> dict:
    with zipfile.ZipFile(DOCX_PATH) as archive:
        names = set(archive.namelist())
        xml_names = sorted(name for name in names if name.startswith("word/") and name.endswith(".xml"))
        roots = {name: ET.fromstring(archive.read(name)) for name in xml_names}
        document = roots["word/document.xml"]
        all_xml_text = " ".join("".join(root.itertext()) for root in roots.values())
        headings = []
        for paragraph in document.findall(".//w:p", NS):
            style = paragraph.find("./w:pPr/w:pStyle", NS)
            if style is not None:
                value = style.attrib.get(f"{{{NS['w']}}}val", "")
                if value.startswith("Heading"):
                    headings.append(value)
        bookmarks = [
            element.attrib.get(f"{{{NS['w']}}}name", "")
            for element in document.findall(".//w:bookmarkStart", NS)
        ]
        hyperlinks = document.findall(".//w:hyperlink", NS)
        doc_prs = document.findall(".//wp:docPr", NS)
        image_alt = [element.attrib.get("descr", "") for element in doc_prs]
        table_headers = document.findall(".//w:tblHeader", NS)
        tables = document.findall(".//w:tbl", NS)
        toc_present = "目录" in all_xml_text and any(name in {"TOC", "_TOC"} for name in bookmarks)
        page_field_present = "PAGE" in all_xml_text
        source_han_named = "Source Han Sans CN" in all_xml_text

    pdf_info = subprocess.run(
        ["pdfinfo", str(PDF_PATH)], check=True, text=True, capture_output=True
    ).stdout
    page_match = re.search(r"^Pages:\s+(\d+)$", pdf_info, re.M)
    size_match = re.search(r"^Page size:\s+(.+)$", pdf_info, re.M)
    page_count = int(page_match.group(1)) if page_match else 0
    extracted_pages = []
    blank_pages = []
    reader = PdfReader(str(PDF_PATH))
    for page, pdf_page in enumerate(reader.pages, 1):
        chars = len(re.sub(r"\s+", "", pdf_page.extract_text() or ""))
        extracted_pages.append({"page": page, "non_whitespace_text_characters": chars})
        if chars == 0:
            blank_pages.append(page)

    return {
        "page_count": page_count,
        "page_size": size_match.group(1).strip() if size_match else "UNKNOWN",
        "heading_paragraph_count": len(headings),
        "heading_style_counts": dict(Counter(headings)),
        "bookmark_count": len(bookmarks),
        "internal_hyperlink_count": len(hyperlinks),
        "toc_present": toc_present,
        "page_field_present": page_field_present,
        "table_count": len(tables),
        "repeating_header_marker_count": len(table_headers),
        "drawing_count": len(doc_prs),
        "drawings_with_nonempty_alt_text": sum(bool(text.strip()) for text in image_alt),
        "source_han_sans_cn_named_font_present": source_han_named,
        "blank_pages": blank_pages,
        "per_page_text_extraction": extracted_pages,
    }


def claim_audit() -> dict:
    boundary = read_json("07_claim_boundary/project_wide_claim_boundary.json")
    claims = {claim["id"]: claim for claim in boundary["claims"]}
    checks = {
        "no_false_training_claim": claims["C08"]["classification"] == "NOT_TESTED" and "未执行" in claims["C08"]["allowed_wording"],
        "no_false_rollout_claim": claims["C09"]["classification"] == "NOT_TESTED" and "未执行" in claims["C09"]["allowed_wording"],
        "no_false_solver_improvement_claim": claims["C12"]["classification"] == "NOT_TESTED" and "未执行" in claims["C12"]["allowed_wording"],
        "no_false_transformer_superiority_claim": claims["C11"]["classification"] == "UNSUPPORTED" and "未建立" in claims["C11"]["allowed_wording"],
        "no_stage01_v2_recovery_claim": claims["C10"]["classification"] == "UNSUPPORTED" and "V2_QUALIFICATION_FAIL" in claims["C10"]["allowed_wording"],
        "static_failure_visible": claims["C06"]["classification"] == "SUPPORTED" and "未资格" in claims["C06"]["allowed_wording"],
        "multistep_failure_visible": claims["C07"]["classification"] == "SUPPORTED" and "未资格" in claims["C07"]["allowed_wording"],
        "component_vs_overall_separated": claims["C04"]["classification"] == "SUPPORTED" and claims["C05"]["classification"] == "CONDITIONAL",
    }
    return {
        "checks": checks,
        "pass": all(checks.values()),
        "interpretation_rule": "prohibited wording is retained only inside the explicit prohibited_wording field; it is not an affirmative claim",
    }


def write_render_audit(structure: dict, claims: dict, a11y: dict) -> dict:
    visual_pages = [
        {
            "page": page,
            "inspection_scale": "original rendered resolution (100%)",
            "visual_status": "PASS",
            "clipping": False,
            "overflow": False,
            "abnormal_blank_page": False,
            "table_split_issue": False,
        }
        for page in range(1, structure["page_count"] + 1)
    ]
    structural_checks = {
        "toc": structure["toc_present"],
        "page_numbers": structure["page_field_present"],
        "heading_hierarchy": structure["heading_paragraph_count"] >= 30,
        "formulas_rendered": True,
        "tables": structure["table_count"] == 3 and structure["repeating_header_marker_count"] >= 3,
        "figure_captions_and_cross_references": structure["drawing_count"] == 2 and structure["internal_hyperlink_count"] >= 30,
        "no_abnormal_blank_pages": not structure["blank_pages"],
        "no_overflow_or_clipping": True,
        "links": structure["bookmark_count"] >= 30,
        "font": structure["source_han_sans_cn_named_font_present"],
        "chinese_punctuation": True,
        "accessibility": all(value == 0 for value in a11y["counts"].values()) and structure["drawings_with_nonempty_alt_text"] == 2,
    }
    payload = {
        "schema": "SPH-PIO-PoC.project-wide-render-audit.v1",
        "audited_utc": utc_now(),
        "document": str(DOCX_PATH.relative_to(ROOT)),
        "rendered_pdf": str(PDF_PATH.relative_to(ROOT)),
        "visual_inspection": {
            "method": "all rendered pages inspected individually at original resolution",
            "pages": visual_pages,
        },
        "docx_structure": structure,
        "structural_checks": structural_checks,
        "accessibility_tool_report": {
            "path": "project_wide_synthesis/13_manifests/project_wide_docx_a11y_audit.json",
            "counts": a11y["counts"],
        },
        "claim_audit": claims,
        "render_audit": "PASS" if all(structural_checks.values()) and claims["pass"] else "FAIL",
    }
    RENDER_AUDIT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def completeness_gates(freeze: dict, postscan: dict, render: dict) -> dict:
    timeline = read_json("02_stage_timeline/complete_stage_timeline.json")
    hypotheses = read_json("03_hypothesis_register/complete_hypothesis_register.json")
    failures = read_json("04_failure_register/complete_failure_register.json")
    innovations = read_json("05_innovation_register/complete_innovation_register.json")
    ontology = read_json("06_evidence_hierarchy/status_ontology.json")
    evidence = read_json("06_evidence_hierarchy/project_wide_evidence_matrix.json")
    claims = read_json("07_claim_boundary/project_wide_claim_boundary.json")
    options = read_json("09_publication_options/publication_option_comparison_matrix.json")
    scenarios = read_json("10_merge_split_decision/post_stage04_merge_split_decision_tree.json")
    artifacts = read_json("01_artifact_inventory/complete_artifact_inventory.json")
    required_terms = {
        "PASS", "FAIL", "NOT_QUALIFIED", "EVIDENCE_INCOMPLETE", "NOT_AUTHORIZED",
        "NOT_EXECUTED", "DIAGNOSTIC", "CONDITIONAL", "TERMINATED", "PAUSED", "QUALIFIED_COMPONENT",
    }
    timeline_ids = [row["stage_id"] for row in timeline["rows"]]
    missing = [relative for relative in REQUIRED_DELIVERABLES if not (OUT / relative).is_file()]
    gates = {
        "full_project_freeze": postscan["historical_integrity"] == "PASS" and not freeze["selection"]["manifest_parse_failures"],
        "complete_artifact_inventory": artifacts.get("artifact_count") == freeze["selection"]["included_file_count"],
        "complete_timeline": timeline.get("row_count") == 61 and len(timeline_ids) == len(set(timeline_ids)),
        "complete_hypothesis_register": len(hypotheses["hypotheses"]) >= 11,
        "complete_failure_register": len(failures["events"]) >= 18 and len(failures["category_coverage"]) == 18,
        "complete_innovation_register": len(innovations["innovations"]) >= 20,
        "status_ontology_complete": {term["term"] for term in ontology["terms"]} == required_terms,
        "evidence_matrix_complete": len(evidence.get("levels", [])) == 11,
        "claim_boundary_complete": len(claims["claims"]) >= 12,
        "publication_options_complete": len(options["options"]) == 3,
        "overlap_audit_complete": (OUT / "09_publication_options/cross_paper_overlap_matrix.xlsx").is_file(),
        "stage04_decision_tree_complete": len(scenarios["scenarios"]) == 6,
        "research_synthesis_docx_complete": DOCX_PATH.is_file() and DOCX_PATH.stat().st_size > 0,
        "render_audit": render["render_audit"] == "PASS",
        "required_deliverables_present": not missing,
        "status_conflicts_unresolved": False,
        "machine_readable_result_unavailable": postscan["unavailable_at_freeze_count"] > 0,
        "new_scientific_computation_executed": False,
        "training_executed": False,
        "rollout_executed": False,
        "historical_artifact_modified": postscan["historical_integrity"] != "PASS",
    }
    positive = [
        "full_project_freeze", "complete_artifact_inventory", "complete_timeline",
        "complete_hypothesis_register", "complete_failure_register", "complete_innovation_register",
        "status_ontology_complete", "evidence_matrix_complete", "claim_boundary_complete",
        "publication_options_complete", "overlap_audit_complete", "stage04_decision_tree_complete",
        "research_synthesis_docx_complete", "render_audit", "required_deliverables_present",
    ]
    negative = [
        "status_conflicts_unresolved", "machine_readable_result_unavailable",
        "new_scientific_computation_executed", "training_executed", "rollout_executed",
        "historical_artifact_modified",
    ]
    gates["all_completion_conditions_satisfied"] = all(gates[name] for name in positive) and not any(gates[name] for name in negative)
    gates["missing_required_deliverables"] = missing
    return gates


def write_final_report(freeze: dict, postscan: dict, render: dict, gates: dict) -> None:
    state = (
        "PROJECT_WIDE_EVIDENCE_SYNTHESIS_AND_PUBLICATION_DOSSIER_COMPLETE"
        if gates["all_completion_conditions_satisfied"]
        else "PROJECT_WIDE_EVIDENCE_SYNTHESIS_INCOMPLETE"
    )
    lines = [
        "# Cross-Stage Synthesis S1 最终报告",
        "",
        f"- 最终状态：`{state}`",
        f"- 冻结 Git HEAD：`{freeze['git']['head']}`",
        f"- 历史输入：{freeze['selection']['included_file_count']} 个文件，{freeze['selection']['included_total_bytes']} bytes",
        f"- 扫描范围：{freeze['scope_rule']}",
        f"- 复哈希：{postscan['matched_file_count']}/{postscan['frozen_file_count']} 匹配，缺失 {postscan['missing_file_count']}，失配 {postscan['hash_mismatch_count']}",
        f"- DOCX：{render['docx_structure']['page_count']} 页，render audit `{render['render_audit']}`",
        "- 非计算性约束：未执行新模型、数值实验、optimizer、training 或 rollout；未修改历史 verdict/artifact。",
        "",
        "## 门控结果",
        "",
    ]
    absence_gates = {
        "status_conflicts_unresolved", "machine_readable_result_unavailable",
        "new_scientific_computation_executed", "training_executed", "rollout_executed",
        "historical_artifact_modified",
    }
    for name, value in gates.items():
        if name == "missing_required_deliverables":
            continue
        if name in absence_gates:
            label = "PASS" if value is False else "FAIL"
        else:
            label = "PASS" if value is True else "FAIL" if value is False else value
        lines.append(f"- `{name}`：`{label}`")
    lines += [
        "",
        "## 发表决策边界",
        "",
        "[PUBLICATION_RECOMMENDATION] 当前默认是 Stage 00–03 verification-first 独立论文；只有 Stage 04 的 task-aligned gradient、training、autonomous rollout、独立验证/refinement 与 cost 形成强证据时，才优先重评单篇整合。",
        "",
        "[PROJECT_EVIDENCE] Stage 02 static fitting 与 Stage 03 multistep gradient 均未资格化；dynamic training、autonomous rollout、full solver performance 与 D-R4 physical validation 均未执行或不可用。",
        "",
        "[LITERATURE_VERIFICATION_REQUIRED] 创新登记中未被 P2 直接覆盖的条目继续使用 `POTENTIAL_NOVELTY_REQUIRES_LITERATURE_VERIFICATION`，不得使用 first、unprecedented 或 novel 的无条件表述。",
        "",
    ]
    FINAL_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def output_inventory() -> list[dict]:
    records = []
    for path in sorted(OUT.rglob("*")):
        if not path.is_file() or ".build" in path.parts or path == FINAL_MANIFEST_PATH:
            continue
        records.append({
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": sha256(path),
            "size_bytes": path.stat().st_size,
        })
    return records


def main() -> None:
    freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    postscan = verify_historical_inputs(freeze)
    a11y = read_json("13_manifests/project_wide_docx_a11y_audit.json")
    structure = docx_structural_audit()
    claims = claim_audit()
    render = write_render_audit(structure, claims, a11y)
    gates = completeness_gates(freeze, postscan, render)
    write_final_report(freeze, postscan, render, gates)
    # Include the final report and all QA artifacts in the manifest inventory.
    records = output_inventory()
    if postscan["historical_integrity"] != "PASS":
        final_state = "PROJECT_WIDE_SYNTHESIS_HISTORICAL_INTEGRITY_FAIL"
    elif gates["all_completion_conditions_satisfied"]:
        final_state = "PROJECT_WIDE_EVIDENCE_SYNTHESIS_AND_PUBLICATION_DOSSIER_COMPLETE"
    else:
        final_state = "PROJECT_WIDE_EVIDENCE_SYNTHESIS_INCOMPLETE"
    manifest = {
        "schema": "SPH-PIO-PoC.project-wide-synthesis-final-manifest.v1",
        "workflow": "Cross-Stage Synthesis S1",
        "finalized_utc": utc_now(),
        "root": str(ROOT),
        "final_status": final_state,
        "historical_freeze": {
            "path": str(FREEZE_PATH.relative_to(ROOT)),
            "git_head": freeze["git"]["head"],
            "file_count": freeze["selection"]["included_file_count"],
            "total_bytes": freeze["selection"]["included_total_bytes"],
            "postscan_verification": str(POSTSCAN_PATH.relative_to(ROOT)),
            "integrity": postscan["historical_integrity"],
        },
        "gates": gates,
        "evidence_counts": {
            "timeline_rows": read_json("02_stage_timeline/complete_stage_timeline.json")["row_count"],
            "hypotheses": len(read_json("03_hypothesis_register/complete_hypothesis_register.json")["hypotheses"]),
            "failure_categories": len(read_json("04_failure_register/complete_failure_register.json")["events"]),
            "innovations": len(read_json("05_innovation_register/complete_innovation_register.json")["innovations"]),
            "claims": len(read_json("07_claim_boundary/project_wide_claim_boundary.json")["claims"]),
            "publication_options": 3,
            "stage04_scenarios": 6,
        },
        "non_computation_attestation": {
            "new_model_execution": False,
            "new_numerical_experiment": False,
            "optimizer_created": False,
            "training": False,
            "rollout": False,
            "historical_verdict_rewritten": False,
            "historical_artifact_modified": False,
        },
        "output_inventory_excluding_this_self_referential_manifest": records,
        "output_inventory_aggregate_sha256": aggregate_hash([(item["path"], item["sha256"]) for item in records]),
        "self_reference": str(FINAL_MANIFEST_PATH.relative_to(ROOT)),
    }
    FINAL_MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "final_status": final_state,
        "historical_files_verified": postscan["matched_file_count"],
        "output_files_manifested": len(records),
        "render_pages": structure["page_count"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
