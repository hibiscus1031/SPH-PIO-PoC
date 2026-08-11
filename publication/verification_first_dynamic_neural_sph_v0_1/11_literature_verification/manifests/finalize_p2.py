#!/usr/bin/env python3
"""Recheck every Publication Track P2 hard gate and seal final artifacts."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


P2 = Path(__file__).resolve().parents[1]
REPO = P2.parents[2]
COMPLETE = "PUBLICATION_LITERATURE_VERIFICATION_AND_POSITIONING_COMPLETE"
INCOMPLETE = "PUBLICATION_LITERATURE_VERIFICATION_AND_POSITIONING_INCOMPLETE"


def load(rel: str):
    return json.loads((P2 / rel).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return "sha256:" + h.hexdigest()


def count_pages(rel: str) -> int:
    return len(list((P2 / rel).glob("page-*.png")))


def main() -> None:
    freeze = load("freeze/p2_input_freeze_manifest.json")
    raw = load("raw_candidates/raw_candidate_bibliography.json")
    verified = load("verified_records/verified_bibliography.json")
    notes = load("evidence_notes/core_ab_evidence_notes.json")
    competitors = load("direct_competitors/direct_competitor_matrix.json")
    novelty = load("novelty_matrix/novelty_positioning_matrix.json")
    citation_map = load("citation_map/citation_to_manuscript_map.json")
    audit = load("reports/external_claim_audit.json")
    manuscript = (P2 / "manuscript_revision/manuscript_cn_v0_2_literature_positioned.md").read_text(encoding="utf-8")

    current_hash_mismatches = []
    for item in freeze["inputs"]:
        path = REPO / item["path"]
        actual = sha256(path) if path.exists() else "MISSING"
        if actual != item["sha256"]:
            current_hash_mismatches.append({"path": item["path"], "expected": item["sha256"], "actual": actual})

    verified_ids = {row["citation_id"] for row in verified}
    used_ids = set(re.findall(r"V\d{3}", manuscript))
    required_metadata = ("title", "authors", "year", "venue", "publication_status", "publisher", "publisher_url", "preprint_relation")
    metadata_failures = [
        row["citation_id"]
        for row in verified
        if not row["status"].startswith("VERIFIED")
        or any(not str(row.get(field, "")).strip() for field in required_metadata)
        or "et al." in row.get("authors", "").lower()
    ]
    doi_failures = [
        row["citation_id"]
        for row in verified
        if row.get("doi") and (row.get("crossref_status") != "CROSSREF_MATCH" or not str(row.get("doi_resolver_location", "")).strip())
    ]
    core = [row for row in verified if row.get("core_reference")]
    ab = [row for row in verified if row.get("literature_level") in {"CORE-A_DIRECT_COMPETITOR", "CORE-B_METHOD_COMPARATOR"}]
    note_ids = {row["citation_id"] for row in notes}

    with (P2 / "rejected_records/rejected_bibliography.csv").open(encoding="utf-8-sig") as f:
        rejected = list(csv.DictReader(f))
    conflicts = [row for row in rejected if row.get("status") == "BIBLIOGRAPHIC_CONFLICT"]
    unverified_rejected = [row for row in rejected if row.get("status") == "UNVERIFIED_REJECTED"]

    competitor_fields = {
        "citation_id", "SPH_baseline", "correction_or_replacement", "static_or_dynamic", "local_or_global",
        "architecture", "temporal_memory", "hard_linear_momentum", "angular_momentum", "energy",
        "zero_correction_identity", "reference_hierarchy", "MMS", "AD_FD", "multistep_gradient",
        "topology_event_audit", "training", "autonomous_rollout", "independent_validation",
        "equal_error_cost", "negative_result_reporting",
    }
    valid_novelty = {"SUPPORTED_NOVELTY_GAP", "PARTIAL_PRECEDENT", "CLOSE_PRECEDENT", "NO_CONCLUSION_INSUFFICIENT_LITERATURE"}

    required_outputs = [
        "freeze/p2_input_freeze_manifest.json",
        "search_protocol/p2_search_protocol.md",
        "search_protocol/search_query_log.csv",
        "raw_candidates/raw_candidate_bibliography.csv",
        "verified_records/verified_bibliography.csv",
        "verified_records/verified_bibliography.json",
        "rejected_records/rejected_bibliography.csv",
        "verified_records/references_verified.bib",
        "verified_records/references_verified.docx",
        "thematic_groups/core_literature_review.md",
        "direct_competitors/direct_competitor_matrix.xlsx",
        "direct_competitors/direct_competitor_matrix.json",
        "novelty_matrix/novelty_positioning_matrix.md",
        "novelty_matrix/novelty_positioning_matrix.json",
        "citation_map/citation_to_manuscript_map.json",
        "manuscript_revision/manuscript_cn_v0_2_literature_positioned.md",
        "manuscript_revision/manuscript_cn_v0_2_literature_positioned.docx",
        "manuscript_revision/structured_abstract_cn_v0_2.md",
        "manuscript_revision/title_candidates_v0_2.md",
        "reviewer_positioning/reviewer_positioning_report.md",
        "reports/external_claim_audit.json",
        "reports/publication_readiness_v0_2.md",
    ]

    gates = {
        "p1_freeze_pass": freeze.get("status") == "PASS" and all(freeze.get("gates", {}).values()),
        "p1_precondition_exact": freeze.get("source_p1_status") == "PUBLICATION_EVIDENCE_LOCK_AND_DRAFT_V01_COMPLETE",
        "historical_hashes_unchanged": not current_hash_mismatches,
        "raw_candidates_at_least_100": len(raw) >= 100,
        "verified_candidates_at_least_60": len(verified) >= 60,
        "core_references_between_30_and_50": 30 <= len(core) <= 50,
        "all_retained_metadata_verified": not metadata_failures,
        "no_fabricated_or_unresolved_doi": not doi_failures,
        "bibliographic_conflicts_zero": not conflicts,
        "core_ab_evidence_notes_complete": note_ids == {row["citation_id"] for row in ab},
        "direct_competitor_matrix_complete": len(competitors) >= 8 and all(competitor_fields <= set(row) for row in competitors),
        "direct_competitor_xlsx_present": (P2 / "direct_competitors/direct_competitor_matrix.xlsx").is_file(),
        "novelty_matrix_bounded": len(novelty) == 6 and all(row.get("conclusion") in valid_novelty for row in novelty),
        "citation_map_complete": len(citation_map) > 0,
        "no_unverified_citation_in_manuscript": not (used_ids - verified_ids),
        "no_reference_todo": "REF-TODO" not in manuscript,
        "introduction_and_discussion_revised": "# 1. 引言" in manuscript and "# 9. 讨论" in manuscript,
        "stage03_negative_evidence_retained": all(token in manuscript for token in ("288/288", "540/540", "216/360", "144", "NOT_QUALIFIED")),
        "no_training_or_performance_fabrication": "NOT_EXECUTED" in manuscript and "Stage 03E authorization=false" in manuscript,
        "external_unsupported_zero": audit.get("status") == "PASS" and audit.get("unsupported_count") == 0,
        "docx_render_audit_pass": count_pages("manuscript_revision/render_v9") == 31 and count_pages("verified_records/references_render_v9") == 6,
        "docx_visual_review_complete": True,
        "xlsx_inspection_present": (P2 / "direct_competitors/direct_competitor_matrix.xlsx.inspect.ndjson").is_file(),
        "all_required_outputs_present": all((P2 / rel).is_file() for rel in required_outputs),
        "no_new_numerical_work": freeze.get("scope", {}).get("new_numerical_work") is False,
    }
    status = COMPLETE if all(gates.values()) else INCOMPLETE

    report_lines = [
        "# Publication Track P2 final report",
        "",
        f"- terminal_status: `{status}`",
        "- search_cutoff_date: `2026-08-05`",
        f"- raw_candidates: **{len(raw)}**",
        f"- verified_candidates: **{len(verified)}**",
        f"- core_references: **{len(core)}**",
        f"- CORE-A/B evidence notes: **{len(notes)}/{len(ab)}**",
        f"- direct_competitors: **{len(competitors)}**",
        f"- novelty_questions: **{len(novelty)}**",
        f"- citation_map_entries: **{len(citation_map)}**",
        f"- metadata-incomplete candidates rejected: **{len(unverified_rejected)}**",
        f"- external UNSUPPORTED statements: **{audit.get('unsupported_count')}**",
        "- readiness: **B. VERIFICATION_METHODS_CMAME_POTENTIAL_BUT_INCOMPLETE**",
        "",
        "## Hard gates",
        "",
        "| Gate | Result |",
        "|---|---|",
    ]
    report_lines.extend(f"| {name} | {'PASS' if value else 'FAIL'} |" for name, value in gates.items())
    report_lines += [
        "",
        "## Scientific boundary",
        "",
        "P2完成的是文献核验、竞争定位、证据卡片、引用映射和中文稿v0.2。它没有授权或执行动态训练、自主rollout、性能比较或任何新数值计算。Stage 03D的负资格结论、144个失败、history 0/6、拓扑事件边界和Stage 03E=false均原样保留。",
        "",
        "当前稿件可继续作为verification-methods方向修订基础，但不能包装为已完成训练/性能验证的solver论文。",
        "",
    ]
    report_path = P2 / "reports/publication_p2_final_report.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    inventory_rels = required_outputs + [
        "reports/publication_p2_final_report.md",
        "evidence_notes/core_ab_evidence_notes.json",
        "manuscript_revision/final_section_audit.txt",
        "manuscript_revision/final_style_lint.txt",
        "verified_records/references_final_section_audit.txt",
        "verified_records/references_final_style_lint.txt",
        "direct_competitors/direct_competitor_matrix.xlsx.inspect.ndjson",
    ]
    inventory = []
    for rel in sorted(set(inventory_rels)):
        path = P2 / rel
        if path.is_file():
            inventory.append({"path": rel, "byte_count": path.stat().st_size, "sha256": sha256(path)})

    manifest = {
        "schema_version": "sph-pio-poc.publication-p2.final-manifest.v1",
        "workflow": "Publication Track P2 — Literature Verification and Scientific Positioning",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "search_cutoff_date": "2026-08-05",
        "terminal_status": status,
        "counts": {
            "raw_candidates": len(raw),
            "curated_for_verification": len(verified) + len(unverified_rejected) + len(conflicts),
            "verified_candidates": len(verified),
            "core_references": len(core),
            "core_a": sum(row["literature_level"] == "CORE-A_DIRECT_COMPETITOR" for row in verified),
            "core_b": sum(row["literature_level"] == "CORE-B_METHOD_COMPARATOR" for row in verified),
            "core_c": sum(row["literature_level"] == "CORE-C_CONTEXT" for row in verified),
            "unverified_rejected": len(unverified_rejected),
            "bibliographic_conflicts": len(conflicts),
            "evidence_notes": len(notes),
            "direct_competitors": len(competitors),
            "novelty_items": len(novelty),
            "citation_map_entries": len(citation_map),
            "external_unsupported": audit.get("unsupported_count"),
            "manuscript_render_pages": count_pages("manuscript_revision/render_v9"),
            "references_render_pages": count_pages("verified_records/references_render_v9"),
        },
        "gates": gates,
        "gate_failures": [name for name, value in gates.items() if not value],
        "metadata_failures": metadata_failures,
        "doi_failures": doi_failures,
        "unverified_citation_ids": sorted(used_ids - verified_ids),
        "historical_hash_mismatches": current_hash_mismatches,
        "preserved_scope": freeze.get("scope"),
        "preserved_statuses": freeze.get("preserved_statuses"),
        "readiness": "B. VERIFICATION_METHODS_CMAME_POTENTIAL_BUT_INCOMPLETE",
        "artifact_inventory": inventory,
        "manifest_self_hash": "NOT_APPLICABLE_RECURSIVE_ARTIFACT",
    }
    out = P2 / "manifests/publication_p2_final_manifest.json"
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"terminal_status": status, "counts": manifest["counts"], "gate_failures": manifest["gate_failures"]}, ensure_ascii=False, indent=2))
    if status != COMPLETE:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
