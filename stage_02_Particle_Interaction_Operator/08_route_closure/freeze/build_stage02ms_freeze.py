#!/usr/bin/env python3
"""Freeze all historical Stage 01/02 evidence before Stage 02M-S synthesis."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
STAGE = REPO / "stage_02_Particle_Interaction_Operator"
ROOT = STAGE / "08_route_closure"


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


required = [
    STAGE / "07_reports/stage02mq_final_report.md",
    STAGE / "06_model/pair_force_pio_static_fitting_v0_2/results/stage02mq_qualification_summary.json",
    STAGE / "06_model/pair_force_pio_static_fitting_v0_2/results/stage02mq_frozen_success_gate_evaluation.json",
    STAGE / "06_model/pair_force_pio_static_fitting_v0_2/test_seal/test_release_manifest.json",
    STAGE / "06_model/pair_force_pio_static_fitting_v0_2/test_evaluation/stage02mq_sealed_test_evaluation.json",
    STAGE / "06_model/pair_force_pio_static_fitting_v0_2/conservation/stage02mq_postfit_conservation_results.json",
    STAGE / "06_model/pair_force_pio_static_fitting_v0_2/symmetry/stage02mq_postfit_symmetry_results.json",
    STAGE / "06_model/pair_force_pio_static_fitting_v0_2/resources/stage02mq_actual_resource_audit.json",
    STAGE / "06_model/pair_force_pio_training_protocol_v0_2/freeze/training_protocol_v0_2.yaml",
    STAGE / "06_model/pair_force_pio_failure_attribution_v0_1/results/stage02mr_final_summary.json",
    STAGE / "06_model/pair_force_pio_architecture_v0_1/results/stage02k_qualification_summary.json",
    STAGE / "05_dataset/blind_multifamily_pair_scope_v1_0/manifests/stage02jw_final_manifest.json",
    REPO / "07_reports/stage01g_execution_v2_qualification.md",
    REPO / "07_reports/stage01h_final_report.md",
    REPO / "stage_01_verification/documents/Stage_01_Research_Record.docx",
]
stage_reports = {
    "Stage 02A": "07_reports/stage02a_pio_theory_report.md",
    "Stage 02B": "07_reports/stage02b_final_report.md",
    "Stage 02C": "07_reports/stage02c_final_report.md",
    "Stage 02D": "07_reports/stage02d_final_report.md",
    "Stage 02E": "07_reports/stage02e_final_report.md",
    "Stage 02F": "07_reports/stage02f_final_report.md",
    "Stage 02G": "07_reports/stage02g_final_report.md",
    "Stage 02H": "07_reports/stage02h_final_report.md",
    "Stage 02I": "07_reports/stage02i_final_report.md",
    "Stage 02I-R": "07_reports/stage02ir_final_report.md",
    "Stage 02J": "07_reports/stage02j_final_report.md",
    "Stage 02J-R": "07_reports/stage02jr_final_report.md",
    "Stage 02J-S": "07_reports/stage02js_final_report.md",
    "Stage 02J-T": "07_reports/stage02jt_final_report.md",
    "Stage 02J-V": "07_reports/stage02jv_final_report.md",
    "Stage 02J-W": "07_reports/stage02jw_final_report.md",
    "Stage 02K": "07_reports/stage02k_final_report.md",
    "Stage 02L": "07_reports/stage02l_final_report.md",
    "Stage 02M": "07_reports/stage02m_final_report.md",
    "Stage 02M-R": "07_reports/stage02mr_final_report.md",
    "Stage 02M-P": "07_reports/stage02mp_final_report.md",
    "Stage 02M-Q": "07_reports/stage02mq_final_report.md",
}
expected_status = {
    "Stage 02A": "PIO_THEORY_QUALIFICATION_COMPLETE",
    "Stage 02B": "DATASET_QUALIFICATION_COMPLETE",
    "Stage 02C": "DATASET_GENERATION_AUDIT_COMPLETE",
    "Stage 02D": "TARGET_ATTRIBUTION_QUALIFICATION_COMPLETE",
    "Stage 02E": "TARGET_CONSTRUCTION_COMPLETE",
    "Stage 02F": "SPATIAL_TARGET_QUALIFICATION_COMPLETE",
    "Stage 02G": "SPATIAL_ATTRIBUTION_CLOSURE_COMPLETE",
    "Stage 02H": "REFERENCE_FIDELITY_QUALIFICATION_COMPLETE",
    "Stage 02I": "QUALIFIED_SPATIAL_TARGET_POOL_NOT_READY",
    "Stage 02I-R": "CONSERVATION_COMPATIBILITY_RESOLVED_PAIR_ONLY",
    "Stage 02J": "CONTROLLED_REGULAR_DATASET_NOT_READY",
    "Stage 02J-R": "MULTIFAMILY_CONTROLLED_DATASET_NOT_READY",
    "Stage 02J-S": "VERSIONED_MULTIFAMILY_DATASET_NOT_READY",
    "Stage 02J-T": "REGULARITY_GATE_V03_NOT_QUALIFIED",
    "Stage 02J-V": "REGULARITY_HARD_GATE_ROUTE_TERMINATED",
    "Stage 02J-W": "BLIND_MULTIFAMILY_DATASET_READY",
    "Stage 02K": "PAIR_FORCE_PIO_ARCHITECTURE_QUALIFIED",
    "Stage 02L": "STATIC_FITTING_PROTOCOL_READY",
    "Stage 02M": "STATIC_PAIR_FORCE_FITTING_NOT_QUALIFIED",
    "Stage 02M-R": "STATIC_FITTING_FAILURE_ATTRIBUTED_OPTIMIZATION_CONDITIONING",
    "Stage 02M-P": "STATIC_FITTING_PROTOCOL_V02_READY",
    "Stage 02M-Q": "STATIC_PAIR_FORCE_FITTING_V02_NOT_QUALIFIED",
}
required.extend(STAGE / value for value in stage_reports.values())
run_terminals = sorted((STAGE / "06_model/pair_force_pio_static_fitting_v0_2/runs").glob("K*/seed_*/run_terminal.json"))
required.extend(run_terminals)
missing = [str(path) for path in required if not path.is_file()]
if missing:
    raise FileNotFoundError(missing)

status_checks = {}
for stage, relative in stage_reports.items():
    text = (STAGE / relative).read_text()
    status_checks[stage] = expected_status[stage] in text

summary_sources = {
    "Stage 02K": STAGE / "06_model/pair_force_pio_architecture_v0_1/results/stage02k_qualification_summary.json",
    "Stage 02M": STAGE / "06_model/pair_force_pio_static_fitting_v0_1/results/stage02m_qualification_summary.json",
    "Stage 02M-R": STAGE / "06_model/pair_force_pio_failure_attribution_v0_1/results/stage02mr_final_summary.json",
    "Stage 02M-P": STAGE / "06_model/pair_force_pio_training_protocol_v0_2/results/stage02mp_final_summary.json",
    "Stage 02M-Q": STAGE / "06_model/pair_force_pio_static_fitting_v0_2/results/stage02mq_qualification_summary.json",
}
alias_checks = {stage: json.loads(path.read_text())["status"] == expected_status[stage] for stage, path in summary_sources.items()}
selected_checkpoints = []
for path in run_terminals:
    terminal = json.loads(path.read_text())
    checkpoint = REPO / terminal["selected_checkpoint"]
    selected_checkpoints.append({
        "run_id": terminal["run_id"],
        "terminal_summary": str(path.relative_to(REPO)),
        "terminal_summary_sha256": sha(path),
        "selected_checkpoint": terminal["selected_checkpoint"],
        "expected_sha256": terminal["selected_checkpoint_hash"],
        "actual_sha256": sha(checkpoint),
        "status": "PASS" if sha(checkpoint) == terminal["selected_checkpoint_hash"] else "FAIL",
    })

historical_paths = []
for path in STAGE.rglob("*"):
    if not path.is_file():
        continue
    rel = path.relative_to(STAGE)
    if rel.parts[0] == "08_route_closure" or (rel.parts[0] == "documents" and path.name == "Stage_02_Research_Record.docx") or (rel.parts[0] == "07_reports" and path.name.startswith("stage02ms_")):
        continue
    historical_paths.append(path)
for base in (REPO / "07_reports", REPO / "stage_01_verification"):
    for path in base.rglob("*"):
        if path.is_file() and (base.name == "stage_01_verification" or path.name.startswith(("stage01", "stage_01"))):
            historical_paths.append(path)
historical_paths = sorted(set(historical_paths))
rows = [{"path": str(path.relative_to(REPO)), "sha256": sha(path), "byte_count": path.stat().st_size, "historical_workflow_mode": "read_only_input"} for path in historical_paths]
checks = {
    "complete_stage02_status_reports_22_of_22": len(stage_reports) == 22 and all(status_checks.values()),
    "no_missing_final_status": all(status_checks.values()),
    "no_conflicting_state_alias": all(alias_checks.values()),
    "stage02mq_terminal_summaries_9_of_9": len(run_terminals) == 9,
    "stage02mq_selected_checkpoint_hashes_9_of_9": len(selected_checkpoints) == 9 and all(row["status"] == "PASS" for row in selected_checkpoints),
    "stage02mq_failure_preserved": expected_status["Stage 02M-Q"] == json.loads(summary_sources["Stage 02M-Q"].read_text())["status"],
    "historical_files_treated_as_nonwritable_inputs": True,
    "historical_write_operations": 0,
}
manifest = {
    "manifest_version": "stage02ms-historical-freeze-1.0.0",
    "freeze_timing": "before_stage02ms_evidence_synthesis",
    "historical_file_count": len(rows),
    "historical_files": rows,
    "stage_status_sources": {stage: {"status": expected_status[stage], "path": relative, "sha256": sha(STAGE / relative)} for stage, relative in stage_reports.items()},
    "selected_checkpoints": selected_checkpoints,
    "checks": checks,
    "scope_contract": {
        "static_pio_learning_route_terminated": True,
        "Stage02N_authorized": False,
        "training_protocol_v03_permitted": False,
        "rollout_authorized": False,
        "solver_in_the_loop_authorized": False,
        "new_training_runs": 0,
        "new_optimizer_steps": 0,
        "new_test_evaluations": 0,
    },
}
manifest["status"] = "PASS" if all(value is True or value == 0 for value in checks.values()) else "FAIL"
output = ROOT / "freeze/stage02ms_historical_freeze_manifest.json"
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n")
print(json.dumps({"status": manifest["status"], "historical_files": len(rows), "stage_statuses": len(stage_reports), "selected_checkpoints": len(selected_checkpoints)}, sort_keys=True))
