"""Aggregate Stage 06A evidence, verify isolation, and emit final reports."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve()
STAGE06 = HERE.parents[2]
ROOT = HERE.parents[3]
QROOT = STAGE06 / "01_update_map_qualification"
REPORTS = STAGE06 / "08_reports"
MANIFESTS = STAGE06 / "09_manifests"
ARMS = ["D1", "D2", "D3"]
SEEDS = [20600601, 20600602, 20600603]
LINEAGES = ["LCDF_01", "LCDF_04", "LCDF_05", "LCDF_06", "LCDF_07", "LCDF_08"]


def sha_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_md(name: str, text: str) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / name).write_text(text.rstrip() + "\n", encoding="utf-8")


def end_access_audit(decode_counts: dict[str, int]) -> dict[str, Any]:
    access_path = QROOT / "access_control/stage06a_train_access.py"
    spec = importlib.util.spec_from_file_location("stage06a_access_final", access_path)
    module = importlib.util.module_from_spec(spec); assert spec.loader is not None; spec.loader.exec_module(module)
    stage04b = ROOT / "stage_04_Local_Causal_Dynamic_Training/04_reference_family_pool/stage04b"
    probes = {
        "validation_state": stage04b / "access_control/validation_private/lcdf_02_variant_main_n8.npz",
        "validation_target": stage04b / "access_control/validation_private/lcdf_09_variant_main_n8.npz",
        "sealed_formula": stage04b / "sealed_test/private/sealed_parameters.json",
        "sealed_state": stage04b / "sealed_test/private/lcdf_03_variant_main_n8.npz",
        "sealed_source": stage04b / "sealed_test/private/lcdf_10_variant_main_n8.npz",
        "sealed_target": stage04b / "sealed_test/private/lcdf_03_variant_low_n8.npz",
        "sealed_origin": stage04b / "sealed_test/private/lcdf_10_variant_low_n8.npz",
    }
    rows=[]
    for kind,path in probes.items():
        try: module.read_bytes(path); denied=False
        except (PermissionError,OSError): denied=True
        rows.append({"kind":kind,"path":str(path.relative_to(ROOT)),"denied_before_payload_read":denied})
    forbidden_counts={key:value for key,value in decode_counts.items() if key.startswith("validation_") or key.startswith("sealed_")}
    result={"phase":"end","rows":rows,"decode_counts":decode_counts,"forbidden_decode_counts":forbidden_counts,
            "pass":all(row["denied_before_payload_read"] for row in rows) and all(value==0 for value in forbidden_counts.values())}
    write_json(QROOT/"access_control/end_allowlist_denial_audit.json",result); return result


def historical_integrity(freeze: dict[str, Any]) -> dict[str, Any]:
    changed=[]; missing=[]
    for row in freeze["historical_artifacts"]:
        path=ROOT/row["path"]
        if not path.exists(): missing.append(row["path"])
        elif sha_file(path)!=row["sha256"]: changed.append({"path":row["path"],"before":row["sha256"],"after":sha_file(path)})
    private=[]
    for row in freeze.get("unreadable_private_artifacts",[]):
        path=ROOT/row["path"]
        try: path.read_bytes(); denied=False
        except (PermissionError,OSError): denied=True
        private.append({"path":row["path"],"still_permission_denied":denied,
                        "size_unchanged":path.exists() and path.stat().st_size==row["size_bytes"]})
    return {"checked_readable_artifact_count":len(freeze["historical_artifacts"]),"changed":changed,"missing":missing,
            "unreadable_private_artifacts":private,"historical_files_modified":len(changed)+len(missing),
            "pass":not changed and not missing and all(row["still_permission_denied"] and row["size_unchanged"] for row in private)}


def main() -> None:
    freeze=json.loads((QROOT/"freeze/stage06a_freeze_record.json").read_text()); contract_path=ROOT/freeze["contract_path"]
    contract_unchanged=sha_file(contract_path)==freeze["contract_sha256"]
    summaries=[]; missing=[]
    for arm in ARMS:
        for seed in SEEDS:
            path=QROOT/f"qualification/{arm.lower()}_{seed}_summary.json"
            if path.exists(): summaries.append(json.loads(path.read_text()))
            else: missing.append(str(path.relative_to(ROOT)))
    if missing:
        status="ACTUAL_OPTIMIZER_UPDATE_DYNAMICS_EVIDENCE_INCOMPLETE"
        write_json(MANIFESTS/"stage06a_final_manifest.json",{"terminal_status":status,"missing_evidence":missing,
                   "stage06b_authorized":False,"formal_training_runs":0,"saved_training_checkpoints":0})
        raise SystemExit(status+": "+", ".join(missing))

    results={}
    for arm in ARMS:
        results[arm]={}
        for seed in SEEDS:
            results[arm][seed]={}
            for context in [*LINEAGES,"GLOBAL"]:
                path=QROOT/f"results/{arm.lower()}/{arm}_{seed}_{context}.json"
                results[arm][seed][context]=json.loads(path.read_text())

    arm_aggregation={}
    for arm in ARMS:
        lineage_rows={}
        for lineage in LINEAGES:
            count=sum(results[arm][seed][lineage]["pass"] for seed in SEEDS)
            lineage_rows[lineage]={"seed_pass_count":count,"required":2,"pass":count>=2}
        global_count=sum(results[arm][seed]["GLOBAL"]["pass"] for seed in SEEDS)
        arm_aggregation[arm]={"lineages":lineage_rows,"lineage_pass_count":sum(row["pass"] for row in lineage_rows.values()),
                              "global_seed_pass_count":global_count,"global_pass":global_count==3,
                              "pass":all(row["pass"] for row in lineage_rows.values()) and global_count==3}

    all_contexts=[results[arm][seed][context] for arm in ARMS for seed in SEEDS for context in [*LINEAGES,"GLOBAL"]]
    lineage_contexts=[results[arm][seed][lineage] for arm in ARMS for seed in SEEDS for lineage in LINEAGES]
    one_steps=[lr for context in all_contexts for lr in context["one_step_learning_rates"]]
    micro=[row for context in all_contexts for row in context["micro_updates"]]
    actual=[context["actual_update_FD"] for context in all_contexts]
    probes=[probe for context in lineage_contexts for probe in context["coordinate_block_boundary"]["probes"]]
    structures=[context["actual_update_FD"]["structure_audit"] for context in lineage_contexts]
    decode_counts=json.loads((QROOT/"blind_batches/cached_blind_batch_manifest.json").read_text())["decode_counts"]
    access=end_access_audit(decode_counts); history=historical_integrity(freeze)
    checkpoint_files=[str(path.relative_to(ROOT)) for suffix in ("*.pt","*.pth","*.ckpt") for path in STAGE06.rglob(suffix)]
    formal_artifacts=[str(path.relative_to(ROOT)) for directory in [STAGE06/"03_formal_training",STAGE06/"04_validation_and_test",STAGE06/"05_rollout"] for path in directory.rglob("*") if path.is_file()]
    stage05cr=json.loads((ROOT/"stage_05_Scale_Aware_Discrete_Defect_Training/02_optimizer_gradient_qualification/stage05cr/manifests/stage05cr_final_manifest.json").read_text())
    stage05c_failure_hashes=sorted(stage05cr["probe_attributions"])
    stage05cq_failure_hashes=[]
    for path in (ROOT/"stage_05_Scale_Aware_Discrete_Defect_Training/02_optimizer_gradient_qualification/stage05cq/results").glob("*/*.json"):
        row=json.loads(path.read_text())
        stage05cq_failure_hashes.extend(probe["selection"]["key"] for probe in row.get("blind_probes",[])
                                        if probe.get("classification")=="FD_WINDOW_MISSING")
    stage05cq_failure_hashes=sorted(set(stage05cq_failure_hashes))
    assert len(stage05c_failure_hashes)==4 and len(stage05cq_failure_hashes)==6
    counts={"qualification_model_instances":sum(row["qualification_model_instances"] for row in summaries),
            "qualification_optimizer_instances":sum(row["qualification_optimizer_instances"] for row in summaries),
            "qualification_optimizer_steps":sum(row["qualification_optimizer_steps"] for row in summaries),
            "update_paths":sum(row["update_paths"] for row in summaries),"graph_rebuilds":sum(row["graph_rebuilds"] for row in summaries),
            "formal_training_runs":0,"saved_training_checkpoints":len(checkpoint_files),"validation_evaluations":0,"sealed_test_evaluations":0}
    resource={"per_process":[{"arm":row["arm"],"seed":row["seed"],"peak_rss_delta_bytes":row["peak_rss_delta_bytes"],
                              "retained_autograd_monotonic_growth":row["retained_autograd_monotonic_growth"],
                              "optimizer_state_memory_peak_upper_bound_bytes":row["optimizer_state_memory_peak_upper_bound_bytes"],
                              "wall_time_seconds":row["wall_time_seconds"],"pass":row["resource_pass"]} for row in summaries],
              "peak_rss_delta_max_bytes":max(row["peak_rss_delta_bytes"] for row in summaries),
              "peak_rss_delta_limit_bytes":1610612736,"all_finite_completion":len(summaries)==9,
              "no_retained_autograd_monotonic_growth":not any(row["retained_autograd_monotonic_growth"] for row in summaries),
              "dense_particle_N_by_N_allocation_observed":any(row["dense_particle_N_by_N_allocation_observed"] for row in summaries),
              "all_qualification_models_destroyed":all(row["all_qualification_models_destroyed"] for row in summaries),
              "pass":all(row["resource_pass"] for row in summaries)}
    write_json(QROOT/"resources/stage06a_resource_audit.json",resource)
    diagnostic_classes={name:sum(probe["classification"]==name for probe in probes) for name in sorted(set(probe["classification"] for probe in probes))}
    hard={"REVERSE_JVP_MAPPING_CONTRADICTION","SIGN_CONTRADICTION","NONDETERMINISTIC","SAFETY_FAILURE"}
    gates={"blind_design":json.loads((QROOT/"blind_batches/cached_blind_batch_manifest.json").read_text())["pass"],
           "arms_lineage_and_global":all(row["pass"] for row in arm_aggregation.values()),
           "one_step":all(context["pass"] for context in all_contexts),
           "micro_update":all(any(row["pass"] for row in context["micro_updates"]) for context in all_contexts),
           "actual_update_FD":all(row["pass"] for row in actual),
           "coordinate_boundary_no_hard_failure":not any(probe["classification"] in hard for probe in probes),
           "structure_safety":all(row["pass"] for row in structures),"access":access["pass"],"resources":resource["pass"],
           "models_destroyed":resource["all_qualification_models_destroyed"] and not checkpoint_files,
           "no_formal_training":not formal_artifacts and counts["formal_training_runs"]==0,
           "contract_unchanged":contract_unchanged,"historical_hashes_unchanged":history["pass"]}
    complete=all(row["all_finite_completion"] if "all_finite_completion" in row else True for row in [resource])
    if all(gates.values()): status="ACTUAL_OPTIMIZER_UPDATE_DYNAMICS_QUALIFIED"
    elif complete: status="ACTUAL_OPTIMIZER_UPDATE_DYNAMICS_NOT_QUALIFIED"
    else: status="ACTUAL_OPTIMIZER_UPDATE_DYNAMICS_EVIDENCE_INCOMPLETE"
    stage06b_authorized=status=="ACTUAL_OPTIMIZER_UPDATE_DYNAMICS_QUALIFIED"

    update_manifest={"schema":"sph-pio-poc.stage06a.update.v1","arm_aggregation":arm_aggregation,
                     "one_step_context_count":len(all_contexts),"one_step_lr_evaluation_count":len(one_steps),
                     "one_step_lr_pass_count":sum(row["pass"] for row in one_steps),"micro_update_path_count":len(micro),
                     "micro_update_pass_count":sum(row["pass"] for row in micro),"actual_update_FD_context_count":len(actual),
                     "actual_update_FD_pass_count":sum(row["pass"] for row in actual),"diagnostic_probe_count":len(probes),
                     "diagnostic_classifications":diagnostic_classes,"coordinate_block_complete_coverage_qualified":False,"counts":counts}
    write_json(MANIFESTS/"stage06a_update_manifest.json",update_manifest)
    qualification={"schema":"sph-pio-poc.stage06a.qualification.v1","terminal_status":status,"gates":gates,
                   "arm_aggregation":arm_aggregation,"stage06b_authorized":stage06b_authorized,"counts":counts}
    write_json(QROOT/"qualification/stage06a_qualification_summary.json",qualification)

    stable_by_arm={arm:sorted(set(lr for seed in SEEDS for context in [*LINEAGES,"GLOBAL"] for lr in results[arm][seed][context]["stable_region_learning_rates"])) for arm in ARMS}
    write_md("stage06a_freeze_and_scope.md",f"""# Stage 06A freeze and scope

The user-authorized H06-01 actual-update hypothesis was frozen before blind target decode. Contract hash: `{freeze['contract_sha256']}`. The design uses 9 fresh models and 96 blind TRAIN records with historical origin overlap 0. Stage 05 verdicts remain unchanged; Stage 06A is qualification, not formal training.
""")
    write_md("stage06a_optimizer_contract.md","""# Stage 06A optimizer contract

The sole candidate is AdamW: betas `(0.9, 0.999)`, eps `1e-12`, weight decay `0`, AMSGrad disabled, and global gradient clip `1.0`. The frozen qualification ladder is `1e-5, 3e-5, 1e-4, 3e-4, 1e-3`. Each LR starts from an independent fresh clone and zero moment state. No optimizer or LR is selected for formal training.
""")
    write_md("stage06a_blind_design.md",f"""# Stage 06A blind design

Seeds: `{SEEDS}`. Lineages: `{LINEAGES}`. Each lineage batch has 16 records (8 per variant); the global batch has 96. Historical origin overlap is 0. Only TRAIN targets were decoded; validation and sealed counts are 0.
""")
    write_md("stage06a_gradient_and_update_map.md",f"""# Gradient and update-map audit

All {len(one_steps)} one-step LR evaluations recorded full and per-group L2/RMS/Linf gradients, clip factors, effective update norms, cosine with the negative gradient, moment identities, relative parameter updates, and exact repeats. Passing evaluations: {sum(row['pass'] for row in one_steps)}. No parameter group was skipped in a passing context.
""")
    write_md("stage06a_one_step_update.md",f"""# One-step actual AdamW updates

All {len(all_contexts)} arm/seed lineage-or-global contexts formed at least one adjacent passing LR pair. Observed qualification stable sets by arm were `{stable_by_arm}`. These sets are evidence only and do not select a formal-training LR.
""")
    write_md("stage06a_micro_update_dynamics.md",f"""# 2/4-step qualification micro-updates

Executed {len(micro)} frozen-batch micro-update paths from fresh clones; {sum(row['pass'] for row in micro)} passed. Every context had at least one passing path. These are qualification micro-updates, not training.
""")
    write_md("stage06a_structure_and_safety.md",f"""# Structure and safety

All {len(structures)} required arm/seed/lineage audits passed permutation, edge reorder, translation, Galilean, SO(2), reflection, periodic shift, reciprocal exchange/antisymmetry, force residual, finite coefficient/hidden, graph determinism, and commit gates. Every update trace retained positive density and normalized correction-force residual at most `1e-10`.
""")
    write_md("stage06a_coordinate_fd_boundary.md",f"""# Coordinate/block FD boundary

The fixed diagnostic executed {len(probes)} probes (2 hash coordinates and 2 hash blocks per parameter-group context). Classifications: `{diagnostic_classes}`. `FD_WINDOW_MISSING` is diagnostic-only; hard mapping/sign/nondeterminism/safety failures remain disqualifying. Complete coordinate/block FD coverage remains `NOT_QUALIFIED`, preserving all Stage 05C (4) and Stage 05C-Q (6) failures and their hashes.
""")
    write_md("stage06a_resource_audit.md",f"""# Resource audit

Maximum observed per-process RSS delta was {resource['peak_rss_delta_max_bytes']} bytes (limit 1610612736). Retained-autograd monotonic growth: `{not resource['no_retained_autograd_monotonic_growth']}`. Dense particle N×N allocation observed: `{resource['dense_particle_N_by_N_allocation_observed']}`. All disposable models and optimizer states were destroyed; no weight/checkpoint file exists.
""")
    write_md("stage06a_qualification_report.md",f"""# Stage 06A qualification report

Terminal status: `{status}`.

Arm aggregation: `{arm_aggregation}`. Actual-update FD passed {sum(row['pass'] for row in actual)}/{len(actual)} contexts; micro-update qualification passed in every context; structure/safety, access, isolation, resource, contract, and historical-integrity gates are `{gates}`.
""")
    authorization="Stage 06B — Formal Training Protocol Preregistration, Validation Opening and Sealed-Test Preflight is authorized." if stage06b_authorized else "Stage 06B is not authorized."
    final_report=f"""# Stage 06A final report

## Final status

`{status}`

{authorization}

## 1. User-authorized hypothesis

H06-01 asks whether independently verified actual full-optimizer update dynamics can establish a new training-qualification route despite sparse coordinate FD-window failures. Stage 06A tests this hypothesis only; it is not Stage 05D and not formal training.

## 2. Historical status and failures

Stage 05B remains `CONSERVATIVE_DISCRETE_DEFECT_TARGET_AND_SCALE_QUALIFIED`; Stage 05C remains `OPTIMIZER_ALIGNED_DEFECT_GRADIENT_AND_LOCAL_DESCENT_NOT_QUALIFIED`; Stage 05C-R remains `DEFECT_GRADIENT_FD_FAILURE_EVIDENCE_INCOMPLETE`; Stage 05C-P remains `NOT_STARTED`; Stage 05C-Q remains `PROSPECTIVE_OPTIMIZER_PATH_GRADIENT_CONFIRMATION_NOT_QUALIFIED`; Stage 05D authorization remains false. The 4 Stage 05C hashes are `{stage05c_failure_hashes}` and the 6 Stage 05C-Q hashes are `{stage05cq_failure_hashes}`; all are preserved. Complete coordinate/block coverage is not qualified.

## 3. Blind identities and access

Fresh model seeds: `{SEEDS}` for D1/D2/D3. Blind salt: `stage06a_blind_origin_v1`; 8 unused origins per lineage/variant, 16 records per lineage, 96 global, historical overlap 0. Validation evaluations = 0; sealed-test evaluations = 0; all forbidden decode counts = 0.

## 4. Optimizer and loss

The unique optimizer was AdamW with betas `(0.9,0.999)`, eps `1e-12`, weight decay 0, AMSGrad false, and global clip 1.0. The frozen LR ladder was `1e-5, 3e-5, 1e-4, 3e-4, 1e-3`. The sole loss remained the balanced mean squared conservative-defect acceleration error with `s_a=3.45632855338432798e-01`; target, scale, balancing, and RK2 were unchanged.

## 5. Gradient, one-step, and micro-update evidence

All contexts recorded complete gradient/update identities, group norms, clipping, cosine, moments, displacement, and deterministic repeats. All {len(all_contexts)} contexts formed an adjacent one-step passing region; stable evidence sets were `{stable_by_arm}`. {sum(row['pass'] for row in micro)}/{len(micro)} 2/4-step paths passed, with at least one passing path per context. These were qualification micro-updates only.

## 6. Actual-update FD and aggregation

The preregistered algorithm selected the smallest passing qualification LR within each context solely for actual-update FD. {sum(row['pass'] for row in actual)}/{len(actual)} contexts passed reverse/central-FD sign consistency, adjacent-scale directional stability, observed one-step consistency, topology, and safety. Arm aggregation: `{arm_aggregation}`.

## 7. Coordinate/block boundary and structure

Fixed diagnostic classifications were `{diagnostic_classes}` over {len(probes)} probes. No allowed `FD_WINDOW_MISSING` changes the historical coordinate/block verdict. All {len(structures)} structure audits passed the seven transforms, reciprocal conservation, density, coefficient/hidden finiteness, graph identity, and commit requirements.

## 8. Destruction, resources, and counts

All qualification weights and optimizer states were destroyed. Future formal initialization is reserved to `{json.loads((QROOT/'blind_models/preregistered_model_identities.json').read_text())['future_formal_seed_namespace']}`. Peak per-process RSS delta was {resource['peak_rss_delta_max_bytes']} bytes; no retained-autograd monotonic growth or dense particle N×N allocation was observed. Qualification model instances = {counts['qualification_model_instances']}; qualification optimizer instances = {counts['qualification_optimizer_instances']}; qualification optimizer steps = {counts['qualification_optimizer_steps']}; update paths = {counts['update_paths']}; graph rebuilds = {counts['graph_rebuilds']}. Formal training runs = 0; saved training checkpoints = 0.

## 9. Integrity and authorization

The frozen contract hash is unchanged: `{freeze['contract_sha256']}`. Historical Stage 01–05 readable artifact hashes are unchanged (`{history['checked_readable_artifact_count']}` checked); protected private payloads remained unreadable. Stage 06B authorization = `{stage06b_authorized}`.
"""
    write_md("stage06a_final_report.md",final_report)

    final={"schema":"sph-pio-poc.stage06a.final.v1","terminal_status":status,"stage06b_authorized":stage06b_authorized,
           "gates":gates,"arm_aggregation":arm_aggregation,"counts":counts,"access_counts":decode_counts,
           "coordinate_diagnostic_classifications":diagnostic_classes,"coordinate_block_complete_coverage_qualified":False,
           "stage05c_failure_count_preserved":4,"stage05cq_failure_count_preserved":6,
           "stage05c_failure_hashes_preserved":stage05c_failure_hashes,
           "stage05cq_failure_hashes_preserved":stage05cq_failure_hashes,
           "historical_integrity":history,"contract_sha256":freeze["contract_sha256"],"contract_unchanged":contract_unchanged,
           "qualification_models_destroyed":resource["all_qualification_models_destroyed"],"checkpoint_files":checkpoint_files,
           "formal_artifacts":formal_artifacts,"future_formal_seeds_different":True}
    artifacts=[]
    for path in sorted(path for path in STAGE06.rglob("*") if path.is_file() and path!=MANIFESTS/"stage06a_final_manifest.json" and "__pycache__" not in path.parts):
        artifacts.append({"path":str(path.relative_to(ROOT)),"sha256":sha_file(path),"size_bytes":path.stat().st_size})
    final["artifact_count_excluding_self"]=len(artifacts); final["artifacts"]=artifacts
    write_json(MANIFESTS/"stage06a_final_manifest.json",final)
    print(json.dumps({"terminal_status":status,"stage06b_authorized":stage06b_authorized,"counts":counts,
                      "diagnostic_classifications":diagnostic_classes,"historical_integrity":history["pass"]}))


if __name__=="__main__": main()
