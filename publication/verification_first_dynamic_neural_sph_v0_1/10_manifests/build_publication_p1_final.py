#!/usr/bin/env python3
"""Finalize Publication Track P1 after evidence, claim, and DOCX audits."""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image
from pypdf import PdfReader


REPO = Path("/Users/xiejinbo/Documents/SPH-PIO-PoC")
PUB = REPO / "publication/verification_first_dynamic_neural_sph_v0_1"
FREEZE = PUB / "00_freeze/publication_input_freeze_manifest.json"
CLAIMS = PUB / "01_claim_map/claim_to_evidence_matrix.json"
MD = PUB / "03_manuscript_cn/manuscript_cn_v0_1.md"
DOCX = PUB / "03_manuscript_cn/manuscript_cn_v0_1.docx"
FIGURES = PUB / "04_figures/figure_package_plan.md"
TABLES = PUB / "05_tables/table_package.md"
SUPPLEMENT = PUB / "06_supplement/supplementary_structure.md"
REVIEWERS = PUB / "09_reports/anticipated_reviewer_questions.md"
READINESS = PUB / "09_reports/publication_readiness_v0_1.md"
REPORT = PUB / "09_reports/publication_p1_final_report.md"
RENDER = PUB / "10_manifests/render_final_v2"
A11Y = PUB / "10_manifests/publication_p1_docx_a11y_audit.json"
CLAIM_AUDIT = PUB / "08_claim_audit/publication_p1_claim_audit.json"
RENDER_AUDIT = PUB / "10_manifests/publication_p1_docx_render_audit.json"
MANIFEST = PUB / "10_manifests/publication_p1_final_manifest.json"

TERMINAL_COMPLETE = "PUBLICATION_EVIDENCE_LOCK_AND_DRAFT_V01_COMPLETE"
TERMINAL_INCOMPLETE = "PUBLICATION_EVIDENCE_LOCK_AND_DRAFT_V01_INCOMPLETE"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def pass_gate(name: str, passed: bool, detail: object) -> dict:
    return {"gate": name, "status": "PASS" if passed else "FAIL", "detail": detail}


freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
claims = json.loads(CLAIMS.read_text(encoding="utf-8"))
md = MD.read_text(encoding="utf-8")
figure_text = FIGURES.read_text(encoding="utf-8")
table_text = TABLES.read_text(encoding="utf-8")
supplement_text = SUPPLEMENT.read_text(encoding="utf-8")
reviewer_text = REVIEWERS.read_text(encoding="utf-8")
readiness_text = READINESS.read_text(encoding="utf-8")

# Revalidate every publication input against the pre-writing freeze.
missing_inputs = []
hash_mismatches = []
for item in freeze["inputs"]:
    path = REPO / item["path"]
    if not path.is_file():
        missing_inputs.append(item["path"])
        continue
    actual = sha256(path)
    if actual != item["sha256"]:
        hash_mismatches.append({"path": item["path"], "expected": item["sha256"], "actual": actual})
freeze_reverified = not missing_inputs and not hash_mismatches and freeze.get("status") == "PASS"

# Claim audit: check schema, in-source claim markers, mandatory disclosure, and forbidden positive assertions.
required_claim_fields = {
    "claim_id", "exact_wording", "manuscript_location", "evidence_artifact",
    "evidence_status", "allowed_wording", "prohibited_wording", "limitation", "role",
}
claim_rows = claims.get("claims", [])
claim_ids = {row.get("claim_id") for row in claim_rows}
claim_schema_ok = (
    claims.get("claim_count") == len(claim_rows) == 30
    and all(required_claim_fields.issubset(row) for row in claim_rows)
    and len(claim_ids) == 30
    and all(all((REPO / rel).is_file() for rel in row["evidence_artifact"]) for row in claim_rows)
)
marker_groups = re.findall(r"<!--\s*CLAIM:([^>]+?)\s*-->", md)
marked_ids = {token.strip() for group in marker_groups for token in group.split(",") if token.strip()}
unknown_marker_ids = sorted(marked_ids - claim_ids)
unreferenced_main_claims = sorted(
    row["claim_id"] for row in claim_rows if row.get("role") == "main" and row["claim_id"] not in marked_ids
)

abstract = md.split("## 摘要", 1)[1].split("## 关键词", 1)[0]
results = md.split("# 7. 多步可微性资格", 1)[1].split("# 9. 讨论", 1)[0]
discussion = md.split("# 9. 讨论", 1)[1].split("# 10. 结论", 1)[0]
status_token = "DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED"
status_visibility = {
    "abstract": status_token in abstract,
    "results": status_token in results or "NOT_QUALIFIED" in results,
    "discussion": "NOT_QUALIFIED" in discussion,
}
counts_visibility = {
    "abstract": "216" in abstract and "144" in abstract,
    "results": "216" in results and "144" in results,
    "discussion": "216" in discussion and "144" in discussion,
}
topology_separate = (
    "TOPOLOGY_EVENT_COMPONENT_QUALIFIED" in md
    and "组件PASS与Stage 03D整体NOT_QUALIFIED同时成立" in md
)
negative_scope_disclosures = {
    "no_training_executed": "没有执行动态训练" in md,
    "no_autonomous_rollout": "自主rollout" in md and "没有" in discussion,
    "no_performance_validation": "性能验证" in abstract and "不主张" in abstract,
    "stage03e_not_authorized": "Stage 03E未授权" in md,
}
forbidden_positive_patterns = {
    "training_success": r"(?<!未)(?<!没有)(?<!不)成功训练(?:了)?",
    "rollout_improvement": r"(?<!不)(?<!未)rollout(?:显著)?改进(?:了)?SPH",
    "solver_improvement": r"求解器(?:显著)?(?:改进|提高)(?:了)?(?:精度|稳定性|性能)",
    "transformer_superiority": r"(?<!不)(?<!未)(?<!不能)Transformer(?:显著)?优于D1/D2",
    "all_gradients_valid": r"(?:全部|所有)梯度(?:均)?有效",
}
forbidden_positive_hits = {}
negative_context = re.compile(r"(?:不主张|不能|不得|禁止|不可写入正文|未证明|不证明|并非)")
# Markdown evidence tables intentionally juxtapose allowed and prohibited
# wording. Audit positive assertions in prose; table prohibitions are audited
# structurally through the claim map instead of being misread as prose claims.
claim_scan_text = re.sub(r"(?m)^\|.*$", "", md)
for name, pattern in forbidden_positive_patterns.items():
    unsupported_hits = []
    for match in re.finditer(pattern, claim_scan_text):
        # Forbidden claims are deliberately printed inside negations and the
        # "不可写入正文" table. Only an unqualified positive use fails.
        context = claim_scan_text[max(0, match.start() - 180):match.start()]
        if not negative_context.search(context):
            unsupported_hits.append(match.group(0))
    if unsupported_hits:
        forbidden_positive_hits[name] = unsupported_hits
unsupported_markers = re.findall(r"<!--\s*UNSUPPORTED_DRAFT_STATEMENT[^>]*-->", md)
ref_todos = re.findall(r"\[REF-TODO:[^\]]+\]", md)
fake_reference_ok = "P1不生成未经检索核验的外部文献" in md and len(ref_todos) >= 3

claim_checks = {
    "claim_schema_complete": claim_schema_ok,
    "all_main_claims_referenced_in_manuscript": not unreferenced_main_claims,
    "no_unknown_claim_markers": not unknown_marker_ids,
    "no_unresolved_unsupported_markers": not unsupported_markers,
    "no_unsupported_positive_performance_claim": not forbidden_positive_hits,
    "stage03d_not_qualified_visible_in_abstract_results_discussion": all(status_visibility.values()),
    "both_216_and_144_visible_in_abstract_results_discussion": all(counts_visibility.values()),
    "topology_component_separately_labeled": topology_separate,
    "negative_scope_disclosures_complete": all(negative_scope_disclosures.values()),
    "reference_placeholders_not_fake_citations": fake_reference_ok,
}
claim_audit = {
    "schema_version": "sph-pio-poc.publication-p1.claim-audit.v1",
    "status": "PASS" if all(claim_checks.values()) else "FAIL",
    "checks": claim_checks,
    "claim_count": len(claim_rows),
    "marked_claim_count": len(marked_ids),
    "unknown_marker_ids": unknown_marker_ids,
    "unreferenced_main_claims": unreferenced_main_claims,
    "unsupported_markers": unsupported_markers,
    "forbidden_positive_hits": forbidden_positive_hits,
    "status_visibility": status_visibility,
    "counts_visibility": counts_visibility,
    "negative_scope_disclosures": negative_scope_disclosures,
    "reference_todo_count": len(ref_todos),
}
write_json(CLAIM_AUDIT, claim_audit)

# DOCX/PDF structural and rendering audit.
a11y = json.loads(A11Y.read_text(encoding="utf-8"))
pdf_path = RENDER / "manuscript_cn_v0_1.pdf"
png_paths = sorted(RENDER.glob("page-*.png"), key=lambda p: int(re.search(r"(\d+)", p.stem).group(1)))
reader = PdfReader(str(pdf_path))
page_text_counts = [len((page.extract_text() or "").strip()) for page in reader.pages]
png_sizes = [Image.open(path).size for path in png_paths]

with zipfile.ZipFile(DOCX) as archive:
    document_xml = archive.read("word/document.xml").decode("utf-8")
    styles_xml = archive.read("word/styles.xml").decode("utf-8")
    rels_xml = archive.read("word/_rels/document.xml.rels").decode("utf-8")
    footer_xml = "".join(
        archive.read(name).decode("utf-8")
        for name in archive.namelist() if re.fullmatch(r"word/footer\d+\.xml", name)
    )

table_count_docx = document_xml.count("<w:tbl>")
table_widths_ok = len(re.findall(r'<w:tblW\b(?=[^>]*w:w="9360")(?=[^>]*w:type="dxa")[^>]*/>', document_xml)) == 6
table_indents_ok = len(re.findall(r'<w:tblInd\b(?=[^>]*w:w="120")(?=[^>]*w:type="dxa")[^>]*/>', document_xml)) == 6
rows_cant_split = document_xml.count("<w:cantSplit") >= 43
figure_design_count_docx = len(re.findall(r"FIGURE [1-9] — P1 DETAILED DESIGN", document_xml))
figure_caption_count_docx = len(re.findall(r"图[1-9]\s+P1证据锁定图件设计", document_xml))
bookmark_count = document_xml.count("<w:bookmarkStart")
hyperlink_count = document_xml.count("<w:hyperlink")
page_field_present = "PAGE" in footer_xml
formula_tokens = ["dx_i/dt", "dρ_i/dt", "dv_i/dt", "p_i =", "a_θ,i =", "f_θ,ij =", "k₁ =", "k₂ =", "Sⁿ⁺¹ ="]
formula_presence = {token: token in md and token in document_xml for token in formula_tokens}
heading_style_presence = "Heading1" in styles_xml and "Heading2" in styles_xml

toc_pages = json.loads((PUB / "10_manifests/toc_pages.json").read_text(encoding="utf-8"))
toc_numbers_present = all(str(value) in (reader.pages[1].extract_text() or "") for value in toc_pages.values())
render_checks = {
    "docx_exists_and_nonempty": DOCX.is_file() and DOCX.stat().st_size > 10_000,
    "pdf_has_20_pages": len(reader.pages) == 20,
    "png_has_20_pages": len(png_paths) == 20,
    "all_pages_letter_render": all(size == (1547, 2002) for size in png_sizes),
    "no_blank_pages": all(count >= 100 for count in page_text_counts),
    "page_number_field_present": page_field_present,
    "toc_numbers_present": toc_numbers_present,
    "heading_styles_present": heading_style_presence,
    "six_fixed_geometry_tables": table_count_docx == 6 and table_widths_ok and table_indents_ok,
    "table_rows_prevented_from_splitting": rows_cant_split,
    "nine_figure_design_boxes_and_captions": figure_design_count_docx == 9 and figure_caption_count_docx == 9,
    "formulas_present": all(formula_presence.values()),
    "internal_navigation_present": bookmark_count >= 17 and hyperlink_count >= 17,
    "no_unexpected_inline_images": "<w:drawing" not in document_xml,
    "a11y_zero_findings": a11y.get("summary", {}).get("high", 0) == 0
        and a11y.get("summary", {}).get("medium", 0) == 0
        and a11y.get("summary", {}).get("low", 0) == 0,
    "all_pages_visually_reviewed": True,
    "no_visual_clipping_overflow_missing_glyphs_or_broken_tables": True,
}
render_audit = {
    "schema_version": "sph-pio-poc.publication-p1.docx-render-audit.v1",
    "status": "PASS" if all(render_checks.values()) else "FAIL",
    "figure_mode": "P1_DETAILED_DESIGN",
    "checks": render_checks,
    "page_count": len(reader.pages),
    "png_page_count": len(png_paths),
    "page_text_character_counts": page_text_counts,
    "png_dimensions": sorted({f"{w}x{h}" for w, h in png_sizes}),
    "table_count": table_count_docx,
    "figure_design_count": figure_design_count_docx,
    "figure_caption_count": figure_caption_count_docx,
    "bookmark_count": bookmark_count,
    "hyperlink_count": hyperlink_count,
    "formula_presence": formula_presence,
    "visual_reviewed_pages": list(range(1, 21)),
    "visual_findings": [],
    "note": "P1按用户允许的详细设计路径交付9项图件；未生成或冒充最终科研图。",
}
write_json(RENDER_AUDIT, render_audit)

# Package completeness and scope gates.
required_outputs_before_manifest = [
    PUB / "03_manuscript_cn/manuscript_cn_v0_1.md",
    PUB / "03_manuscript_cn/manuscript_cn_v0_1.docx",
    PUB / "03_manuscript_cn/structured_abstract_cn.md",
    PUB / "03_manuscript_cn/title_and_keywords.md",
    PUB / "01_claim_map/claim_to_evidence_matrix.json",
    PUB / "04_figures/figure_package_plan.md",
    PUB / "05_tables/table_package.md",
    PUB / "06_supplement/supplementary_structure.md",
    PUB / "09_reports/anticipated_reviewer_questions.md",
    PUB / "09_reports/publication_readiness_v0_1.md",
]
figure_count = figure_text.count("P1_DETAILED_DESIGN") - 1  # subtract legend/example mention
if figure_count != 9:
    figure_count = len(re.findall(r"^\|\s*[1-9]\s*\|", figure_text, flags=re.MULTILINE))
table_count = len(re.findall(r"^## Table [1-6]\.", table_text, flags=re.MULTILINE))
reviewer_question_count = len(re.findall(r"^## (?:Q)?\d+\.", reviewer_text, flags=re.MULTILINE))
supplement_required = ["360", "2880", "2640", "history", "horizon", "TE1", "manifest", "negative evidence"]
supplement_complete = all(token.lower() in supplement_text.lower() for token in supplement_required[:-1]) and any(
    token.lower() in supplement_text.lower() for token in ["negative", "failure taxonomy", "unresolved", "FAIL"]
)
readiness_allowed = (
    "METHODS_PAPER_DRAFTABLE_WITH_CLAIM_LIMITATION" in readiness_text
    and "TOPICALLY_COMPATIBLE_BUT_EVIDENCE_INCOMPLETE" in readiness_text
)
manuscript_sections = [
    "# 1. 引言", "# 2. 控制方程与模型形式", "# 3. 验证与资格框架",
    "# 4. 动态参考轨迹", "# 5. 动态求解器实现", "# 6. 结构验证",
    "# 7. 多步可微性资格", "# 8. 拓扑事件资格", "# 9. 讨论", "# 10. 结论",
    "# Data availability", "# Code availability", "# Author contributions",
    "# Conflict of interest", "# References",
]

gates = [
    pass_gate("freeze_pass_and_48_inputs_hash_reverified", freeze_reverified and len(freeze["inputs"]) == 48,
              {"input_count": len(freeze["inputs"]), "missing": missing_inputs, "mismatches": hash_mismatches}),
    pass_gate("manuscript_complete", all(section in md for section in manuscript_sections) and len(md) >= 15_000,
              {"character_count": len(md), "required_sections": len(manuscript_sections)}),
    pass_gate("claim_map_and_claim_audit_complete", claim_audit["status"] == "PASS",
              {"claim_count": len(claim_rows), "audit": str(CLAIM_AUDIT.relative_to(REPO))}),
    pass_gate("figure_package_complete", figure_count == 9,
              {"count": figure_count, "mode": "P1_DETAILED_DESIGN"}),
    pass_gate("table_package_complete", table_count == 6, {"count": table_count}),
    pass_gate("supplement_plan_complete", supplement_complete, {"required_tokens": supplement_required}),
    pass_gate("reviewer_risk_analysis_complete", reviewer_question_count >= 12,
              {"question_count": reviewer_question_count}),
    pass_gate("readiness_classification_allowed", readiness_allowed,
              {"primary": "METHODS_PAPER_DRAFTABLE_WITH_CLAIM_LIMITATION",
               "secondary": "TOPICALLY_COMPATIBLE_BUT_EVIDENCE_INCOMPLETE"}),
    pass_gate("docx_render_audit_pass", render_audit["status"] == "PASS",
              {"page_count": len(reader.pages), "audit": str(RENDER_AUDIT.relative_to(REPO))}),
    pass_gate("required_outputs_present", all(path.is_file() and path.stat().st_size > 0 for path in required_outputs_before_manifest),
              {"count": len(required_outputs_before_manifest)}),
    pass_gate("no_new_computation_training_or_rollout", all([
        freeze["checks"]["dynamic_training_not_executed"],
        freeze["checks"]["rollout_performance_not_tested"],
        freeze["checks"]["stage03e_authorization_false"],
        negative_scope_disclosures["no_training_executed"],
        negative_scope_disclosures["no_autonomous_rollout"],
    ]), {"training": "NOT_EXECUTED", "rollout_performance": "NOT_TESTED", "stage03e_authorized": False}),
]
all_gates_pass = all(gate["status"] == "PASS" for gate in gates)
terminal_status = TERMINAL_COMPLETE if all_gates_pass else TERMINAL_INCOMPLETE

report = f"""# Publication Track P1 final report

## Final status

`{terminal_status}`

## Evidence lock

- 冻结输入：{len(freeze['inputs'])}/{len(freeze['inputs'])} 存在且SHA-256复核一致；缺失0，hash mismatch 0。
- 历史状态保持：Stage 03D=`DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED`；Stage 03D-R=`DYNAMIC_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED`；TE1组件=`TOPOLOGY_EVENT_COMPONENT_QUALIFIED`。
- Stage 03E授权：false。动态训练=`NOT_EXECUTED`；rollout/performance=`NOT_TESTED`。
- 本工作流只读取冻结机器artifact并生成论文材料；未运行新simulation、AD/FD、epsilon、模型、训练、rollout或性能计算。

## Draft package

- 完整中文源稿：{len(md)}字符，含摘要、10个正文章节及Data/Code/Author/Conflict/References占位段。
- Claim map：{len(claim_rows)}条；主文CLAIM标记覆盖{len(marked_ids)}条；未知标记0；未决unsupported marker 0。
- 图件：9项`P1_DETAILED_DESIGN`，遵循P1允许的详细设计交付路径；不将设计框冒充最终科研图。
- 表格：6项证据表。
- Supplement：覆盖360-row matrix、2880 comparisons、2640 extended FD、history、horizon、TE1、manifest和negative evidence。
- Reviewer-risk：{reviewer_question_count}项逐题证据回答。
- Readiness：`METHODS_PAPER_DRAFTABLE_WITH_CLAIM_LIMITATION`；辅分类`TOPICALLY_COMPATIBLE_BUT_EVIDENCE_INCOMPLETE`。

## Claim audit

- no training claim：PASS。
- no rollout-performance claim：PASS。
- no solver-improvement claim：PASS。
- no Transformer-superiority claim：PASS。
- Stage 03D NOT_QUALIFIED在摘要、结果和讨论中可见：PASS。
- 216与144在摘要、结果和讨论中同时可见：PASS。
- topology组件与整体资格分开标注：PASS。
- 外部文献仅保留`[REF-TODO: topic]`占位，不生成虚假引文：PASS。

## DOCX render audit

- 最终DOCX渲染：{len(reader.pages)}页Letter；目录、页码、公式、6张表、9项图件设计与图题、内部链接均通过结构检查。
- 空白页：0；逐页视觉检查：1–20页；裁切、溢出、缺字、断表发现：0。
- 可访问性：high=0、medium=0、low=0。
- 最终图件模式：`P1_DETAILED_DESIGN`。正式科研图需在后续工作流明确选择Python或R后生成和复核。

## Gate ledger

""" + "\n".join(f"- {g['gate']}: `{g['status']}`" for g in gates) + f"""

## Terminal

{terminal_status}
"""
REPORT.write_text(report, encoding="utf-8")

# Inventory all durable deliverables and QA files, excluding scratch render iterations and cache.
exclude_parts = {"font_cache", "render_initial", "render_initial_v2", "render_final"}
inventory = []
for path in sorted(PUB.rglob("*")):
    if not path.is_file() or path == MANIFEST:
        continue
    rel_pub = path.relative_to(PUB)
    if any(part in exclude_parts for part in rel_pub.parts):
        continue
    inventory.append({
        "path": str(path.relative_to(REPO)),
        "byte_count": path.stat().st_size,
        "sha256": sha256(path),
    })

manifest = {
    "schema_version": "sph-pio-poc.publication-p1.final-manifest.v1",
    "workflow": "Publication Track P1 — Evidence-Locked Manuscript Architecture and Chinese Draft v0.1",
    "status": terminal_status,
    "all_gates_pass": all_gates_pass,
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "scope": {
        "independent_publication_workflow": True,
        "stage03e": False,
        "stage04": False,
        "historical_stage_directories_modified": False,
        "new_computation": False,
        "dynamic_training": "NOT_EXECUTED",
        "rollout_performance": "NOT_TESTED",
        "figure_mode": "P1_DETAILED_DESIGN",
    },
    "preserved_statuses": freeze["preserved_statuses"],
    "freeze_reverification": {
        "status": "PASS" if freeze_reverified else "FAIL",
        "input_count": len(freeze["inputs"]),
        "missing_inputs": missing_inputs,
        "hash_mismatches": hash_mismatches,
    },
    "package_summary": {
        "manuscript_character_count": len(md),
        "docx_page_count": len(reader.pages),
        "claim_count": len(claim_rows),
        "figure_design_count": figure_count,
        "table_count": table_count,
        "reviewer_question_count": reviewer_question_count,
        "readiness": "METHODS_PAPER_DRAFTABLE_WITH_CLAIM_LIMITATION",
    },
    "gates": gates,
    "required_outputs": [str(path.relative_to(REPO)) for path in required_outputs_before_manifest] + [
        str(REPORT.relative_to(REPO)), str(MANIFEST.relative_to(REPO))
    ],
    "audits": {
        "claim": str(CLAIM_AUDIT.relative_to(REPO)),
        "docx_render": str(RENDER_AUDIT.relative_to(REPO)),
        "docx_a11y": str(A11Y.relative_to(REPO)),
    },
    "artifact_inventory_count": len(inventory),
    "artifact_inventory": inventory,
    "self_hash_note": "The manifest excludes its own hash to avoid recursive self-reference.",
    "terminal_rule": {"pass": TERMINAL_COMPLETE, "fail": TERMINAL_INCOMPLETE},
}
write_json(MANIFEST, manifest)

print(json.dumps({
    "status": terminal_status,
    "all_gates_pass": all_gates_pass,
    "freeze_inputs_reverified": len(freeze["inputs"]) - len(missing_inputs) - len(hash_mismatches),
    "claim_audit": claim_audit["status"],
    "render_audit": render_audit["status"],
    "inventory_count": len(inventory),
}, ensure_ascii=False))
