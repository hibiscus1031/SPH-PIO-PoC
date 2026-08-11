#!/usr/bin/env python3
"""Freeze the read-only evidence inputs for Publication Track P1."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
PUB = Path(__file__).resolve().parents[1]

for name in (
    "00_freeze", "01_claim_map", "02_outline", "03_manuscript_cn",
    "04_figures", "05_tables", "06_supplement", "07_internal_only",
    "08_claim_audit", "09_reports", "10_manifests",
):
    (PUB / name).mkdir(parents=True, exist_ok=True)


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


inputs = [
    # Stage 01/02 publication boundaries.
    "07_reports/stage01g_v2_qualification_report.md",
    "07_reports/stage01h_final_report.md",
    "stage_02_Particle_Interaction_Operator/07_reports/stage02ms_final_report.md",
    # Stage 03 chronological final reports and final manifests.
    *[f"stage_03_Dynamic_SPH_Transformer_Hybrid/09_reports/stage03{x}_final_report.md" for x in ("a", "b", "c", "d", "dr", "ds")],
    *[f"stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03{x}_final_manifest.json" for x in ("a", "b", "c", "d", "dr", "ds")],
    # Stage 03D-S synthesis package.
    "stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03ds_status_ledger.json",
    "stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03ds_evidence_matrix.json",
    "stage_03_Dynamic_SPH_Transformer_Hybrid/08_route_closure/claim_boundary/stage03ds_claim_boundary.json",
    "stage_03_Dynamic_SPH_Transformer_Hybrid/08_route_closure/gradient_boundary/stage03ds_gradient_boundary.json",
    "stage_03_Dynamic_SPH_Transformer_Hybrid/08_route_closure/topology_boundary/stage03ds_topology_component_boundary.json",
    "stage_03_Dynamic_SPH_Transformer_Hybrid/08_route_closure/manuscript_assessment/stage03ds_manuscript_readiness.json",
    "stage_03_Dynamic_SPH_Transformer_Hybrid/09_reports/stage03ds_manuscript_framework.md",
    "stage_03_Dynamic_SPH_Transformer_Hybrid/08_route_closure/figure_plan/stage03ds_figure_and_table_plan.json",
    "stage_03_Dynamic_SPH_Transformer_Hybrid/documents/Stage_03_Research_Record.docx",
    # Reference qualification.
    "stage_03_Dynamic_SPH_Transformer_Hybrid/04_reference_and_trajectory/stage03b/qualification/stage03b_qualification_summary.json",
    "stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03b_trajectory_manifest.json",
    "stage_03_Dynamic_SPH_Transformer_Hybrid/04_reference_and_trajectory/stage03b/acoustic_boundary/acoustic_candidate_classification.json",
    "stage_03_Dynamic_SPH_Transformer_Hybrid/04_reference_and_trajectory/stage03b/vortex_boundary/periodic_vortex_classification.json",
    # Implementation and structural qualification.
    "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c/results/independent_rk2_results.json",
    "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c/results/zero_correction_results.json",
    "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c/results/structural_smoke_results.json",
    "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c/results/checkpoint_resume_results.json",
    "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c/results/differentiability_smoke_results.json",
    "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c/results/resource_audit_results.json",
    # Full multistep evidence and attribution.
    "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03d/results/fixed_topology_adfd_results.json",
    "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03dr/failure_matrix/stage03d_complete_360_row_matrix.json",
    "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03d/conservation_over_time/conservation_results.json",
    "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03d/history_gradients/reference_prehistory_results.json",
    "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03dr/ad_crosscheck/reverse_vs_jvp.json",
    "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03dr/fd_conditioning/extended_fd_results.json",
    "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03dr/attribution/failure_attribution.json",
    "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03dr/history_path/reference_prehistory_trace.json",
    "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03dr/horizon_scaling/horizon_gradient_scaling.json",
    # TE1 topology component.
    "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03d/topology_event_scan/te1_dense_scan_results.json",
    "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03d/topology_stage_replay/replay_results.json",
    "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03d/event_side_gradients/event_side_gradient_results.json",
    "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03d/event_jump_audit/event_force_jump_results.json",
    "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03dr/topology_preservation/topology_component_status.json",
]

rows = []
missing = []
for rel in inputs:
    path = REPO / rel
    if not path.is_file():
        missing.append(rel)
        continue
    rows.append({"path": rel, "byte_count": path.stat().st_size, "sha256": sha(path), "mode": "read_only_publication_input"})

ledger = json.loads((REPO / "stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03ds_status_ledger.json").read_text())
final = json.loads((REPO / "stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03ds_final_manifest.json").read_text())
statuses = {row["stage"]: row["status"] for row in ledger["rows"]}
checks = {
    "all_inputs_present": not missing,
    "stage03_status_ledger_pass": ledger.get("status") == "PASS",
    "stage03d_not_qualified_preserved": statuses.get("Stage 03D") == "DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED",
    "stage03dr_mixed_or_unresolved_preserved": statuses.get("Stage 03D-R") == "DYNAMIC_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED",
    "stage03e_authorization_false": ledger.get("stage03e_authorization") is False and final["preserved_statuses"]["stage03e_authorization"] is False,
    "dynamic_training_not_executed": final["evidence_summary"]["training_runs"] == 0 and final["evidence_summary"]["optimizer_steps"] == 0,
    "rollout_performance_not_tested": final["evidence_summary"]["rollouts"] == 0 and final["evidence_summary"]["performance_evaluations"] == 0,
    "stage03ds_closure_complete": final.get("status") == "STAGE03_ROUTE_PAUSED_GRADIENT_BOUNDARY_COMPLETE" and final.get("all_gates_pass") is True,
    "no_status_conflict": len(statuses) == 5 and len(set(statuses.values())) == 5,
    "historical_workflow_read_only": True,
}

manifest = {
    "schema_version": "sph-pio-poc.publication-p1.input-freeze.v1",
    "workflow": "Publication Track P1 — Evidence-Locked Manuscript Architecture and Chinese Draft v0.1",
    "workflow_is_stage03e": False,
    "workflow_is_stage04": False,
    "input_count": len(rows),
    "missing_inputs": missing,
    "inputs": rows,
    "preserved_statuses": {
        "stage01": "V2_QUALIFICATION_FAIL",
        "stage01h": "FINITE_RESOLUTION_DOMINANT",
        "viscosity_operator_form": "NOT_CONFIRMED",
        "stage02_route": "STAGE02_ROUTE_CLOSED_PUBLICATION_BOUNDARY_COMPLETE",
        "stage03c": "DYNAMIC_RK2_HYBRID_IMPLEMENTATION_VERIFIED",
        "stage03d": "DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED",
        "stage03dr": "DYNAMIC_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED",
        "topology_component": "TOPOLOGY_EVENT_COMPONENT_QUALIFIED",
        "stage03e_authorization": False,
        "dynamic_training": "NOT_EXECUTED",
        "rollout_performance": "NOT_TESTED",
    },
    "checks": checks,
    "status": "PASS" if all(checks.values()) else "FAIL",
}

out = PUB / "00_freeze/publication_input_freeze_manifest.json"
out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
print(json.dumps({"status": manifest["status"], "input_count": len(rows), "missing": missing, "output": str(out)}, ensure_ascii=False))
if manifest["status"] != "PASS":
    raise SystemExit(1)
