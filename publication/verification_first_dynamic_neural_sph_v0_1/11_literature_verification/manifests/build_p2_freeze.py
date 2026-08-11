#!/usr/bin/env python3
"""Build the Publication P2 input-freeze manifest without mutating P1 inputs."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
P1 = ROOT / "publication/verification_first_dynamic_neural_sph_v0_1"
P2 = P1 / "11_literature_verification"
P1_FINAL = P1 / "10_manifests/publication_p1_final_manifest.json"
S3_FINAL = ROOT / "stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03ds_final_manifest.json"

REQUIRED = [
    "publication/verification_first_dynamic_neural_sph_v0_1/03_manuscript_cn/manuscript_cn_v0_1.md",
    "publication/verification_first_dynamic_neural_sph_v0_1/03_manuscript_cn/manuscript_cn_v0_1.docx",
    "publication/verification_first_dynamic_neural_sph_v0_1/03_manuscript_cn/structured_abstract_cn.md",
    "publication/verification_first_dynamic_neural_sph_v0_1/03_manuscript_cn/title_and_keywords.md",
    "publication/verification_first_dynamic_neural_sph_v0_1/01_claim_map/claim_to_evidence_matrix.json",
    "publication/verification_first_dynamic_neural_sph_v0_1/04_figures/figure_package_plan.md",
    "publication/verification_first_dynamic_neural_sph_v0_1/05_tables/table_package.md",
    "publication/verification_first_dynamic_neural_sph_v0_1/06_supplement/supplementary_structure.md",
    "publication/verification_first_dynamic_neural_sph_v0_1/09_reports/anticipated_reviewer_questions.md",
    "publication/verification_first_dynamic_neural_sph_v0_1/09_reports/publication_readiness_v0_1.md",
    "publication/verification_first_dynamic_neural_sph_v0_1/09_reports/publication_p1_final_report.md",
    "publication/verification_first_dynamic_neural_sph_v0_1/10_manifests/publication_p1_final_manifest.json",
    "stage_03_Dynamic_SPH_Transformer_Hybrid/08_route_closure/claim_boundary/stage03ds_claim_boundary.json",
    "stage_03_Dynamic_SPH_Transformer_Hybrid/08_route_closure/evidence_matrix/stage03ds_dynamic_evidence_matrix.json",
    "stage_03_Dynamic_SPH_Transformer_Hybrid/09_reports/stage03ds_manuscript_framework.md",
    "stage_03_Dynamic_SPH_Transformer_Hybrid/09_reports/stage03ds_manuscript_readiness.md",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def inventory_index(manifest: dict) -> dict[str, str]:
    return {row["path"]: row["sha256"] for row in manifest.get("artifact_inventory", [])}


def main() -> None:
    p1 = json.loads(P1_FINAL.read_text(encoding="utf-8"))
    s3 = json.loads(S3_FINAL.read_text(encoding="utf-8"))
    p1_hashes = inventory_index(p1)
    s3_hashes = inventory_index(s3)
    missing: list[str] = []
    mismatches: list[dict] = []
    inputs: list[dict] = []
    for rel in REQUIRED:
        path = ROOT / rel
        if not path.exists():
            missing.append(rel)
            continue
        actual = sha256(path)
        expected = p1_hashes.get(rel) or s3_hashes.get(rel)
        comparison = "MATCH" if expected == actual else ("NO_LEDGER_ENTRY" if expected is None else "MISMATCH")
        if comparison == "MISMATCH":
            mismatches.append({"path": rel, "expected": expected, "actual": actual})
        inputs.append({
            "path": rel,
            "byte_count": path.stat().st_size,
            "sha256": actual,
            "expected_sha256": expected,
            "hash_check": comparison,
            "mode": "READ_ONLY_P2_INPUT",
        })

    claim_audit = json.loads((P1 / "08_claim_audit/publication_p1_claim_audit.json").read_text(encoding="utf-8"))
    stage_claims = json.loads((ROOT / REQUIRED[12]).read_text(encoding="utf-8")) if not missing else {}
    unsupported = stage_claims.get("unsupported_claims", [])
    statuses = p1.get("preserved_statuses", {})
    gates = {
        "p1_manifest_status_complete": p1.get("status") == "PUBLICATION_EVIDENCE_LOCK_AND_DRAFT_V01_COMPLETE",
        "p1_all_gates_pass": p1.get("all_gates_pass") is True,
        "required_inputs_complete": not missing,
        "historical_hashes_unchanged": not mismatches,
        "unsupported_statements_parseable": isinstance(unsupported, list) and all(isinstance(x, dict) for x in unsupported),
        "p1_unsupported_markers_parseable": isinstance(claim_audit.get("unsupported_markers"), list),
        "stage03e_authorization_false": statuses.get("stage03e_authorization") is False,
        "training_not_executed": statuses.get("dynamic_training") == "NOT_EXECUTED",
        "rollout_performance_not_executed": statuses.get("rollout_performance") in {"NOT_TESTED", "NOT_EXECUTED"},
    }
    passed = all(gates.values())
    out = {
        "schema_version": "sph-pio-poc.publication-p2.input-freeze.v1",
        "workflow": "Publication Track P2 — Literature Verification and Scientific Positioning",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "search_cutoff_date": "2026-08-05",
        "status": "PASS" if passed else "PUBLICATION_LITERATURE_POSITIONING_EVIDENCE_INCOMPLETE",
        "source_p1_status": p1.get("status"),
        "gates": gates,
        "required_input_count": len(REQUIRED),
        "verified_input_count": len(inputs),
        "missing_inputs": missing,
        "hash_mismatches": mismatches,
        "unsupported_statement_count": len(unsupported),
        "unsupported_statements": unsupported,
        "preserved_statuses": statuses,
        "scope": {
            "stage03e_authorization": False,
            "dynamic_training": "NOT_EXECUTED",
            "rollout_performance": "NOT_TESTED",
            "new_numerical_work": False,
            "p1_files_mutated": False,
        },
        "inputs": inputs,
    }
    target = P2 / "freeze/p2_input_freeze_manifest.json"
    target.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"target": str(target), "status": out["status"], "gates": gates}, ensure_ascii=False, indent=2))
    if not passed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
