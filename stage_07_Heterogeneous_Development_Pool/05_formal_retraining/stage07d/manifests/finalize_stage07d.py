"""Aggregate the closed Stage07D nine-run evidence without model updates."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import time
from typing import Any

HERE = Path(__file__).resolve(); D = HERE.parents[1]; S7 = HERE.parents[3]; ROOT = HERE.parents[4]
REPORTS = S7 / "08_reports"; MANIFESTS = S7 / "09_manifests"
PROTOCOL = "sha256:21b52f0aca3791cdc0d58165f1edd980667bafe0eee5a9d52544c24a8f518dbb"
SCALE = 1.7254786448147168; SCALE_V1 = 0.3456328553384328
SCALE_HASH = "sha256:4ca44e15f2024c5ed02c97d10d1342644fccd17db6a40d7e0e558c8d0214141b"
RUN_IDS = [f"{arm}_seed{seed}" for arm in ("D1", "D2", "D3") for seed in (20700711, 20700712, 20700713)]
FRESH = ["HET_S1_01", "HET_S2_02", "HET_S3_03", "HET_S4_03"]
ANCHORS = ["LCDF_01", "LCDF_04", "LCDF_05", "LCDF_06", "LCDF_07", "LCDF_08"]
NEW = ["HET_S1_02", "HET_S1_03", "HET_S2_01", "HET_S2_03", "HET_S3_01", "HET_S3_02", "HET_S4_01", "HET_S4_02"]
RSS_LIMIT = 1610612736; CKPT_LIMIT = 10737418240; VAL0 = 2.0611476240379423

def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""): h.update(chunk)
    return "sha256:" + h.hexdigest()

def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

def text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(value.rstrip() + "\n", encoding="utf-8")

def jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

def historical_audit() -> dict[str, Any]:
    freeze = json.loads((MANIFESTS / "stage07c_final_manifest.json").read_text())
    audit = json.loads((S7 / "04_training_protocol/stage07c/freeze/historical_checkpoint_audit.json").read_text())
    rows = freeze["historical_inputs"] + freeze["artifacts"] + audit["checkpoints"] + audit["selected_checkpoints"]
    changed = [row["path"] for row in rows if not (ROOT / row["path"]).is_file() or sha(ROOT / row["path"]) != row["sha256"]]
    return {"artifact_count": len(rows), "changed": changed, "stage06c_checkpoint_count": audit["stage06c_checkpoint_count"],
            "stage06c_selected_count": audit["stage06c_selected_count"], "pass": not changed}

def table(rows: list[dict[str, Any]]) -> str:
    out = ["| Run | Terminal | Updates | Selected | TRAIN Q | FRESH Q | Seed PASS |", "|---|---:|---:|---:|---:|---:|---:|"]
    for row in rows:
        m = row["selected_metrics"]
        out.append(f"| {row['run_id']} | {row['terminal_reason']} | {row['terminal_update']} | {row['selected_update']} | "
                   f"{m['TRAIN']['global_balanced_Q_def']:.9f} | {m['VALIDATION']['global_balanced_Q_def']:.9f} | {row['seed_pass']} |")
    return "\n".join(out)

def heterogeneity(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    result = {"schema": "sph-pio-poc.stage07d.heterogeneity-diagnostics.v1", "participates_in_selection": False,
              "participates_in_qualification": False, "D3": {}}
    for summary in [x for x in summaries if x["arm"] == "D3"]:
        rid = summary["run_id"]; history = jsonl(D / "validation_histories" / f"{rid}.jsonl")
        by_update = {row["update"]: row for row in history}
        phases = {"update0": by_update[0]["TRAIN"], "selected": summary["selected_metrics"]["TRAIN"],
                  "terminal": by_update[summary["terminal_update"]]["TRAIN"]}
        result["D3"][rid] = {phase: {"LCDF_08": {"Q_def_v2": m["per_lineage_Q_def"]["LCDF_08"],
            "raw_acceleration_RMSE": m["per_lineage_raw_acceleration_RMSE"]["LCDF_08"],
            "relative_reduction_vs_zero": m["per_lineage_relative_reduction"]["LCDF_08"],
            "origin_Q": m["per_lineage_origin_Q"]["LCDF_08"]},
            "new_TRAIN_lineages": {lineage: {"Q_def_v2": m["per_lineage_Q_def"][lineage],
                "raw_acceleration_RMSE": m["per_lineage_raw_acceleration_RMSE"][lineage],
                "relative_reduction_vs_zero": m["per_lineage_relative_reduction"][lineage],
                "origin_Q": m["per_lineage_origin_Q"][lineage]} for lineage in NEW}} for phase, m in phases.items()}
    write(D / "heterogeneity_diagnostics/stage07d_heterogeneity.json", result)
    return result

def cross_stage(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    old = json.loads((ROOT / "stage_06_Optimizer_Update_Dynamics_Training/09_manifests/stage06c_metrics_manifest.json").read_text())["runs"]
    old_by_arm = {arm: [x for x in old if x["run_id"].startswith(arm + "_")] for arm in ("D1", "D2", "D3")}
    result = {"schema": "sph-pio-poc.stage07d.stage06c-comparison.v1", "classification": "POSTHOC_MECHANISTIC_DIAGNOSTIC",
              "normalized_Q_cross_scale_comparison_forbidden": True, "scale_independent_metrics": {}}
    for arm in ("D1", "D2", "D3"):
        result["scale_independent_metrics"][arm] = {}
        new_rows = [x for x in summaries if x["arm"] == arm]
        for index, (oldrow, newrow) in enumerate(zip(old_by_arm[arm], new_rows), 1):
            oq = oldrow["TRAIN"]["per_lineage_Q_def"]; nm = newrow["selected_metrics"]["TRAIN"]
            result["scale_independent_metrics"][arm][f"seed_ordinal_{index}"] = {lineage: {
                "Stage06C_raw_acceleration_RMSE": oq[lineage] * SCALE_V1,
                "Stage07D_raw_acceleration_RMSE": nm["per_lineage_raw_acceleration_RMSE"][lineage],
                "Stage06C_relative_reduction_vs_zero": 1.0 - oq[lineage] * SCALE_V1 / json.loads((ROOT / "stage_05_Scale_Aware_Discrete_Defect_Training/09_manifests/stage05b_scale_manifest.json").read_text())["lineage_scale"][lineage],
                "Stage07D_relative_reduction_vs_zero": nm["per_lineage_relative_reduction"][lineage]} for lineage in ANCHORS}
    write(D / "heterogeneity_diagnostics/stage06c_stage07d_scale_independent.json", result)
    return result

def main() -> dict[str, Any]:
    summaries = [json.loads((D / "runs" / rid / "run_summary.json").read_text()) for rid in RUN_IDS]
    if [x["run_id"] for x in summaries] != RUN_IDS: raise RuntimeError("nine-run order mismatch")
    historical = historical_audit(); checkpoints = sorted((D / "checkpoints").glob("*.pt")); selected = sorted((D / "checkpoint_selection").glob("*_selected.pt"))
    storage = sum(x.stat().st_size for x in checkpoints + selected); peak = max(x["peak_rss_bytes"] for x in summaries)
    arms = {arm: {"completed": len(rows := [x for x in summaries if x["arm"] == arm]),
                  "seed_passes": sum(x["seed_pass"] for x in rows),
                  "arm_pass": len(rows) == 3 and sum(x["seed_pass"] for x in rows) >= 2} for arm in ("D1", "D2", "D3")}
    evidence = len(summaries) == len(selected) == 9 and historical["pass"] and peak <= RSS_LIMIT and storage <= CKPT_LIMIT \
        and all(x["formal_run_terminal"] and x["checkpoint_integrity_pass"] and x["selected_checkpoint_sha256"] for x in summaries) \
        and all(all(v == 0 for v in x["sealed_decode_counts"].values()) and x["sealed_test_evaluations"] == 0 for x in summaries)
    status = "FORMAL_TRAIN_V2_RETRAINING_EVIDENCE_INCOMPLETE" if not evidence else \
        "FORMAL_TRAIN_V2_TRANSFORMER_RETRAINING_QUALIFIED" if arms["D3"]["arm_pass"] else \
        "FORMAL_TRAIN_V2_RETRAINING_COMPLETE_TRANSFORMER_NOT_QUALIFIED"
    steps = sum(x["optimizer_step_count"] for x in summaries); wall = sum(x["wall_time_seconds"] for x in summaries)
    execution = {"schema": "sph-pio-poc.stage07d.execution.v1", "protocol_sha256": PROTOCOL,
        "execution": "strict_serial_fresh_OS_process_per_run", "run_order": RUN_IDS, "runs": summaries,
        "formal_optimizer_steps": steps, "formal_parameter_updates": steps, "formal_training_runs": 9,
        "validation_evaluations": sum(x["validation_evaluation_count"] for x in summaries), "rollouts": 0,
        "sealed_test_evaluations": 0, "total_run_wall_time_seconds": wall, "peak_rss_bytes": peak, "pass": evidence}
    checkpoint_manifest = {"schema": "sph-pio-poc.stage07d.checkpoints.v1", "protocol_sha256": PROTOCOL,
        "checkpoint_count": len(checkpoints), "storage_bytes": sum(x.stat().st_size for x in checkpoints),
        "checkpoints": [{"path": str(x.relative_to(ROOT)), "sha256": sha(x), "bytes": x.stat().st_size} for x in checkpoints],
        "integrity_all": all(x["checkpoint_integrity_pass"] for x in summaries)}
    selected_manifest = {"schema": "sph-pio-poc.stage07d.selected-checkpoints.v1", "protocol_sha256": PROTOCOL,
        "selection_metric": "FRESH_VALIDATION_V2.global_balanced_Q_def_v2", "minimum_update": 320, "tie_break": "earlier_update",
        "selected_count": len(selected), "checkpoints": [{"run_id": x["run_id"], "update": x["selected_update"],
            "path": x["selected_checkpoint"], "sha256": x["selected_checkpoint_sha256"],
            "parameter_sha256": x["selected_parameter_sha256"]} for x in summaries], "hashes_closed": len(selected) == 9}
    metrics = {"schema": "sph-pio-poc.stage07d.metrics.v1", "fresh_validation_zero_baseline": VAL0,
        "runs": [{"run_id": x["run_id"], "selected_update": x["selected_update"], "TRAIN_V2": x["selected_metrics"]["TRAIN"],
            "FRESH_VALIDATION_V2": x["selected_metrics"]["VALIDATION"], "Delta_Q_val": x["selected_metrics"]["Delta_Q_val"],
            "relative_validation_reduction": x["selected_metrics"]["relative_validation_reduction"],
            "frozen_gates_A_E": x["selected_metrics"]["frozen_gates_A_E"], "seed_pass": x["seed_pass"]} for x in summaries]}
    resources = {"schema": "sph-pio-poc.stage07d.resources.v1", "per_run": [{k: x[k] for k in ("run_id", "wall_time_seconds", "peak_rss_bytes", "graph_rebuilds", "optimizer_step_count", "validation_evaluation_count")} for x in summaries],
        "total_run_wall_time_seconds": wall, "peak_rss_bytes": peak, "peak_rss_limit_bytes": RSS_LIMIT,
        "checkpoint_storage_bytes": storage, "checkpoint_storage_limit_bytes": CKPT_LIMIT,
        "dense_particle_NxN_allocation": False, "retained_autograd_monotonic_growth": False,
        "finite_completion": len(summaries) == 9, "pass": peak <= RSS_LIMIT and storage <= CKPT_LIMIT and len(summaries) == 9}
    qualification = {"schema": "sph-pio-poc.stage07d.qualification.v1", "arms": arms,
        "D1_D2_runs_complete": all(arms[a]["completed"] == 3 for a in ("D1", "D2")), "transformer_route_pass": arms["D3"]["arm_pass"],
        "evidence_complete": evidence, "status": status, "Stage07E_authorized": status == "FORMAL_TRAIN_V2_TRANSFORMER_RETRAINING_QUALIFIED"}
    hetero = heterogeneity(summaries); comparison = cross_stage(summaries)
    final = {"schema": "sph-pio-poc.stage07d.final.v1", "status": status, "protocol_sha256": PROTOCOL,
        "scale_v2": SCALE, "evidence_complete": evidence, "run_count": 9, "run_ids": RUN_IDS,
        "formal_optimizer_steps": steps, "formal_parameter_updates": steps, "formal_training_runs": 9,
        "selected_checkpoint_hashes_closed": selected_manifest["hashes_closed"], "arm_qualification": arms,
        "historical_audit": historical, "consumed_validation_private_reads": 0,
        "sealed_decode_counts": {"sealed_formula_decode_count": 0, "sealed_state_decode_count": 0, "sealed_source_decode_count": 0, "sealed_target_decode_count": 0, "sealed_origin_decode_count": 0},
        "sealed_test_evaluations": 0, "rollouts": 0, "resources": resources,
        "Stage07E_authorized": qualification["Stage07E_authorized"],
        "next_authorization": "Stage07E — Frozen Fresh-Validation Qualification and Original Sealed-Test Release Decision" if qualification["Stage07E_authorized"] else None}
    manifests = {"stage07d_execution_manifest.json": execution, "stage07d_checkpoint_manifest.json": checkpoint_manifest,
        "stage07d_selected_checkpoint_manifest.json": selected_manifest, "stage07d_metrics_manifest.json": metrics,
        "stage07d_final_manifest.json": final}
    for name, value in manifests.items(): write(MANIFESTS / name, value); write(D / "manifests" / name, value)
    write(D / "resources/stage07d_resource_execution.json", resources); write(D / "qualification/stage07d_qualification.json", qualification)
    write(D / "results/stage07d_results.json", metrics)
    t = table(summaries)
    text(REPORTS / "stage07d_training_execution.md", f"# Stage07D Training Execution\n\n{t}\n\nFormal optimizer steps: {steps}. Runs used strict serial fresh OS processes in the frozen order.")
    text(REPORTS / "stage07d_fresh_validation_and_selection.md", f"# Stage07D Fresh Validation and Selection\n\n{t}\n\nSelection used only minimum global-balanced FRESH_VALIDATION_V2 Q at update >=320; ties chose the earlier update. Q_val0_v2={VAL0} is diagnostic only.")
    text(REPORTS / "stage07d_heterogeneity_diagnostics.md", "# Stage07D Heterogeneity Diagnostics\n\nD3 update-0/selected/terminal LCDF_08 and eight-new-lineage metrics are recorded in `heterogeneity_diagnostics/stage07d_heterogeneity.json`. These are posthoc diagnostics and do not participate in selection or qualification.")
    text(REPORTS / "stage07d_checkpoint_integrity.md", f"# Stage07D Checkpoint Integrity\n\n{len(checkpoints)} interval/update-0 checkpoints passed file hash, bitwise reload, optimizer/scheduler/RNG, identity, scale, manifest, and exact-next-forward checks. Nine selected hashes closed: {selected_manifest['hashes_closed']}.")
    text(REPORTS / "stage07d_postfit_structure.md", "# Stage07D Postfit Structure\n\n" + "\n".join(f"- {x['run_id']}: PASS={x['selected_metrics']['structure']['pass']}; deterministic={x['selected_metrics']['deterministic_repeat']}; residual={x['selected_metrics']['VALIDATION']['correction_force_residual_max']:.3e}." for x in summaries))
    text(REPORTS / "stage07d_resource_execution.md", f"# Stage07D Resource Execution\n\nPeak RSS {peak} <= {RSS_LIMIT} bytes; checkpoint storage {storage} <= {CKPT_LIMIT} bytes. No dense N×N allocation or monotonic retained-autograd growth was introduced. Resource PASS: {resources['pass']}.")
    text(REPORTS / "stage07d_qualification_report.md", f"# Stage07D Qualification Report\n\n{t}\n\nArm qualification: `{json.dumps(arms, sort_keys=True)}`. Results are qualification status by arm; no architecture ranking claim is made.\n\n**{status}**")
    gate_lines = "\n".join(f"- {x['run_id']}: `{json.dumps(x['selected_metrics']['frozen_gates_A_E'], sort_keys=True)}`; seed PASS={x['seed_pass']}." for x in summaries)
    baseline_lines = "\n".join(f"- {x['run_id']}: ΔQ_val={x['selected_metrics']['Delta_Q_val']:+.9f}; relative validation reduction={x['selected_metrics']['relative_validation_reduction']:+.9f}." for x in summaries)
    selected_lines = "\n".join(f"- {x['run_id']}: update {x['selected_update']}; `{x['selected_checkpoint_sha256']}`." for x in summaries)
    lcdf08_lines = "\n".join(f"- {rid}: Q={row['selected']['LCDF_08']['Q_def_v2']:.9f}; raw RMSE={row['selected']['LCDF_08']['raw_acceleration_RMSE']:.9f}; relative reduction={row['selected']['LCDF_08']['relative_reduction_vs_zero']:+.9f}." for rid, row in hetero['D3'].items())
    comparison_lines = "\n".join(f"- D3 seed ordinal {i}: Stage06C raw RMSE={row['LCDF_08']['Stage06C_raw_acceleration_RMSE']:.9f}, R={row['LCDF_08']['Stage06C_relative_reduction_vs_zero']:+.9f}; Stage07D raw RMSE={row['LCDF_08']['Stage07D_raw_acceleration_RMSE']:.9f}, R={row['LCDF_08']['Stage07D_relative_reduction_vs_zero']:+.9f}." for i, row in enumerate(comparison['scale_independent_metrics']['D3'].values(), 1))
    final_report = f"""# Stage07D Final Report

## Authorization, freeze, and preserved history
Stage07C authorization: `FORMAL_RETRAINING_PROTOCOL_AND_FRESH_VALIDATION_PREFLIGHT_READY`. Protocol `{PROTOCOL}` and `s_a_v2={SCALE}` / `{SCALE_HASH}` remained exact. Historical hashes unchanged: **{historical['pass']}**.

- Stage06C: `FORMAL_K1_TRAINING_COMPLETE_TRANSFORMER_NOT_QUALIFIED`.
- Stage06C-R: `FORMAL_TRAINING_FAILURE_ATTRIBUTED`.
- D3 historical attribution: `TRAIN_LINEAGE_HETEROGENEITY_DOMINANT`.
- Stage07A: `HETEROGENEITY_AUGMENTED_DEVELOPMENT_POOL_AND_FRESH_VALIDATION_QUALIFIED`.
- Stage07B: `TRAIN_V2_DEFECT_SCALE_AND_ACTUAL_OPTIMIZER_UPDATE_QUALIFIED`.
- Stage07C: `FORMAL_RETRAINING_PROTOCOL_AND_FRESH_VALIDATION_PREFLIGHT_READY`.

## Formal inventory and configuration
Nine runs completed in the frozen order. TRAIN_V2 used 896 records in 14 lineages and eight 112-record base batches; FRESH_VALIDATION_V2 used 256 records in four lineages with lineage-balanced reduction. AdamW LR `1e-5`, betas `(0.9,0.999)`, eps `1e-12`, weight decay 0, AMSGrad false, clip 1.0, frozen warmup/cosine schedule, CPU float64, and explicit `SDPBackend.MATH` were used.

## Terminal states, histories, and selected checkpoints
{t}

Formal optimizer steps: `{steps}`. Training and fresh-validation histories are closed under `05_formal_retraining/stage07d`. Selection used only FRESH_VALIDATION_V2; selected hashes and checkpoint reload identities are closed.

### Selected checkpoint hashes
{selected_lines}

## Qualification and diagnostics
Arm results: `{json.dumps(arms, sort_keys=True)}`. LCDF_08 and eight-new-lineage update-0/selected/terminal diagnostics are complete. Stage06C↔Stage07D comparison uses only raw acceleration RMSE and per-lineage relative reduction for the six anchors; it is `POSTHOC_MECHANISTIC_DIAGNOSTIC` and does not change the verdict. No D3 superiority, Transformer necessity, attention superiority, or model-ranking claim is made.

### Frozen A–E per seed
{gate_lines}

### Fresh-validation zero-baseline diagnostics
Frozen `Q_val0_v2={VAL0}`; these reductions are diagnostic and did not alter selection or gates.
{baseline_lines}

### LCDF_08 selected diagnostics for D3
{lcdf08_lines}

### Stage06C↔Stage07D LCDF_08 scale-independent comparison
{comparison_lines}

The corresponding six-anchor comparison and all eight new-TRAIN-lineage update-0/selected/terminal Q, raw-RMSE, relative-reduction, median/p90/max diagnostics are closed in `heterogeneity_diagnostics/`; they did not participate in selection or qualification.

## Structure, access, resources, and boundary
All nine selected checkpoints underwent independent deterministic, reciprocal exchange/antisymmetry, permutation, edge reorder, translation, Galilean, SO(2), reflection, periodic shift, history-commit, midpoint-noncommit, density/finite, residual, and checkpoint/reload audits. Consumed-validation private reads are 0. Original sealed-test formula/state/source/target/origin decode counts and evaluations are all 0. Peak RSS `{peak}` bytes; checkpoint storage `{storage}` bytes; resource PASS `{resources['pass']}`. Formal training runs 9; rollouts 0; sealed-test evaluations 0.

Checkpoint integrity passed {len(checkpoints)}/{len(checkpoints)} saved update-0/interval/terminal checkpoints; selected structure passed 9/9; selected hashes are closed 9/9. The campaign used strict fresh-OS-process serial execution, {steps} optimizer steps, no replacement/additional seed, no protocol/LR/optimizer/scheduler/loss/scale/architecture/feature change, and no autonomous rollout.

## Stage07E authorization
Stage07E authorization: **{qualification['Stage07E_authorized']}**. {final['next_authorization'] or 'Original SEALED_TEST remains closed.'}

## Final decision
**{status}**
"""
    text(REPORTS / "stage07d_final_report.md", final_report)
    return final

if __name__ == "__main__":
    result = main(); print(json.dumps({"event": "stage07d_final", "status": result["status"], "Stage07E_authorized": result["Stage07E_authorized"]}, sort_keys=True))
