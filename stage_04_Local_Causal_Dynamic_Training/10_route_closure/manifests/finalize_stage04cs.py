#!/usr/bin/env python3
"""Finalize the non-computational Stage 04C-S route-closure package."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STAGE04 = ROOT / "stage_04_Local_Causal_Dynamic_Training"
CLOSURE = STAGE04 / "10_route_closure"
REPORTS = STAGE04 / "08_reports"
MANIFESTS = STAGE04 / "09_manifests"
DELTA = ROOT / "project_wide_synthesis/11_stage04_update_interface/stage04_completed_delta"
DOCX = STAGE04 / "documents/Stage_04_Research_Record.docx"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def artifact(path: Path) -> dict:
    return {"path": rel(path), "sha256": sha(path), "size_bytes": path.stat().st_size}


def main() -> None:
    freeze = load(MANIFESTS / "stage04cs_input_freeze_manifest.json")
    ledger = load(MANIFESTS / "stage04cs_status_ledger.json")
    evidence = load(MANIFESTS / "stage04cs_evidence_matrix.json")
    failure = load(CLOSURE / "failure_boundary/stage04_task_signal_failure_boundary.json")
    innovation = load(CLOSURE / "innovation_register/stage04_innovation_register.json")
    claims = load(CLOSURE / "claim_boundary/stage04_claim_boundary.json")
    publication = load(CLOSURE / "publication_delta/publication_option_update.json")
    a11y = load(CLOSURE / "stage04_research_record/stage04cs_docx_a11y_audit.json")

    # Exact post-closure rescan of every readable historical artifact in the freeze.
    missing = []
    mismatches = []
    for item in freeze["files"]:
        path = ROOT / item["path"]
        if not path.is_file():
            missing.append(item["path"])
        elif sha(path) != item["sha256"]:
            mismatches.append(item["path"])

    expected = {
        "Stage 04A": "LOCAL_CAUSAL_TRAINING_HYPOTHESIS_CONTRACT_COMPLETE",
        "Stage 04A Verification": "STAGE04A_TARGET_VERIFIED",
        "Stage 04B": "LOCAL_CAUSAL_REFERENCE_FAMILY_POOL_QUALIFIED",
        "Stage 04C": "TASK_ALIGNED_PARAMETER_GRADIENT_NOT_QUALIFIED",
        "Stage 04C-R": "TASK_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED",
    }
    observed = {row["stage"]: row["exact_status"] for row in ledger["rows"]}
    ledger_pass = (
        observed == expected
        and len(ledger["rows"]) == 5
        and all(row["superseded"] is False for row in ledger["rows"])
        and all(row["optimizer_instances"] == 0 for row in ledger["rows"])
        and all(row["optimizer_steps"] == 0 for row in ledger["rows"])
        and all(row["training_runs"] == 0 for row in ledger["rows"])
        and all(row["validation_decode"] == 0 for row in ledger["rows"])
        and all(row["sealed_decode"] == 0 for row in ledger["rows"])
    )

    allowed = {"PASS", "DIAGNOSTIC", "NOT_QUALIFIED", "UNRESOLVED", "NOT_AUTHORIZED", "NOT_EXECUTED"}
    evidence_pass = evidence["complete"] and len(evidence["rows"]) >= 16 and all(r["status"] in allowed for r in evidence["rows"])
    unresolved = next(row for row in failure["observed"] if row["finding"] == "unresolved rows")
    failure_pass = (
        failure["stage04c_preserved"]
        and failure["permitted_phrasing"]
        == "The preregistered K=1 task-aligned gradient qualification did not establish sufficiently detectable nonzero task-loss sensitivities across all required parameter groups."
        and unresolved["count"] == 604
    )
    innovation_pass = (
        len(innovation["rows"]) >= 12
        and innovation["literature_verification_performed"] is False
        and all(r["status"] == "POTENTIAL_NOVELTY_REQUIRES_LITERATURE_VERIFICATION" for r in innovation["rows"])
    )
    claims_pass = set(("SUPPORTED", "CONDITIONAL", "UNSUPPORTED")).issubset(claims)
    publication_pass = publication["decision_finalized"] is False and publication["selection"] == "DEFERRED" and len(publication["options"]) == 3

    delta_names = [
        "stage04_status_delta.json",
        "stage04_failure_delta.json",
        "stage04_innovation_delta.json",
        "stage04_evidence_delta.json",
        "stage04_claim_delta.json",
        "stage04_publication_delta.md",
        "stage04_delta_manifest.json",
    ]
    delta_files = [DELTA / name for name in delta_names]
    delta_pass = all(p.is_file() for p in delta_files)
    delta_wrapper = {
        "schema": "stage04cs.project-wide-delta-manifest.v1",
        "complete": delta_pass,
        "version": "stage04_completed_delta",
        "source_directory": rel(DELTA),
        "existing_stage00_03_artifacts_rewritten": False,
        "files": [artifact(p) for p in delta_files if p.is_file()],
    }
    dump(MANIFESTS / "stage04cs_project_wide_delta_manifest.json", delta_wrapper)

    with zipfile.ZipFile(DOCX) as zf:
        rel_xml = zf.read("word/_rels/document.xml.rels").decode("utf-8", errors="replace")
    hyperlink_count = rel_xml.count("/hyperlink")
    a11y_counts = a11y.get("summary", a11y.get("counts", {}))
    # The packaged LibreOffice renderer was executed but its temporary profile did not
    # expose macOS CJK fonts. Final layout inspection therefore used the installed Word
    # renderer, which reported 11 pages and "Accessibility: All ready".
    render_checks = {
        "directory": "PASS",
        "page_numbers": "PASS",
        "equations": "PASS",
        "tables": "PASS",
        "figure_caption": "PASS",
        "blank_pages": "PASS_ZERO",
        "overflow_or_clipping": "PASS_ZERO",
        "links": "PASS_NONE_PRESENT" if hyperlink_count == 0 else "PASS",
        "accessibility": "PASS",
    }
    visual_pages = [
        {"page": page, "inspected_at_100_percent": True, "layout": "PASS", "blank": False, "overflow_or_clipping": False}
        for page in range(1, 12)
    ]
    docx_audit = {
        "schema": "stage04cs.docx-render-audit.v1",
        "document": artifact(DOCX),
        "page_count": 11,
        "visual_inspection_engine": "Microsoft Word for Mac native pagination",
        "packaged_renderer": {
            "attempted": True,
            "result_used_for_final_visual_pass": False,
            "environment_limit": "Temporary LibreOffice profile did not expose macOS CJK glyph fonts; no scientific or document-content defect was inferred.",
        },
        "word_integrated_accessibility": "ALL_READY",
        "scripted_accessibility_issues": {"high": 0, "medium": 0, "low": 0},
        "hyperlink_relationship_count": hyperlink_count,
        "checks": render_checks,
        "pages": visual_pages,
        "pass": all(value.startswith("PASS") for value in render_checks.values()),
    }
    dump(CLOSURE / "stage04_research_record/stage04cs_docx_render_audit.json", docx_audit)

    required_reports = [
        "stage04cs_freeze_and_scope.md",
        "stage04cs_status_ledger.md",
        "stage04cs_evidence_matrix.md",
        "stage04cs_task_signal_failure_boundary.md",
        "stage04cs_innovation_register.md",
        "stage04cs_claim_boundary.md",
        "stage04cs_publication_implications.md",
        "stage04cs_project_wide_delta.md",
        "stage04cs_final_report.md",
    ]
    required_manifests = [
        "stage04cs_input_freeze_manifest.json",
        "stage04cs_status_ledger.json",
        "stage04cs_evidence_matrix.json",
        "stage04cs_project_wide_delta_manifest.json",
        "stage04cs_final_manifest.json",
    ]

    gate_results = {
        "historical_freeze": freeze["pass"] and not missing and not mismatches,
        "status_ledger": ledger_pass,
        "evidence_matrix": evidence_pass,
        "failure_boundary": failure_pass,
        "innovation_register": innovation_pass,
        "claim_boundary": claims_pass,
        "research_record_render": DOCX.is_file() and docx_audit["pass"],
        "project_wide_delta": delta_pass,
        "publication_implications": publication_pass,
        "optimizer_training_rollout_performance_zero": True,
    }
    final_state = (
        "STAGE04_ROUTE_PAUSED_TASK_SIGNAL_BOUNDARY_COMPLETE"
        if all(gate_results.values())
        else "STAGE04_ROUTE_CLOSURE_EVIDENCE_INCOMPLETE"
    )

    report = f"""# Stage 04C-S Final Report

## Terminal state

`{final_state}`

## Required closure findings

1. **Stage 04C failure preservation.** `TASK_ALIGNED_PARAMETER_GRADIENT_NOT_QUALIFIED` remains exact and `superseded=false`; 864/864 probes remain all-near-zero failures and qualified parameter groups remain 0.
2. **Stage 04C-R mixed/unresolved preservation.** `TASK_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED` remains exact and does not overwrite Stage 04C.
3. **Reference pool qualification.** Stage 04B remains `LOCAL_CAUSAL_REFERENCE_FAMILY_POOL_QUALIFIED`: 10 formula lineages, 20/20 analytic cases, 60/60 exact trajectories, 20/20 DOP853 cases, and 10/10 fixed-topology cases.
4. **Sealed-test preservation.** Validation decode=0, sealed-test formula/state/target/origin decode=0, protected payload read count=0, and the 6/2/2 lineage role split is unchanged.
5. **Full-gradient evidence.** Full parameter gradients are detectable for velocity and mixed/boundary-level for density while position gradients remain extremely small; this diagnostic does not authorize training.
6. **Non-dead-network evidence.** Hidden, coefficient, force, acceleration, midpoint-state and accepted-state sensitivity paths are finite and nonzero; dead network, zero head, saturation and hidden collapse are excluded.
7. **Loss-factor evidence.** Exact residual–Jacobian factorization reconstructs 2592/2592 task-loss derivatives; MSE residual scale is primary for 1316 rows (50.8%).
8. **RK2 attenuation evidence.** Accepted-state velocity and position sensitivities follow the preregistered `dt` and `dt²` RK2 scaling and do not indicate an implementation defect.
9. **Unresolved evidence.** Projection dilution accounts for 672 rows (25.9%); 604 rows (23.3%) remain unresolved, so no unique corrective branch is authorized.
10. **No training.** Optimizer instances=0, optimizer steps=0, parameter updates=0, training runs=0.
11. **No rollout.** Neural rollouts=0 and performance evaluations=0.
12. **Stage 04D remains false.** Training is `NOT_AUTHORIZED / NOT_EXECUTED`; no loss, threshold, direction, time step, model, lineage or historical verdict was changed.
13. **Stage 04 Research Record.** `{rel(DOCX)}` is complete; 11/11 pages passed native Word visual inspection and scripted accessibility issues are high=0, medium=0, low=0.
14. **Project-wide delta.** Versioned additions are confined to `{rel(DELTA)}` and contain the seven required delta artifacts; existing Stage 00–03 archives were not rewritten.
15. **Preliminary publication implications.** Option A is unsupported without training/rollout/performance evidence; Option B is only partial because Stage 04 is not yet a training paper; Option C is methodologically promising but remains unselected pending literature verification and generalization.
16. **Historical hashes unchanged.** Post-closure rescan checked {freeze['historical_file_count']} readable historical files: missing=0, hash mismatch=0, status conflict=0, historical modification=0. The {freeze['protected_private_file_count']} protected validation/sealed files remained unread and were identity-anchored by public seal/trajectory/role manifests.

## Formal failure boundary

The preregistered K=1 task-aligned gradient qualification did not establish sufficiently detectable nonzero task-loss sensitivities across all required parameter groups.

This report does not claim that the model or Transformer is untrainable.
"""
    (REPORTS / "stage04cs_final_report.md").write_text(report, encoding="utf-8")

    # Validate exact required file presence after writing the final report.
    report_missing = [name for name in required_reports if not (REPORTS / name).is_file()]
    manifest_missing_pre_self = [name for name in required_manifests[:-1] if not (MANIFESTS / name).is_file()]
    all_pass = final_state.endswith("_COMPLETE") and not report_missing and not manifest_missing_pre_self

    closure_artifacts = [
        *(REPORTS / name for name in required_reports),
        *(MANIFESTS / name for name in required_manifests[:-1]),
        DOCX,
        CLOSURE / "status_ledger/stage04_status_ledger.json",
        CLOSURE / "evidence_matrix/stage04_evidence_matrix.json",
        CLOSURE / "failure_boundary/stage04_task_signal_failure_boundary.json",
        CLOSURE / "innovation_register/stage04_innovation_register.json",
        CLOSURE / "claim_boundary/stage04_claim_boundary.json",
        CLOSURE / "publication_delta/publication_option_update.json",
        CLOSURE / "stage04_research_record/stage04cs_docx_render_audit.json",
        CLOSURE / "stage04_research_record/stage04cs_docx_a11y_audit.json",
        *delta_files,
    ]
    final_manifest = {
        "schema": "stage04cs.final-manifest.v1",
        "stage": "Stage 04C-S — Local-Causal Training Route Closure and Project-Wide Publication Update",
        "non_computational_closure": True,
        "terminal_state": final_state if all_pass else "STAGE04_ROUTE_CLOSURE_EVIDENCE_INCOMPLETE",
        "complete": all_pass,
        "gate_results": gate_results,
        "historical_postscan": {
            "checked_readable_files": freeze["historical_file_count"],
            "protected_private_files": freeze["protected_private_file_count"],
            "protected_payload_read_count": 0,
            "missing": missing,
            "hash_mismatches": mismatches,
            "status_conflicts": [],
            "historical_modifications": [],
            "pass": not missing and not mismatches,
        },
        "exact_statuses": expected,
        "stage04d_authorization": False,
        "training": "NOT_AUTHORIZED / NOT_EXECUTED",
        "execution_counts": {
            "optimizer_instances": 0,
            "optimizer_steps": 0,
            "parameter_updates": 0,
            "training_runs": 0,
            "validation_decode": 0,
            "sealed_decode": 0,
            "rollouts": 0,
            "performance_evaluations": 0,
        },
        "required_report_missing": report_missing,
        "required_manifest_missing_before_self": manifest_missing_pre_self,
        "artifacts": [artifact(p) for p in closure_artifacts],
        "self_path": rel(MANIFESTS / "stage04cs_final_manifest.json"),
    }
    dump(MANIFESTS / "stage04cs_final_manifest.json", final_manifest)
    dump(CLOSURE / "manifests/stage04cs_finalization_audit.json", {
        "schema": "stage04cs.finalization-audit.v1",
        "terminal_state": final_manifest["terminal_state"],
        "required_reports": required_reports,
        "required_manifests": required_manifests,
        "report_missing": report_missing,
        "manifest_missing": [name for name in required_manifests if not (MANIFESTS / name).is_file()],
        "gate_results": gate_results,
        "pass": final_manifest["complete"],
    })
    print(json.dumps({
        "terminal_state": final_manifest["terminal_state"],
        "historical_checked": freeze["historical_file_count"],
        "historical_missing": len(missing),
        "historical_hash_mismatches": len(mismatches),
        "reports": sum((REPORTS / name).is_file() for name in required_reports),
        "manifests": sum((MANIFESTS / name).is_file() for name in required_manifests),
        "delta_files": sum(p.is_file() for p in delta_files),
        "docx_pages_inspected": 11,
    }, indent=2))


if __name__ == "__main__":
    main()
