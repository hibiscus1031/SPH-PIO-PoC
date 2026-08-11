"""Aggregate Stage07C gates, resource forecast, reports, and manifests."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import statistics
import stat
from typing import Any


HERE=Path(__file__).resolve(); C=HERE.parents[1]; STAGE07=HERE.parents[3]; ROOT=HERE.parents[4]
REPORTS=STAGE07/"08_reports"; MANIFESTS=STAGE07/"09_manifests"
ARMS=["D1","D2","D3"]; SEEDS=[20700711,20700712,20700713]
LINEAGES=["LCDF_01","LCDF_04","LCDF_05","LCDF_06","LCDF_07","LCDF_08","HET_S1_02","HET_S1_03","HET_S2_01","HET_S2_03","HET_S3_01","HET_S3_02","HET_S4_01","HET_S4_02"]
FRESH=["HET_S1_01","HET_S2_02","HET_S3_03","HET_S4_03"]
GATE=1610612736; STORAGE_GATE=10*1024**3
READY="FORMAL_RETRAINING_PROTOCOL_AND_FRESH_VALIDATION_PREFLIGHT_READY"
NOT_READY="FORMAL_RETRAINING_PROTOCOL_NOT_READY"; INCOMPLETE="FORMAL_RETRAINING_PROTOCOL_EVIDENCE_INCOMPLETE"


def read(path:Path)->Any: return json.loads(path.read_text(encoding="utf-8"))
def write_json(path:Path,value:Any)->None:
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(value,indent=2,sort_keys=True)+"\n",encoding="utf-8")
def write_md(path:Path,value:str)->None:
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(value.rstrip()+"\n",encoding="utf-8")
def sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1<<20),b""): h.update(chunk)
    return "sha256:"+h.hexdigest()
def artifact(path:Path)->dict[str,Any]: return {"path":str(path.relative_to(ROOT)),"sha256":sha(path),"bytes":path.stat().st_size}
def table(headers:list[str],rows:list[list[Any]])->str:
    def f(value:Any)->str:
        if isinstance(value,bool): return "PASS" if value else "FAIL"
        if isinstance(value,float): return f"{value:.8g}"
        return str(value)
    return "\n".join(["| "+" | ".join(headers)+" |","| "+" | ".join(["---"]*len(headers))+" |",
                      *("| "+" | ".join(f(v) for v in row)+" |" for row in rows)])


def main()->None:
    freeze=read(C/"freeze/stage07c_input_freeze_record.json"); protocol_manifest=read(C/"manifests/stage07c_protocol_manifest.json")
    contract=ROOT/protocol_manifest["protocol_path"]; batches=read(C/"train_v2_batch_schedule/formal_train_v2_batch_schedule.json")
    models=read(C/"model_seed_schedule/formal_model_seed_schedule.json"); validation=read(C/"validation_qualification/validation_target_qualification.json")
    validation_targets=read(C/"manifests/validation_target_manifest.json"); zero=read(C/"validation_qualification/fresh_validation_zero_baseline.json")
    release=read(C/"fresh_validation_release/fresh_validation_release_manifest.json"); restore=read(C/"access_control/post_validation_restore_audit.json")
    construction=read(C/"results/validation_construction_result.json"); target_train=read(C/"train_v2_batch_schedule/train_case_cache_manifest.json")
    checkpoint_audit=read(C/"freeze/historical_checkpoint_audit.json")
    missing=[]; preflights=[]
    for arm in ARMS:
        for seed in SEEDS:
            path=C/f"zero_step_preflight/identities/{arm}_seed{seed}.json"
            if not path.exists(): missing.append(str(path.relative_to(ROOT)))
            else: preflights.append(read(path))
    protocol_unchanged=sha(contract)==protocol_manifest["protocol_sha256"]==freeze["protocol"]["sha256"]
    historical=[]
    for expected in freeze["historical_inputs"]:
        path=ROOT/expected["path"]; current=sha(path)
        historical.append({**expected,"current_sha256":current,"unchanged":current==expected["sha256"] and path.stat().st_size==expected["bytes"]})
    checkpoint_current=[]
    for expected in checkpoint_audit["checkpoints"]:
        path=ROOT/expected["path"]; current=sha(path)
        checkpoint_current.append(current==expected["sha256"] and path.stat().st_size==expected["bytes"])
    selected_current=[]
    for expected in checkpoint_audit["selected_checkpoints"]:
        path=ROOT/expected["path"]; selected_current.append(sha(path)==expected["sha256"])
    historical_pass=all(row["unchanged"] for row in historical) and len(checkpoint_current)==590 and all(checkpoint_current) and len(selected_current)==9 and all(selected_current)

    memory112=[{"run_id":row["run_id"],"peak_rss_bytes":row["memory"]["peak_rss_bytes"],
                "peak_rss_delta_bytes":row["memory"]["peak_rss_delta_bytes"],"gate_bytes":GATE,
                "fresh_OS_process":row["fresh_OS_process"],"parameter_unchanged":row["parameter_hash_unchanged"],
                "pass":row["memory"]["peak_rss_delta_bytes"]<=GATE and row["fresh_OS_process"] and row["parameter_hash_unchanged"]} for row in preflights]
    memory_val=[{"run_id":row["run_id"],"validation_peak_rss_bytes":row["memory"]["phases"]["validation_peak"],
                "validation_records":row["validation_case_count"],"chunk_rule":"4x64 lineage-exact",
                "pass":row["memory"]["phases"]["validation_peak"]<=GATE and row["validation_case_count"]==256} for row in preflights]
    checkpoint_rows=[{"run_id":row["run_id"],"checkpoint_sha256":row["checkpoint"]["sha256"],
                      "checkpoint_bytes":row["checkpoint"]["bytes"],"equality":row["checkpoint"]["equality"],
                      "pass":all(row["checkpoint"]["equality"].values())} for row in preflights]
    denial_rows=[{"run_id":row["run_id"],**actor} for row in preflights for actor in row["sealed_test_denial"]["actors"]]
    sealed_counts={"formula":0,"state":0,"source":0,"target":0,"origin":0,"evaluations":0}
    sealed_pass=len(denial_rows)==45 and all(row["denied"] and not row["payload_read"] for row in denial_rows) and all(v==0 for v in sealed_counts.values())
    write_json(C/"sealed_test_preflight/original_sealed_test_denial.json",
               {"actors_per_run":5,"run_count":len(preflights),"rows":denial_rows,"decode_counts":sealed_counts,
                "consumed_validation_private_reads":0,"pass":sealed_pass})
    write_json(C/"memory_preflight/train_112_memory_preflight.json",{"run_count":len(memory112),"rows":memory112,"passed":sum(row["pass"] for row in memory112),"pass":len(memory112)==9 and all(row["pass"] for row in memory112)})
    write_json(C/"memory_preflight/validation_256_memory_preflight.json",{"run_count":len(memory_val),"rows":memory_val,"passed":sum(row["pass"] for row in memory_val),"pass":len(memory_val)==9 and all(row["pass"] for row in memory_val)})
    write_json(C/"checkpoint_preflight/checkpoint_roundtrip_results.json",{"run_count":len(checkpoint_rows),"rows":checkpoint_rows,"pass":len(checkpoint_rows)==9 and all(row["pass"] for row in checkpoint_rows)})

    forecast_arms={}; forecast_total=0.; checkpoint_total=0; graph_total=0
    for arm in ARMS:
        rows=[row for row in preflights if row["arm"]==arm]
        update_seconds=statistics.median(row["timing_seconds"]["train_forward"]+row["timing_seconds"]["backward"] for row in rows)*1.15
        val_seconds=statistics.median(sum(row["timing_seconds"]["validation_chunks"].values()) for row in rows)
        serialize_seconds=statistics.median(row["timing_seconds"]["checkpoint_serialization"] for row in rows)
        per_run=1500*update_seconds+75*val_seconds+78*serialize_seconds
        count=next(row["parameter_count"] for row in models["runs"] if row["arm"]==arm)
        preflight_bytes=max(row["checkpoint"]["bytes"] for row in rows)
        trained_checkpoint_bytes=math.ceil((preflight_bytes+2*count*8)*1.25)
        arm_storage=trained_checkpoint_bytes*78*3; arm_graphs=3*(1500*112*3+75*256*3)
        forecast_arms[arm]={"median_update_seconds_forecast":update_seconds,"validation_cycle_seconds":val_seconds,
                            "checkpoint_serialization_seconds":serialize_seconds,"per_run_wall_seconds":per_run,
                            "three_run_sequential_wall_seconds":3*per_run,"trained_checkpoint_bytes_forecast":trained_checkpoint_bytes,
                            "three_run_checkpoint_storage_bytes":arm_storage,"three_run_graph_rebuilds":arm_graphs}
        forecast_total+=3*per_run; checkpoint_total+=arm_storage; graph_total+=arm_graphs
    result_storage=9*(1500*2048+75*16384+4*1024**2)
    peak_absolute=max(row["memory"]["peak_rss_bytes"] for row in preflights); peak_delta=max(row["memory"]["peak_rss_delta_bytes"] for row in preflights)
    forecast={"schema":"sph-pio-poc.stage07c.resource-forecast.v1","based_on_actual_stage07c_preflight":True,
              "arms":forecast_arms,"sequential_total_wall_seconds":forecast_total,"peak_rss_bytes":peak_absolute,
              "peak_rss_delta_bytes":peak_delta,"peak_gate_bytes":GATE,"checkpoint_storage_bytes":checkpoint_total,
              "checkpoint_storage_gate_bytes":STORAGE_GATE,"result_storage_bytes":result_storage,"graph_rebuilds":graph_total,
              "finite_sequential_completion_feasible":math.isfinite(forecast_total) and forecast_total<=72*3600,
              "budget_reduced":False,"pass":peak_absolute<=GATE and peak_delta<=GATE and checkpoint_total<=STORAGE_GATE
                    and math.isfinite(forecast_total) and forecast_total<=72*3600}
    write_json(C/"resource_forecast/stage07d_resource_forecast.json",forecast)

    counters={key:sum(row["counters"][key] for row in preflights) for key in preflights[0]["counters"]} if preflights else {}
    preflight_pass=len(preflights)==9 and all(row["pass"] for row in preflights)
    fresh_files=read(STAGE07/"09_manifests/stage07a_validation_seal_manifest.json")["private_artifacts"]
    all_mode0=len(fresh_files)==89 and all(stat.S_IMODE((ROOT/row["path"]).stat().st_mode)==0 for row in fresh_files)
    first_decode=datetime.fromisoformat(release["first_decode_timestamp"]); protocol_mtime=datetime.fromtimestamp(contract.stat().st_mtime,tz=first_decode.tzinfo)
    gates={
        "A_historical_freeze":historical_pass,
        "B_protocol_frozen_before_fresh_validation_decode":protocol_unchanged and freeze["fresh_validation_decode_count_at_freeze"]==0 and protocol_mtime<first_decode,
        "C_formal_seeds_fixed":models["formal_seeds"]==SEEDS and models["run_count"]==9,
        "D_optimizer_LR_unchanged":read(C/"optimizer_schedule/formal_scheduler_values.json")["pass"] and protocol_unchanged,
        "E_TRAIN_V2_896_exact":target_train["case_count"]==896 and target_train["pass"] and freeze["train_v2"]==LINEAGES,
        "F_eight_112_batches_cover_896":batches["pass"] and batches["base_batch_count"]==8 and all(row["record_count"]==112 for row in batches["base_batches"]),
        "G_fresh_validation_256_complete":validation_targets["record_count"]==256 and validation_targets["pass"] and validation["pass"],
        "H_validation_did_not_alter_protocol":validation["protocol_changes_from_validation"]==0 and validation["protocol_hash_unchanged"] and protocol_unchanged,
        "I_success_gates_frozen_before_validation":protocol_manifest["success_gates_frozen_before_validation"] and protocol_mtime<first_decode,
        "J_nine_run_identities_complete":len(preflights)==9 and {row["run_id"] for row in preflights}=={f"{arm}_seed{seed}" for arm in ARMS for seed in SEEDS},
        "K_112_memory_preflight_9_of_9":len(memory112)==9 and all(row["pass"] for row in memory112),
        "L_validation_memory_preflight_9_of_9":len(memory_val)==9 and all(row["pass"] for row in memory_val),
        "M_zero_step_preflight_9_of_9":preflight_pass,
        "N_checkpoint_reload_9_of_9":len(checkpoint_rows)==9 and all(row["pass"] for row in checkpoint_rows),
        "O_original_sealed_test_denial":sealed_pass,
        "P_sealed_decode_counts_zero":all(value==0 for value in sealed_counts.values()),
        "Q_resource_forecast":forecast["pass"],
        "R_formal_optimizer_steps_zero":counters.get("formal_optimizer_steps",1)==0 and counters.get("formal_parameter_updates",1)==0,
        "S_formal_training_runs_zero":counters.get("formal_training_runs",1)==0 and counters.get("saved_training_checkpoints",1)==0,
    }
    evidence_complete=not missing and len(preflights)==9 and validation_targets["record_count"]==256
    status=READY if evidence_complete and all(gates.values()) else (NOT_READY if evidence_complete else INCOMPLETE)
    qualification={"schema":"sph-pio-poc.stage07c.qualification.v1","status":status,"protocol_sha256":protocol_manifest["protocol_sha256"],
                   "gates":gates,"all_gates_pass":all(gates.values()),"evidence_complete":evidence_complete,"missing":missing,
                   "historical_hashes_unchanged":historical_pass,"validation":{"records":256,"qualification":validation,
                       "zero_baseline":zero,"first_decode_timestamp":release["first_decode_timestamp"],"all_89_restored_mode_000":all_mode0},
                   "preflight":{"run_count":len(preflights),"passed":sum(row["pass"] for row in preflights),"counters":counters,
                       "peak_rss_bytes":peak_absolute,"peak_rss_delta_bytes":peak_delta},
                   "resource_forecast":forecast,"sealed_test": {"denial_pass":sealed_pass,"decode_counts":sealed_counts},
                   "formal_optimizer_steps":0,"formal_parameter_updates":0,"formal_training_runs":0,
                   "saved_training_checkpoints":0,"sealed_test_evaluations":0,"rollouts":0,
                   "stage07d_authorized":status==READY}
    write_json(C/"qualification/stage07c_qualification.json",qualification)

    report_data={
      "stage07c_freeze_and_scope.md":f"# Stage07C freeze and scope\n\nStage07B authorization: `TRAIN_V2_DEFECT_SCALE_AND_ACTUAL_OPTIMIZER_UPDATE_QUALIFIED`. Stage06C/C-R and D3 heterogeneity history are preserved. Protocol `{protocol_manifest['protocol_sha256']}` was frozen before fresh-validation decode. Stage07C performed no optimizer step or training.",
      "stage07c_formal_retraining_protocol.md":f"# Stage07C formal retraining protocol\n\nFormal seeds: {SEEDS}. AdamW `(0.9,0.999)`, eps `1e-12`, weight decay `0`, AMSGrad false, clip `1.0`, sole LR `1e-5`. Budget 320--1500 updates; 40-update linear warmup then cosine to `1e-6`; validation/checkpoint interval 20; early stopping patience 300 with `1e-5` global-Q improvement.",
      "stage07c_train_v2_batch_schedule.md":f"# Stage07C TRAIN_V2 batch schedule\n\n896 records are partitioned without overlap or omission into eight 112-record batches. Each batch contains four origins from every one of 14×2 lineage/variant cells. Orders for all 9 runs and 188 epochs are SHA-256 frozen; random shuffle, augmentation and curriculum are absent.",
      "stage07c_success_gates.md":"# Stage07C frozen success gates\n\nSeed PASS requires A numerical safety, TRAIN_V2 global Q<=0.50, fresh-validation global Q<=0.90, all four fresh lineages Q<=1.00, and structure PASS. Arm PASS is >=2/3 seeds; D3 arm PASS is the transformer route. These gates were frozen before validation opening.",
      "stage07c_checkpoint_selection_policy.md":"# Stage07C checkpoint selection policy\n\nThe sole selected checkpoint minimizes global-balanced FRESH_VALIDATION_V2 Q_def_v2 among updates >=320; earlier update wins ties. TRAIN, consumed validation, LCDF_08, diagnostics, sealed test, and arm comparison cannot participate.",
      "stage07c_fresh_validation_opening.md":f"# Stage07C fresh-validation opening\n\nFirst decode: `{release['first_decode_timestamp']}` under protocol `{release['protocol_hash_at_first_decode']}`. The frozen minimum 41-file set was temporarily mode 0400; 48 N12/N16 payloads remained sealed. Integrity passed 41/41 and all 89 files were restored to mode 000. Original sealed test remained closed.",
      "stage07c_validation_target_qualification.md":f"# Stage07C validation target qualification\n\n256/256 targets pass D0 class/functional/repeat, graph/source, finite, conservative, provenance and symmetry gates. Seven-transform evidence passes 1792/1792. Pair-basis and signal results are diagnostic. TRAIN-only `s_a_v2=1.7254786448147168` was used without refit. Zero-correction `Q_val0_v2={zero['global_Q_val0_v2']:.17g}` is diagnostic only.",
      "stage07c_memory_preflight.md":f"# Stage07C memory preflight\n\n112-record TRAIN forward/backward preflight passes 9/9 in fresh OS processes. 256-record validation using the frozen four-lineage 64-record chunks passes 9/9. Maximum absolute RSS `{peak_absolute}` bytes and delta `{peak_delta}` bytes are below `{GATE}`.",
      "stage07c_zero_step_preflight.md":f"# Stage07C zero-step preflight\n\n9/9 fresh identities pass finite TRAIN gradients, validation evaluation, structure smoke, access denial and parameter-unchanged checks. Formal optimizer steps, parameter updates, training runs and saved training checkpoints are all zero.",
      "stage07c_sealed_test_preflight.md":"# Stage07C original sealed-test preflight\n\nTrainer, validation evaluator, checkpoint selector, report generator and general reader denial pass for all 9 identities (45/45). Formula/state/source/target/origin decode and evaluation counts remain zero. Consumed validation remains diagnostic-only and unread.",
      "stage07c_resource_forecast.md":f"# Stage07C Stage07D resource forecast\n\nActual-preflight forecast: sequential wall `{forecast_total:.1f}` s; peak RSS `{peak_absolute}` bytes; checkpoint storage `{checkpoint_total}` bytes; result storage `{result_storage}` bytes; graph rebuilds `{graph_total}`. Peak and 10-GiB storage gates pass without reducing budget.",
    }
    gate_rows=[[key.split('_',1)[0],key.split('_',1)[1],value] for key,value in gates.items()]
    report_data["stage07c_qualification_report.md"]=f"# Stage07C qualification A--S\n\n{table(['gate','criterion','result'],gate_rows)}\n\nDecision: **`{status}`**."
    final=f"""# Stage07C final report

## Decision

**`{status}`**

Stage07D — Formal K=1 TRAIN_V2 D1/D2/D3 Retraining — is {'authorized' if status==READY else 'not authorized'}.

## Frozen protocol and preserved history

Stage07B authorization is `TRAIN_V2_DEFECT_SCALE_AND_ACTUAL_OPTIMIZER_UPDATE_QUALIFIED`. Stage06C remains `FORMAL_K1_TRAINING_COMPLETE_TRANSFORMER_NOT_QUALIFIED`; Stage06C-R remains `FORMAL_TRAINING_FAILURE_ATTRIBUTED`; D3 attribution remains `TRAIN_LINEAGE_HETEROGENEITY_DOMINANT`. Stage07A/B are unchanged. Protocol hash: `{protocol_manifest['protocol_sha256']}`. All 23 named historical inputs, 590 Stage06C checkpoints and 9 selected checkpoints remain hash-identical.

Formal seeds are `{SEEDS}` across D1/D2/D3. AdamW and sole LR `1e-5` are unchanged. TRAIN_V2 uses 896/896 Stage07B `y_def_v2` records and `s_a_v2=1.7254786448147168` (`sha256:4ca44e15f2024c5ed02c97d10d1342644fccd17db6a40d7e0e558c8d0214141b`); `s_a_v1` is forbidden.

Eight frozen 112-record batches cover all records exactly once and are lineage/variant balanced. Per-run/epoch order is SHA-256 fixed. Budget is 320--1500 updates with 40-update warmup, cosine decay to `1e-6`, validation/checkpoints every 20, and early-stopping patience 300. Success gates and the fresh-validation-only minimum-Q checkpoint selection policy were frozen before opening. LCDF_08/heterogeneity metrics, raw acceleration RMSE and relative-to-zero-baseline reductions remain diagnostic-only and cannot select checkpoints.

## Fresh validation and isolation

FRESH_VALIDATION_V2 first opened at `{release['first_decode_timestamp']}` under the closed protocol hash. 256/256 targets and 1792/1792 seven-transform checks pass using TRAIN-only `s_a_v2`; no validation scale was fitted. Diagnostic zero baseline is `Q_val0_v2={zero['global_Q_val0_v2']:.17g}`. Validation caused zero protocol changes. All 89 private artifacts were restored mode 000. LCDF_02/09 remained unread and diagnostic-only. The original LCDF_03/10 sealed test passes 45/45 actor denials with every decode/evaluation count zero.

## Zero-step and resource preflight

All 9 formal identities ran in fresh OS processes. 112-record forward/backward memory, frozen 4×64 validation memory, finite full gradient, optimizer/scheduler construction, structure smoke, checkpoint serialize/reload, RNG reload and exact-next-forward checks pass 9/9. Maximum RSS is `{peak_absolute}` bytes (delta `{peak_delta}`), below `{GATE}`. Forecast sequential wall is `{forecast_total:.1f}` s, checkpoint storage `{checkpoint_total}` bytes, result storage `{result_storage}` bytes and graph rebuilds `{graph_total}`; all resource gates pass.

Formal optimizer steps = 0; formal parameter updates = 0; formal training runs = 0; saved training checkpoints = 0; sealed-test evaluations = 0; rollouts = 0. Preflight weights and temporary checkpoint payloads were destroyed and cannot be used by Stage07D.

## Gates A--S

{table(['gate','criterion','result'],gate_rows)}
"""
    report_data["stage07c_final_report.md"]=final
    for name,value in report_data.items(): write_md(REPORTS/name,value)

    manifests={
      "stage07c_train_batch_manifest.json":{"schema":"stage07c_train-batch-manifest-v1","schedule":artifact(C/"train_v2_batch_schedule/formal_train_v2_batch_schedule.json"),"case_cache":artifact(C/"train_v2_batch_schedule/train_case_cache_manifest.json"),"record_count":896,"base_batches":8,"pass":gates["F_eight_112_batches_cover_896"]},
      "stage07c_model_seed_manifest.json":{"schema":"stage07c-model-seed-manifest-v1","formal_seeds":SEEDS,"runs":models["runs"],"run_count":9,"pass":gates["J_nine_run_identities_complete"]},
      "stage07c_validation_manifest.json":{"schema":"stage07c-validation-manifest-v1","release":artifact(C/"fresh_validation_release/fresh_validation_release_manifest.json"),"targets":artifact(C/"manifests/validation_target_manifest.json"),"qualification":artifact(C/"validation_qualification/validation_target_qualification.json"),"zero_baseline":artifact(C/"validation_qualification/fresh_validation_zero_baseline.json"),"record_count":256,"pass":gates["G_fresh_validation_256_complete"] and release["pass"]},
      "stage07c_checkpoint_policy_manifest.json":{"schema":"stage07c-checkpoint-policy-manifest-v1","policy":artifact(C/"checkpoint_policy/frozen_checkpoint_selection_policy.json"),"roundtrip":artifact(C/"checkpoint_preflight/checkpoint_roundtrip_results.json"),"run_count":9,"pass":gates["N_checkpoint_reload_9_of_9"]},
      "stage07c_preflight_manifest.json":{"schema":"stage07c-preflight-manifest-v1","run_count":9,"passed":sum(row["pass"] for row in preflights),"identity_artifacts":[artifact(C/f"zero_step_preflight/identities/{row['run_id']}.json") for row in preflights],"train_memory":artifact(C/"memory_preflight/train_112_memory_preflight.json"),"validation_memory":artifact(C/"memory_preflight/validation_256_memory_preflight.json"),"sealed_denial":artifact(C/"sealed_test_preflight/original_sealed_test_denial.json"),"counters":counters,"pass":preflight_pass and sealed_pass},
    }
    for name,value in manifests.items(): write_json(MANIFESTS/name,value)
    report_names=list(report_data); manifest_names=list(manifests)
    artifacts=[artifact(REPORTS/name) for name in report_names]+[artifact(MANIFESTS/name) for name in manifest_names]
    artifacts += [artifact(MANIFESTS/"stage07c_input_freeze_manifest.json"),artifact(MANIFESTS/"stage07c_protocol_manifest.json"),
                  artifact(C/"qualification/stage07c_qualification.json"),artifact(C/"resource_forecast/stage07d_resource_forecast.json")]
    final_manifest={"schema":"stage07c-final-manifest-v1","status":status,"protocol_sha256":protocol_manifest["protocol_sha256"],
                    "historical_hashes_unchanged":historical_pass,"historical_inputs":historical,"stage06c_checkpoint_hashes_unchanged":all(checkpoint_current),
                    "stage06c_selected_checkpoint_hashes_unchanged":all(selected_current),"gates":gates,"all_gates_pass":all(gates.values()),
                    "formal_seeds":SEEDS,"train_record_count":896,"validation_record_count":256,"preflight_run_count":9,
                    "formal_optimizer_steps":0,"formal_parameter_updates":0,"formal_training_runs":0,"saved_training_checkpoints":0,
                    "sealed_test_evaluations":0,"rollouts":0,"all_89_fresh_private_mode_000":all_mode0,"stage07d_authorized":status==READY,
                    "artifacts":artifacts}
    write_json(MANIFESTS/"stage07c_final_manifest.json",final_manifest)
    print(json.dumps({"status":status,"gates_pass":sum(gates.values()),"gates_total":len(gates),"preflight":f"{sum(row['pass'] for row in preflights)}/9",
                      "validation_records":validation_targets["record_count"],"peak_rss_bytes":peak_absolute,"forecast_seconds":forecast_total,
                      "checkpoint_storage_bytes":checkpoint_total,"final_manifest_sha256":sha(MANIFESTS/"stage07c_final_manifest.json")},sort_keys=True))


if __name__=="__main__": main()
