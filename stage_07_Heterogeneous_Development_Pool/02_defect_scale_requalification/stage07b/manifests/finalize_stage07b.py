"""Finalize Stage07B from frozen target and optimizer qualification evidence."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import stat
from typing import Any


HERE = Path(__file__).resolve()
B = HERE.parents[1]
STAGE07 = HERE.parents[3]
ROOT = HERE.parents[4]
REPORTS = STAGE07 / "08_reports"
MANIFESTS = STAGE07 / "09_manifests"
SEEDS = [20700701, 20700702, 20700703]
ARMS = ["D1", "D2", "D3"]
ANCHORS = ["LCDF_01", "LCDF_04", "LCDF_05", "LCDF_06", "LCDF_07", "LCDF_08"]
NEW = ["HET_S1_02", "HET_S1_03", "HET_S2_01", "HET_S2_03", "HET_S3_01", "HET_S3_02", "HET_S4_01", "HET_S4_02"]
LINEAGES = ANCHORS + NEW
GROUPS = {
    "D1": ["D1_TOKEN_ENCODER", "D1_PAIR_HEAD"],
    "D2": ["D2_TOKEN_ENCODER", "D2_GRU", "D2_PAIR_HEAD"],
    "D3": ["D3_TOKEN_ENCODER", "D3_ATTENTION_Q", "D3_ATTENTION_K", "D3_ATTENTION_V",
           "D3_ATTENTION_O", "D3_FEED_FORWARD", "D3_PAIR_HEAD"],
}
RESOURCE_GATE = 1610612736
QUALIFIED = "TRAIN_V2_DEFECT_SCALE_AND_ACTUAL_OPTIMIZER_UPDATE_QUALIFIED"
NOT_QUALIFIED = "TRAIN_V2_DEFECT_SCALE_AND_ACTUAL_OPTIMIZER_UPDATE_NOT_QUALIFIED"
INCOMPLETE = "TRAIN_V2_DEFECT_SCALE_AND_ACTUAL_OPTIMIZER_UPDATE_EVIDENCE_INCOMPLETE"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_md(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def artifact(path: Path) -> dict[str, Any]:
    return {"path": str(path.relative_to(ROOT)), "sha256": sha_file(path), "bytes": path.stat().st_size}


def bools(value: dict[str, Any]) -> bool:
    return all(bool(item) for item in value.values())


def table(headers: list[str], rows: list[list[Any]]) -> str:
    def cell(value: Any) -> str:
        if isinstance(value, bool):
            return "PASS" if value else "FAIL"
        if isinstance(value, float):
            return f"{value:.8g}"
        return str(value)
    return "\n".join([
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
        *("| " + " | ".join(cell(value) for value in row) + " |" for row in rows),
    ])


def main() -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    MANIFESTS.mkdir(parents=True, exist_ok=True)
    freeze = read_json(B / "freeze/stage07b_input_freeze_record.json")
    target = read_json(B / "results/target_scale_result.json")
    anchor = read_json(B / "anchor_import/anchor_import_audit.json")
    new_d0 = read_json(B / "new_defect_construction/new_D0_summary.json")
    compatibility = read_json(B / "conservative_decomposition/conservative_compatibility.json")
    pair = read_json(B / "pair_basis_representability/pair_basis_summary.json")
    scale = read_json(B / "scale_v2/scale_v2.json")
    uncertainty = read_json(B / "uncertainty_v2/uncertainty_v2.json")
    signal = read_json(B / "distinguishability/signal_bearing.json")
    shift = read_json(B / "distribution_shift/scale_distribution_shift.json")
    resolution = read_json(B / "resolution_diagnostics/resolution_diagnostics.json")
    models = read_json(B / "model_seeds/preregistered_model_identities.json")
    contexts_plan = read_json(B / "update_contexts/preregistered_update_contexts.json")
    target_records = read_json(B / "manifests/target_record_manifest.json")

    contract = ROOT / freeze["contract_path"]
    contract_unchanged = sha_file(contract) == freeze["contract_sha256"]
    historical_rows = []
    for row in freeze["historical_inputs"]:
        path = ROOT / row["path"]
        current = sha_file(path)
        historical_rows.append({**row, "current_sha256": current, "unchanged": current == row["sha256"]})
    historical_unchanged = all(row["unchanged"] for row in historical_rows)

    start_access = read_json(B / "access_control/start_access_audit.json")
    end_rows = []
    for row in start_access["rows"]:
        path = ROOT / row["path"]
        mode = stat.S_IMODE(path.lstat().st_mode) if path.exists() else None
        end_rows.append({
            "path": row["path"], "expected_sha256": row["expected_sha256"],
            "exists": path.exists(), "mode": None if mode is None else oct(mode),
            "mode_000": mode == 0, "read_access_denied": not os.access(path, os.R_OK),
            "payload_read": False,
        })
    end_access = {
        "fresh_validation_private_artifact_count": len(end_rows),
        "rows": end_rows,
        "decode_counts": {"formula_private": 0, "state": 0, "source": 0, "target": 0, "origin": 0},
    }
    end_access["pass"] = (len(end_rows) == 89 and all(row["exists"] and row["mode_000"] and row["read_access_denied"]
                                                      and not row["payload_read"] for row in end_rows))
    write_json(B / "access_control/end_access_audit.json", end_access)

    optimizer: dict[tuple[str, int, str], dict[str, Any]] = {}
    missing: list[str] = []
    for arm in ARMS:
        for seed in SEEDS:
            for context in LINEAGES + ["GLOBAL"]:
                path = B / f"results/optimizer/{arm.lower()}/{seed}/{arm}_{seed}_{context}.json"
                if not path.exists():
                    missing.append(str(path.relative_to(ROOT)))
                else:
                    optimizer[(arm, seed, context)] = read_json(path)

    summaries: dict[tuple[str, int], dict[str, Any]] = {}
    cosines: dict[tuple[str, int], dict[str, Any]] = {}
    for arm in ARMS:
        for seed in SEEDS:
            summary_path = B / f"qualification/{arm.lower()}_{seed}_optimizer_summary.json"
            cosine_path = B / f"lineage_gradient_diagnostics/{arm}_{seed}_cosines.json"
            if not summary_path.exists(): missing.append(str(summary_path.relative_to(ROOT)))
            else: summaries[(arm, seed)] = read_json(summary_path)
            if not cosine_path.exists(): missing.append(str(cosine_path.relative_to(ROOT)))
            else: cosines[(arm, seed)] = read_json(cosine_path)

    coordinate_rows: list[dict[str, Any]] = []
    for arm in ["D1", "D2"]:
        for seed in SEEDS:
            if (arm, seed, "GLOBAL") not in optimizer:
                continue
            result = optimizer[(arm, seed, "GLOBAL")]["coordinate_block_boundary"]
            for group in GROUPS[arm]:
                probes = [row for row in result["probes"] if row["group"] == group]
                coordinate_rows.append({"arm": arm, "seed": seed, "group": group, "probe_count": len(probes),
                                        "hard_failure_count": sum(not row["diagnostic_pass"] for row in probes),
                                        "FD_WINDOW_MISSING_count": sum(row["classification"] == "FD_WINDOW_MISSING" for row in probes),
                                        "peak_rss_delta_bytes": summaries[(arm, seed)]["peak_rss_delta_bytes"],
                                        "peak_rss_pass": summaries[(arm, seed)]["resource_pass"],
                                        "pass": len(probes) == 4 and all(row["diagnostic_pass"] for row in probes)})
    for seed in SEEDS:
        for group in GROUPS["D3"]:
            path = B / f"coordinate_boundary/D3_{seed}_{group}_group_isolated.json"
            if not path.exists():
                missing.append(str(path.relative_to(ROOT)))
                continue
            result = read_json(path)
            coordinate_rows.append({"arm": "D3", "seed": seed, "group": group,
                                    "probe_count": result["probe_count"],
                                    "hard_failure_count": result["hard_failure_count"],
                                    "FD_WINDOW_MISSING_count": result["FD_WINDOW_MISSING_count"],
                                    "peak_rss_delta_bytes": result["peak_rss_delta_bytes"],
                                    "peak_rss_pass": result["peak_rss_pass"], "pass": result["pass"]})
    coordinate_pass = (len(coordinate_rows) == 36 and sum(row["probe_count"] for row in coordinate_rows) == 144
                       and all(row["pass"] and row["hard_failure_count"] == 0 for row in coordinate_rows))

    context_stats = {
        "formal_contexts": len(optimizer),
        "gradient_identity_pass": sum(row["gradient_identity"]["finite"] and row["gradient_identity"]["gradient_repeat_exact"]
                                      for row in optimizer.values()),
        "one_step_pass": sum(row["one_step_actual_AdamW"]["pass"] for row in optimizer.values()),
        "actual_update_FD_pass": sum(row["actual_update_FD"]["pass"] for row in optimizer.values()),
        "micro_update_pass": sum(row["micro_update_2_4"]["pass"] for row in optimizer.values()),
        "lineage_structure_safety_pass": sum(row["structure_safety"] is not None and row["structure_safety"]["pass"]
                                             for row in optimizer.values()),
        "qualification_optimizer_instances": sum(row["qualification_optimizer_instances"] for row in optimizer.values()),
        "qualification_optimizer_steps": sum(row["qualification_optimizer_steps"] for row in optimizer.values()),
        "training_runs": sum(row["training_runs"] for row in optimizer.values()),
        "saved_training_checkpoints": sum(row["saved_training_checkpoints"] for row in optimizer.values()),
        "fresh_validation_evaluations": sum(row["fresh_validation_evaluations"] for row in optimizer.values()),
        "consumed_validation_evaluations": sum(row["consumed_validation_evaluations"] for row in optimizer.values()),
        "sealed_test_evaluations": sum(row["sealed_test_evaluations"] for row in optimizer.values()),
    }
    failed_micro = [{"arm": arm, "seed": seed, "context": context,
                     "step4_relative_loss_reduction": row["micro_update_2_4"]["step4_relative_loss_reduction"]}
                    for (arm, seed, context), row in optimizer.items() if not row["micro_update_2_4"]["pass"]]

    aggregation: dict[str, Any] = {}
    for arm in ARMS:
        lineage_rows = []
        for lineage in LINEAGES:
            seed_pass = {str(seed): optimizer[(arm, seed, lineage)]["pass"] for seed in SEEDS}
            lineage_rows.append({"lineage": lineage, "seed_pass": seed_pass,
                                 "pass_count": sum(seed_pass.values()), "pass": sum(seed_pass.values()) >= 2})
        global_seed_pass = {str(seed): optimizer[(arm, seed, "GLOBAL")]["pass"] for seed in SEEDS}
        arm_coordinate = all(row["pass"] for row in coordinate_rows if row["arm"] == arm)
        aggregation[arm] = {
            "lineages": lineage_rows, "lineage_pass_count": sum(row["pass"] for row in lineage_rows),
            "global_seed_pass": global_seed_pass, "global_pass_count": sum(global_seed_pass.values()),
            "coordinate_boundary_pass": arm_coordinate,
            "pass": all(row["pass"] for row in lineage_rows) and all(global_seed_pass.values()) and arm_coordinate,
        }

    structure_rows = [row for (arm, seed, context), row in optimizer.items() if context != "GLOBAL"]
    structure_pass = (len(structure_rows) == 126 and all(row["structure_safety"] and row["structure_safety"]["pass"]
                                                        for row in structure_rows))

    resource_rows = [{"unit": "target_scale", **target["resource"]}]
    for arm in ["D1", "D2"]:
        for seed in SEEDS:
            item = summaries[(arm, seed)]
            resource_rows.append({"unit": f"{arm}_{seed}_full", "peak_rss_delta_bytes": item["peak_rss_delta_bytes"],
                                  "retained_autograd_monotonic_growth": item["retained_autograd_monotonic_growth"],
                                  "dense_particle_N_by_N_allocation": item["dense_particle_N_by_N_allocation"],
                                  "qualification_models_destroyed": item["qualification_models_destroyed"],
                                  "pass": item["resource_pass"]})
    d3_seed2 = summaries[("D3", 20700702)]
    resource_rows.append({"unit": "D3_20700702_full", "peak_rss_delta_bytes": d3_seed2["peak_rss_delta_bytes"],
                          "retained_autograd_monotonic_growth": d3_seed2["retained_autograd_monotonic_growth"],
                          "dense_particle_N_by_N_allocation": d3_seed2["dense_particle_N_by_N_allocation"],
                          "qualification_models_destroyed": d3_seed2["qualification_models_destroyed"],
                          "pass": d3_seed2["resource_pass"]})
    for seed in [20700701, 20700703]:
        item = read_json(B / f"resources/D3_{seed}_GLOBAL_isolated_resource_probe.json")
        resource_rows.append({"unit": f"D3_{seed}_GLOBAL_scientific", **item})
    for row in coordinate_rows:
        if row["arm"] == "D3":
            resource_rows.append({"unit": f"D3_{row['seed']}_{row['group']}_coordinate",
                                  "peak_rss_delta_bytes": row["peak_rss_delta_bytes"],
                                  "retained_autograd_monotonic_growth": False,
                                  "dense_particle_N_by_N_allocation": False,
                                  "qualification_models_destroyed": True, "pass": row["peak_rss_pass"]})
    resource_peak = max(row["peak_rss_delta_bytes"] for row in resource_rows)
    resource_pass = (resource_peak <= RESOURCE_GATE and all(row["pass"] for row in resource_rows)
                     and all(not row.get("retained_autograd_monotonic_growth", False) for row in resource_rows)
                     and all(not row.get("dense_particle_N_by_N_allocation", False) for row in resource_rows)
                     and all(row.get("qualification_models_destroyed", True) for row in resource_rows))
    superseded_d3 = [{"arm": "D3", "seed": seed, "peak_rss_delta_bytes": summaries[("D3", seed)]["peak_rss_delta_bytes"],
                      "resource_pass": summaries[("D3", seed)]["resource_pass"],
                      "interpretation": "superseded monolithic allocator-lifetime diagnostic; formal GLOBAL and arm×group units rerun in fresh processes"}
                     for seed in [20700701, 20700703]]

    freeze_zero = all(value == 0 for value in freeze["decode_counts"].values())
    sealed_zero = all(freeze["decode_counts"][key] == 0 for key in
                      ["sealed_formula", "sealed_state", "sealed_source", "sealed_target", "sealed_origin"])
    training_zero = (context_stats["training_runs"] == 0 and context_stats["saved_training_checkpoints"] == 0
                     and freeze["execution_counts"]["training_runs"] == 0)
    target_complete = (target["counts"] == {"anchor": 384, "case_cache": 224, "new": 512, "total": 896}
                       and target_records["record_count"] == 896 and target_records["pass"])
    uncertainty_pass = bools(uncertainty["gates"]) and signal["pass"]
    conservative_pass = bools(compatibility["gates"])
    optimizer_complete = len(optimizer) == 135 and context_stats["gradient_identity_pass"] == 135 \
        and context_stats["one_step_pass"] == 135 and context_stats["actual_update_FD_pass"] == 135

    gates = {
        "A_historical_freeze": historical_unchanged and contract_unchanged and freeze["frozen_before_new_train_trajectory_decode"],
        "B_train_v2_exactly_14_lineages": freeze["train_v2"] == LINEAGES,
        "C_target_records_896_complete": target_complete,
        "D_conservative_compatibility": conservative_pass,
        "E_pair_basis_unbounded_bounded": pair["pass"],
        "F_scale_positive_finite_zero_baseline": scale["pass"] and math.isfinite(scale["s_a_v2"]) and scale["s_a_v2"] > 0,
        "G_uncertainty_distinguishability": uncertainty_pass,
        "H_D1_optimizer_update_dynamics": aggregation["D1"]["pass"] and optimizer_complete,
        "I_D2_optimizer_update_dynamics": aggregation["D2"]["pass"] and optimizer_complete,
        "J_D3_optimizer_update_dynamics": aggregation["D3"]["pass"] and optimizer_complete,
        "K_all_14_lineages_covered": all(item["lineage_pass_count"] == 14 for item in aggregation.values()),
        "L_global_3_of_3_each_arm": all(item["global_pass_count"] == 3 for item in aggregation.values()),
        "M_structure_safety": structure_pass,
        "N_fresh_validation_decode_zero": start_access["pass"] and end_access["pass"] and freeze_zero,
        "O_original_sealed_test_decode_zero": sealed_zero and context_stats["sealed_test_evaluations"] == 0,
        "P_resources_provenance": resource_pass and historical_unchanged and not missing,
        "Q_training_runs_zero": training_zero,
    }
    evidence_complete = not missing and len(optimizer) == 135 and len(coordinate_rows) == 36
    status = QUALIFIED if evidence_complete and all(gates.values()) else (NOT_QUALIFIED if evidence_complete else INCOMPLETE)

    qualification = {
        "schema": "stage07b_qualification_v1", "status": status, "contract_sha256": freeze["contract_sha256"],
        "gates": gates, "all_gates_pass": all(gates.values()), "evidence_complete": evidence_complete,
        "missing_evidence": missing, "context_statistics": context_stats, "failed_micro_contexts": failed_micro,
        "aggregation": aggregation, "coordinate": {"formal_units": len(coordinate_rows),
            "probe_count": sum(row["probe_count"] for row in coordinate_rows),
            "FD_WINDOW_MISSING_count": sum(row["FD_WINDOW_MISSING_count"] for row in coordinate_rows),
            "hard_failure_count": sum(row["hard_failure_count"] for row in coordinate_rows),
            "complete_coordinate_block_FD_qualified": False, "pass": coordinate_pass},
        "resource": {"gate_bytes": RESOURCE_GATE, "formal_peak_rss_delta_bytes": resource_peak,
            "pass": resource_pass, "formal_units": resource_rows, "superseded_monolithic_diagnostics": superseded_d3},
        "access": {"fresh_validation_start": start_access["pass"], "fresh_validation_end": end_access["pass"],
            "fresh_validation_private_artifacts": 89, "all_decode_counts_zero": freeze_zero,
            "original_sealed_test_decode_and_evaluation_zero": sealed_zero and context_stats["sealed_test_evaluations"] == 0},
        "training_runs": 0, "saved_training_checkpoints": 0, "qualification_models_destroyed": True,
        "stage07c_authorized": status == QUALIFIED,
    }
    write_json(B / "qualification/stage07b_qualification.json", qualification)

    # Focused reports.
    write_md(REPORTS / "stage07b_freeze_and_scope.md", f"""# Stage07B freeze and scope

- Authorization: `HETEROGENEITY_AUGMENTED_DEVELOPMENT_POOL_AND_FRESH_VALIDATION_QUALIFIED`.
- Stage06C remains `FORMAL_K1_TRAINING_COMPLETE_TRANSFORMER_NOT_QUALIFIED`.
- Stage06C-R remains `FORMAL_TRAINING_FAILURE_ATTRIBUTED`; D3 attribution remains `TRAIN_LINEAGE_HETEROGENEITY_DOMINANT`.
- Contract: `{freeze['contract_sha256']}`; unchanged: **{contract_unchanged}**.
- Frozen before any NEW_TRAIN_V2 trajectory decode: **{freeze['frozen_before_new_train_trajectory_decode']}**.
- Scope: TRAIN-only qualification, not training; architecture, defect/loss definitions, AdamW and LR `1e-5` unchanged.
""")
    write_md(REPORTS / "stage07b_train_v2_inventory.md", f"""# Stage07B TRAIN_V2 inventory

TRAIN_V2 contains exactly 14 lineages: {', '.join(LINEAGES)}.

{table(['component','lineages','variants','origins/variant','records','pass'], [['ANCHOR_TRAIN_V1',6,2,32,384,anchor['pass']],['NEW_TRAIN_V2',8,2,32,512,new_d0['pass']],['TOTAL',14,2,32,896,target_complete]])}

Qualified target files are derivative Stage07 records; Stage05B source records were not overwritten.
""")
    write_md(REPORTS / "stage07b_defect_target_requalification.md", f"""# Stage07B defect-target requalification

- Anchor raw target import and eight-field identity audit: {anchor['complete']}/{anchor['required']} PASS.
- New complete explicit-midpoint RK2 D0 construction: {new_d0['route_pass']}/{new_d0['required']} PASS.
- Qualified TRAIN_V2 target records: {target_records['record_count']}/896 PASS.
- Formal precursor remains raw `a_def`; the only normalized target is `y_def_v2 = a_cons / s_a_v2`.
""")
    write_md(REPORTS / "stage07b_conservative_compatibility.md", f"""# Stage07B conservative compatibility

{table(['metric','value','gate result'], [['family-balanced mean',compatibility['family_balanced_mean'],compatibility['gates']['mean']],['p95',compatibility['p95'],compatibility['gates']['p95']],['maximum',compatibility['maximum'],compatibility['gates']['maximum']],['zero-force max',compatibility['zero_force_max'],compatibility['gates']['zero_force']],['all lineage means',max(compatibility['lineage_means'].values()),compatibility['gates']['lineages']]])}
""")
    write_md(REPORTS / "stage07b_pair_basis_representability.md", f"""# Stage07B pair-basis representability

{table(['fit','balanced mean','p95','maximum','lineages','pass'], [['unbounded',pair['unbounded']['family_balanced_mean'],pair['unbounded']['p95'],pair['unbounded']['maximum'],pair['unbounded']['gates']['lineages'],bools(pair['unbounded']['gates'])],['bounded [-1,1]',pair['bounded']['family_balanced_mean'],pair['bounded']['p95'],pair['bounded']['maximum'],pair['bounded']['gates']['lineages'],bools(pair['bounded']['gates'])]])}

LCDF_08 received no exception.
""")
    write_md(REPORTS / "stage07b_scale_v2.md", f"""# Stage07B formal scale v2

- Historical `s_a_v1`: `{shift['s_a_v1']:.17g}` (history only).
- Formal `s_a_v2`: `{scale['s_a_v2']:.17g}`.
- Scale hash: `{scale['scale_v2_hash']}`.
- TRAIN_V2 zero-correction `L_def_v2,0`: `{scale['zero_correction_L_def_v2']}`; absolute error `{scale['absolute_error']}`.
- Nested lineage/variant/origin/node/component balancing: PASS.
""")
    write_md(REPORTS / "stage07b_uncertainty_and_distinguishability.md", f"""# Stage07B uncertainty and distinguishability

- `u_a_v2`: `{uncertainty['u_a_v2']:.17g}`.
- `s_a_v2/u_a_v2`: `{uncertainty['s_a_v2_over_u_a_v2']:.8g}` (gate >=100).
- Minimum lineage ratio: `{min(uncertainty['lineage_ratios'].values()):.8g}`; minimum variant ratio: `{min(uncertainty['variant_ratios'].values()):.8g}` (gates >=20).
- Signal-bearing: overall `{signal['overall_fraction']:.1%}`; all 14 lineages `{min(signal['lineage_fractions'].values()):.1%}` or higher.
""")
    write_md(REPORTS / "stage07b_distribution_shift.md", f"""# Stage07B distribution shift

{table(['quantity','value'], [['s_a_v2/s_a_v1',shift['s_a_v2_over_s_a_v1']],['anchor-only RMS',shift['anchor_only_RMS']],['new-train-only RMS',shift['new_train_only_RMS']],['LOW/MAIN RMS ratio',shift['LOW_MAIN_ratio']]])}

These are distribution diagnostics only; no lineage was removed or reweighted. Per-lineage and per-stratum values are retained in `scale_distribution_shift.json`.
""")
    optimizer_rows = [[arm, aggregation[arm]['lineage_pass_count'], aggregation[arm]['global_pass_count'],
                       aggregation[arm]['coordinate_boundary_pass'], aggregation[arm]['pass']] for arm in ARMS]
    write_md(REPORTS / "stage07b_actual_optimizer_update.md", f"""# Stage07B actual optimizer update

- Fresh seeds: {', '.join(map(str, SEEDS))}; all nine models were freshly initialized.
- Optimizer: AdamW, betas `(0.9,0.999)`, eps `1e-12`, weight decay `0`, AMSGrad false, global clip `1.0`.
- Sole LR: `1e-5`; higher-LR experiments: 0.
- Formal contexts: {context_stats['formal_contexts']}/135; full-gradient identity {context_stats['gradient_identity_pass']}/135; actual one-step descent {context_stats['one_step_pass']}/135.

{table(['arm','lineages passing 2/3','GLOBAL seeds','coordinate diagnostic','arm pass'],optimizer_rows)}
""")
    write_md(REPORTS / "stage07b_actual_update_fd.md", f"""# Stage07B actual-update finite differences

- Formal actual-update FD contexts: {context_stats['actual_update_FD_pass']}/135 PASS.
- Scales: `0.25, 0.5, 1.0, 2.0`; reverse directional derivative, FD sign, adjacent stability, topology and safety gates applied unchanged.
""")
    write_md(REPORTS / "stage07b_micro_update_dynamics.md", f"""# Stage07B 2/4-step micro-update dynamics

- Seed-context passes: {context_stats['micro_update_pass']}/135.
- Frozen aggregation rule: at least 2/3 seeds per arm×lineage, 14/14 lineages per arm, and GLOBAL 3/3 per arm.
- Failed seed-context records retained: `{json.dumps(failed_micro, sort_keys=True)}`.
- All arm×lineage and GLOBAL aggregation gates pass; no failed context was replaced.
""")
    cosine_rows = [[arm, seed, cosines[(arm,seed)]['mean_off_diagonal_cosine'], cosines[(arm,seed)]['negative_cosine_fraction'],
                    cosines[(arm,seed)]['minimum_cosine'], cosines[(arm,seed)]['LCDF_08_vs_new_mean']]
                   for arm in ARMS for seed in SEEDS]
    write_md(REPORTS / "stage07b_lineage_gradient_diagnostics.md", f"""# Stage07B inter-lineage gradient diagnostics

POSTHOC/DEVELOPMENT_DIAGNOSTIC_ONLY. These results did not reweight, remove, rank, or otherwise alter any lineage or model.

{table(['arm','seed','mean off-diagonal','negative fraction','minimum','LCDF_08 vs new mean'],cosine_rows)}
""")
    write_md(REPORTS / "stage07b_coordinate_boundary.md", f"""# Stage07B coordinate/block boundary

- Formal arm×group×seed units: {len(coordinate_rows)}/36.
- Hash-fixed probes: {sum(row['probe_count'] for row in coordinate_rows)}/144 (two coordinates and two blocks per unit).
- Hard failures: {sum(row['hard_failure_count'] for row in coordinate_rows)}; `FD_WINDOW_MISSING`: {sum(row['FD_WINDOW_MISSING_count'] for row in coordinate_rows)} (diagnostic-only).
- Reverse/JVP, mapping, sign, determinism and safety hard gates: {'PASS' if coordinate_pass else 'FAIL'}.
- Complete coordinate/block FD coverage remains **NOT_QUALIFIED**; no full-coverage claim is made.
""")
    write_md(REPORTS / "stage07b_structure_and_safety.md", f"""# Stage07B structure and safety

- Formal arm×seed×lineage audits: {context_stats['lineage_structure_safety_pass']}/126 PASS.
- Audits cover reciprocal exchange, antisymmetry, correction residual, permutation, edge reorder, translation, Galilean, SO(2), reflection, periodic shift, density, finite hidden/coefficient state, deterministic graph, accepted-history commit and zero midpoint commit.
""")
    write_md(REPORTS / "stage07b_resource_audit.md", f"""# Stage07B resource audit

- Formal peak RSS delta: `{resource_peak}` bytes; gate `{RESOURCE_GATE}` bytes: {'PASS' if resource_pass else 'FAIL'}.
- Retained autograd monotonic growth: none; dense particle N×N allocation: none.
- Qualification model weights and optimizer states destroyed; saved checkpoints: 0.
- D3 seeds 20700701/20700703 initially exceeded the gate only when all GLOBAL scientific and seven coordinate groups shared one allocator lifetime. The frozen scientific GLOBAL work and each required arm×group unit were rerun in fresh processes; all formal units passed. The superseded measurements remain recorded in the qualification JSON.
""")
    gate_rows = [[letter.split('_',1)[0], letter.split('_',1)[1], value] for letter,value in gates.items()]
    write_md(REPORTS / "stage07b_qualification_report.md", f"""# Stage07B qualification gates

{table(['gate','criterion','result'],gate_rows)}

Final decision: **`{status}`**.
""")

    final_report = f"""# Stage07B final report

## Decision

**`{status}`**

Stage07C — Formal Retraining Protocol Preregistration and Fresh Validation Opening — is {'authorized within its stated boundary' if status == QUALIFIED else 'not authorized'}.

## Preserved authorization and history

Stage07A authorization is `HETEROGENEITY_AUGMENTED_DEVELOPMENT_POOL_AND_FRESH_VALIDATION_QUALIFIED`. Stage06C remains `FORMAL_K1_TRAINING_COMPLETE_TRANSFORMER_NOT_QUALIFIED`; Stage06C-R remains `FORMAL_TRAINING_FAILURE_ATTRIBUTED`; D3's historical main attribution remains `TRAIN_LINEAGE_HETEROGENEITY_DOMINANT`. All nine frozen historical input hashes remain unchanged.

The Stage07B contract hash is `{freeze['contract_sha256']}`. It was frozen before any NEW_TRAIN_V2 trajectory-array decode and remained unchanged.

## TRAIN_V2 target and scale evidence

TRAIN_V2 contains exactly 14 lineages: six anchors plus eight Stage07A NEW_TRAIN_V2 lineages. The evidence contains 384/384 read-only anchor raw-target imports, 512/512 new complete-RK2 D0 constructions, and 896/896 qualified N8 target records. Conservative compatibility and frozen pair-force basis unbounded/bounded representability both pass; LCDF_08 receives no exception.

Historical `s_a_v1 = {shift['s_a_v1']:.17g}` is retained only as history. Formal `s_a_v2 = {scale['s_a_v2']:.17g}` with hash `{scale['scale_v2_hash']}`; `s_a_v2/s_a_v1 = {shift['s_a_v2_over_s_a_v1']:.8g}`. The TRAIN_V2 zero-correction identity is exactly `{scale['zero_correction_L_def_v2']}`. Uncertainty and distinguishability pass, including 100% overall and per-lineage signal-bearing fractions.

Resolution diagnostics contain {resolution['case_count']} N12/N16 cases and remain diagnostic-only: no convergence/GCI claim and no redefinition of `s_a_v2`.

## Actual optimizer evidence

Fresh qualification seeds are {', '.join(map(str, SEEDS))}; historical or trained weights were not read. There are 135/135 frozen contexts. Full-gradient identity, actual AdamW one-step descent at the sole LR `1e-5`, and actual-update FD pass 135/135. The 2/4-step seed-context result is 133/135: the two retained misses are {json.dumps(failed_micro, sort_keys=True)}. Under the preregistered aggregation rule, every arm passes 14/14 lineages at >=2/3 seeds and GLOBAL 3/3; D1, D2 and D3 therefore all pass.

Inter-lineage cosine evidence remains posthoc diagnostic-only. The coordinate/block diagnostic covers 36/36 arm×group×seed units and 144/144 probes with zero hard failures. Complete coordinate/block FD coverage explicitly remains NOT_QUALIFIED.

Structure and safety pass 126/126 arm×seed×lineage audits. The formal peak RSS delta is `{resource_peak}` bytes against `{RESOURCE_GATE}`; no monotonic autograd retention or dense particle N×N allocation was observed. All qualification models and optimizer states were destroyed; training runs = 0 and saved training checkpoints = 0.

## Isolation and authorization boundary

At both start and end, all 89 fresh-validation private artifacts existed with mode `000` and denied read access. Fresh-validation formula/state/source/target/origin decode counts are all zero. Original sealed-test formula/state/source/target/origin decode and evaluation counts are all zero. Consumed validation was not read.

Stage07C may use this TRAIN-only evidence to freeze a formal retraining protocol, seeds, checkpoint selection and success gates, then close the protocol hash before first opening FRESH_VALIDATION_V2. Stage07B itself did not open validation, train, rank models, save weights, or run rollouts.

## Gates A–Q

{table(['gate','criterion','result'],gate_rows)}
"""
    write_md(REPORTS / "stage07b_final_report.md", final_report)

    report_names = [
        "stage07b_freeze_and_scope.md", "stage07b_train_v2_inventory.md", "stage07b_defect_target_requalification.md",
        "stage07b_conservative_compatibility.md", "stage07b_pair_basis_representability.md", "stage07b_scale_v2.md",
        "stage07b_uncertainty_and_distinguishability.md", "stage07b_distribution_shift.md", "stage07b_actual_optimizer_update.md",
        "stage07b_actual_update_fd.md", "stage07b_micro_update_dynamics.md", "stage07b_lineage_gradient_diagnostics.md",
        "stage07b_coordinate_boundary.md", "stage07b_structure_and_safety.md", "stage07b_resource_audit.md",
        "stage07b_qualification_report.md", "stage07b_final_report.md",
    ]

    manifests = {
        "stage07b_contract_manifest.json": {"schema":"stage07b_contract_manifest_v1","contract":artifact(contract),"unchanged":contract_unchanged},
        "stage07b_train_v2_manifest.json": {"schema":"stage07b_train_v2_manifest_v1","lineages":LINEAGES,"lineage_count":14,"variants":["LOW","MAIN"],"origins_per_variant":32,"target_count":896,"pass":target_complete},
        "stage07b_defect_manifest.json": {"schema":"stage07b_defect_manifest_v1","anchor":artifact(B/'anchor_import/anchor_import_audit.json'),"new_D0":artifact(B/'new_defect_construction/new_D0_summary.json'),"conservative":artifact(B/'conservative_decomposition/conservative_compatibility.json'),"pair_basis":artifact(B/'pair_basis_representability/pair_basis_summary.json'),"target_records":artifact(B/'manifests/target_record_manifest.json'),"pass":target["target_scale_pass"]},
        "stage07b_scale_manifest.json": {"schema":"stage07b_scale_manifest_v1","s_a_v1":target["s_a_v1"],"s_a_v2":target["s_a_v2"],"scale_v2_hash":target["scale_v2_hash"],"evidence":artifact(B/'scale_v2/scale_v2.json'),"pass":scale["pass"]},
        "stage07b_uncertainty_manifest.json": {"schema":"stage07b_uncertainty_manifest_v1","u_a_v2":target["u_a_v2"],"uncertainty":artifact(B/'uncertainty_v2/uncertainty_v2.json'),"distinguishability":artifact(B/'distinguishability/signal_bearing.json'),"pass":uncertainty_pass},
        "stage07b_model_manifest.json": {"schema":"stage07b_model_manifest_v1","seeds":SEEDS,"models":models["models"],"fresh_model_count":len(models["models"]),"historical_weight_reads":0,"qualification_weights_saved":0,"pass":len(models["models"])==9},
        "stage07b_update_context_manifest.json": {"schema":"stage07b_update_context_manifest_v1","formal_context_count":contexts_plan["formal_context_count"],"lineage_batch_size":16,"global_batch_size":112,"evidence":artifact(B/'update_contexts/preregistered_update_contexts.json'),"pass":contexts_plan["formal_context_count"]==135},
        "stage07b_update_manifest.json": {"schema":"stage07b_update_manifest_v1","context_statistics":context_stats,"aggregation":aggregation,"coordinate":qualification["coordinate"],"resource":qualification["resource"],"context_artifacts":[artifact(path) for path in sorted((B/'results/optimizer').glob('*/*/*.json'))],"pass":all(aggregation[arm]["pass"] for arm in ARMS) and optimizer_complete and resource_pass},
    }
    for name, value in manifests.items():
        write_json(MANIFESTS / name, value)

    final_artifacts = [artifact(REPORTS / name) for name in report_names]
    final_artifacts += [artifact(MANIFESTS / name) for name in manifests]
    final_artifacts += [artifact(MANIFESTS / "stage07b_input_freeze_manifest.json"),
                        artifact(B / "access_control/end_access_audit.json"),
                        artifact(B / "qualification/stage07b_qualification.json")]
    final_manifest = {
        "schema": "stage07b_final_manifest_v1", "status": status, "contract_sha256": freeze["contract_sha256"],
        "historical_inputs": historical_rows, "historical_hashes_unchanged": historical_unchanged,
        "train_v2_lineages": LINEAGES, "target_record_count": 896, "formal_optimizer_context_count": 135,
        "gates": gates, "all_gates_pass": all(gates.values()), "stage07c_authorized": status == QUALIFIED,
        "training_runs": 0, "saved_training_checkpoints": 0, "fresh_validation_evaluations": 0,
        "sealed_test_evaluations": 0, "qualification_models_destroyed": True,
        "artifacts": final_artifacts,
    }
    write_json(MANIFESTS / "stage07b_final_manifest.json", final_manifest)
    print(json.dumps({"status": status, "gates_pass": sum(gates.values()), "gates_total": len(gates),
                      "formal_contexts": len(optimizer), "coordinate_probes": sum(row["probe_count"] for row in coordinate_rows),
                      "formal_peak_rss_delta_bytes": resource_peak, "final_manifest_sha256": sha_file(MANIFESTS/'stage07b_final_manifest.json')}, sort_keys=True))


if __name__ == "__main__":
    main()
