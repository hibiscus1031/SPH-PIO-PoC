"""Run one Stage07C zero-step identity in a fresh OS process."""

from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import random
import resource
import stat
import sys
import time
from typing import Any

import numpy as np
import psutil
import torch
from torch.nn.attention import SDPBackend, sdpa_kernel


HERE = Path(__file__).resolve(); C = HERE.parents[1]; STAGE07 = HERE.parents[3]; ROOT = HERE.parents[4]
QPATH = ROOT / "stage_05_Scale_Aware_Discrete_Defect_Training/02_optimizer_gradient_qualification/stage05c/qualification/run_stage05c_arm.py"
ARMS = ["D1", "D2", "D3"]; SEEDS = [20700711, 20700712, 20700713]
FRESH = ["HET_S1_01", "HET_S2_02", "HET_S3_03", "HET_S4_03"]
S_A = 1.7254786448147168; SCALE_HASH = "sha256:4ca44e15f2024c5ed02c97d10d1342644fccd17db6a40d7e0e558c8d0214141b"
RESOURCE_GATE = 1610612736


def import_path(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path); module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None; sys.modules[name] = module; spec.loader.exec_module(module); return module


q = import_path("stage07c_stage05c", QPATH); q.S_A = S_A
PROCESS = psutil.Process()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha_bytes(value: bytes) -> str: return "sha256:" + hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    digest=hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda:handle.read(1<<20),b""): digest.update(chunk)
    return "sha256:"+digest.hexdigest()


def rss_peak() -> int:
    return max(PROCESS.memory_info().rss, int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))


def case_from_row(row: dict[str, Any]) -> q.Case:
    path=ROOT/row["path"]; assert sha_file(path)==row["sha256"]
    with np.load(path,allow_pickle=False) as archive: a={key:archive[key] for key in archive.files}
    tensor=lambda value: torch.from_numpy(np.ascontiguousarray(value)).to(torch.float64)
    return q.Case(row["record_id"],row["lineage"],row["variant"],row["origin"],
        torch.from_numpy(a["frames"]).to(torch.int64),tensor(a["physical_times"]),tensor(a["x"]),tensor(a["velocity"]),
        tensor(a["density"]),tensor(a["material_labels"]),tensor(a["mass"]),tensor(a["smoothing"]),tensor(a["history_tokens"]),
        tensor(a["source_start"]),tensor(a["source_midpoint"]),tensor(a["v0_accepted"]),tensor(a["a_cons"]))


def fresh(arm: str, seed: int, expected: str) -> tuple[torch.nn.Module,q.DefectAdapter]:
    prior=torch.get_default_dtype(); torch.set_default_dtype(torch.float32)
    try:
        torch.manual_seed(seed); model=q.ARMS[arm]().to(dtype=torch.float64,device="cpu")
    finally: torch.set_default_dtype(prior)
    assert q.parameter_hash(model)==expected
    return model,q.DefectAdapter(arm,model)


def optimizer(adapter:q.DefectAdapter)->torch.optim.AdamW:
    return torch.optim.AdamW(adapter.parameters(),lr=1e-5,betas=(.9,.999),eps=1e-12,weight_decay=0,amsgrad=False)


def scheduler(opt:torch.optim.Optimizer)->torch.optim.lr_scheduler.LambdaLR:
    rows=json.loads((C/"optimizer_schedule/formal_scheduler_values.json").read_text())["rows"]
    factors=[row["factor"] for row in rows]
    return torch.optim.lr_scheduler.LambdaLR(opt,lr_lambda=lambda update:factors[min(update,1500)])


def rng_payload()->dict[str,Any]:
    return {"torch":torch.get_rng_state(),"numpy":np.random.get_state(),"python":random.getstate()}


def restore_rng(value:dict[str,Any])->None:
    torch.set_rng_state(value["torch"]); np.random.set_state(value["numpy"]); random.setstate(value["python"])


def next_rng()->dict[str,Any]:
    return {"torch":torch.rand(4).tolist(),"numpy":np.random.random(4).tolist(),"python":[random.random() for _ in range(4)]}


def denial_preflight()->dict[str,Any]:
    sealed=ROOT/"stage_04_Local_Causal_Dynamic_Training/04_reference_family_pool/stage04b/sealed_test/private/lcdf_03_variant_main_n8.npz"
    actors=["trainer","validation_evaluator","checkpoint_selector","report_generator","general_reader"]
    rows=[{"actor":actor,"path":str(sealed.relative_to(ROOT)),"exists":sealed.exists(),
           "mode":oct(stat.S_IMODE(sealed.stat().st_mode)),"os_read_access":sealed.exists() and __import__('os').access(sealed,__import__('os').R_OK),
           "payload_read":False,"denied":sealed.exists() and stat.S_IMODE(sealed.stat().st_mode)==0 and not __import__('os').access(sealed,__import__('os').R_OK)} for actor in actors]
    return {"actors":rows,"decode_counts":{"formula":0,"state":0,"source":0,"target":0,"origin":0},
            "pass":len(rows)==5 and all(row["denied"] for row in rows)}


def main(arm:str,seed:int)->None:
    torch.set_num_threads(1); started=time.perf_counter(); baseline=PROCESS.memory_info().rss; phases={"baseline":baseline}
    protocol=json.loads((C/"manifests/stage07c_protocol_manifest.json").read_text()); contract=ROOT/protocol["protocol_path"]
    assert sha_file(contract)==protocol["protocol_sha256"]
    runs=json.loads((C/"model_seed_schedule/formal_model_seed_schedule.json").read_text())["runs"]
    run=next(row for row in runs if row["arm"]==arm and row["formal_seed"]==seed); run_id=run["run_id"]
    schedule=json.loads((C/"train_v2_batch_schedule/formal_train_v2_batch_schedule.json").read_text())
    epoch0=next(row for row in schedule["epoch_orders"] if row["run_id"]==run_id and row["epoch"]==0)
    first_batch_id=epoch0["base_batch_order"][0]; first_batch=next(row for row in schedule["base_batches"] if row["base_batch_id"]==first_batch_id)
    train_manifest=json.loads((C/"train_v2_batch_schedule/train_case_cache_manifest.json").read_text()); train_map={row["record_id"]:row for row in train_manifest["cases"]}
    train_cases=[case_from_row(train_map[row["record_id"]]) for row in first_batch["records"]]; assert len(train_cases)==112
    val_manifest=json.loads((C/"validation_target_construction/validation_case_cache_manifest.json").read_text()); val_by_lineage={lineage:[] for lineage in FRESH}
    for row in val_manifest["cases"]: val_by_lineage[row["lineage"]].append(case_from_row(row))
    assert all(len(rows)==64 for rows in val_by_lineage.values()); phases["cases_loaded"]=rss_peak()
    model,adapter=fresh(arm,seed,run["initial_parameter_sha256"]); model.train(); before=q.parameter_hash(model)
    t0=time.perf_counter()
    with sdpa_kernel(SDPBackend.MATH): train_loss=adapter(train_cases)
    train_forward_seconds=time.perf_counter()-t0; train_safe=adapter.last_trace["safe"]; phases["forward_peak"]=rss_peak()
    t0=time.perf_counter(); train_loss.backward(); backward_seconds=time.perf_counter()-t0; phases["backward_peak"]=rss_peak()
    gradients=[parameter.grad for parameter in adapter.parameters()]
    gradient_finite=all(gradient is not None and torch.isfinite(gradient).all() for gradient in gradients)
    gradient_norm=float(torch.sqrt(sum(gradient.detach().square().sum() for gradient in gradients if gradient is not None)))
    clip_return=float(torch.nn.utils.clip_grad_norm_(adapter.parameters(),1.0)); clipped_norm=float(torch.sqrt(sum(parameter.grad.detach().square().sum() for parameter in adapter.parameters())))
    parameter_unchanged=q.parameter_hash(model)==before
    opt=optimizer(adapter); sched=scheduler(opt); optimizer_empty=len(opt.state_dict()["state"])==0
    phases["optimizer_state_peak"]=rss_peak(); scheduler_lr=float(opt.param_groups[0]["lr"])
    opt.zero_grad(set_to_none=True); model.eval(); val_losses={}; val_safety={}; validation_seconds={}
    for lineage in FRESH:
        t0=time.perf_counter()
        with torch.no_grad(),sdpa_kernel(SDPBackend.MATH): value=adapter(val_by_lineage[lineage])
        validation_seconds[lineage]=time.perf_counter()-t0; val_losses[lineage]=float(value); val_safety[lineage]=adapter.last_trace["safe"]
    validation_L=math_fsum(val_losses.values())/4.; validation_Q=float(np.sqrt(validation_L)); phases["validation_peak"]=rss_peak()
    model.train(); first_case=train_cases[0]
    with torch.no_grad(),sdpa_kernel(SDPBackend.MATH):
        state,history,output,graph,token=adapter.start_audit(first_case)
        structure=q.audit_stage(arm=arm,model=model,state=state,history=history,stage="start",reference_output=output,reference_graph=graph,reference_token=token)
    phases["structure_peak"]=rss_peak(); sealed=denial_preflight(); checkpoint_rng=rng_payload()
    checkpoint={"model":model.state_dict(),"optimizer":opt.state_dict(),"scheduler":sched.state_dict(),"RNG":checkpoint_rng,
        "update":0,"protocol_hash":protocol["protocol_sha256"],"run_id":run_id,"architecture_hash":run["architecture_sha256"],
        "parameter_hash":before,"batch_order_state":{"epoch":0,"base_batch_id":first_batch_id,"next_update":1},
        "TRAIN_metrics":{"L_def_v2":float(train_loss.detach()),"Q_def_v2":float(torch.sqrt(train_loss.detach()))},
        "fresh_validation_metrics":{"L_def_v2":validation_L,"Q_def_v2":validation_Q,"per_lineage_L":val_losses},
        "scale_hash":SCALE_HASH,"target_manifest_hash":run["target_manifest_sha256"],"backend":run["backend"]}
    buffer=io.BytesIO(); t0=time.perf_counter(); torch.save(checkpoint,buffer); serialization_seconds=time.perf_counter()-t0
    payload=buffer.getvalue(); phases["checkpoint_serialization_peak"]=rss_peak(); restore_rng(checkpoint_rng)
    model.eval()
    with torch.no_grad(),sdpa_kernel(SDPBackend.MATH): original_next=float(adapter(train_cases))
    original_rng=next_rng()
    re_model,re_adapter=fresh(arm,seed,run["initial_parameter_sha256"]); re_opt=optimizer(re_adapter); re_sched=scheduler(re_opt)
    t0=time.perf_counter(); loaded=torch.load(io.BytesIO(payload),map_location="cpu",weights_only=False)
    re_model.load_state_dict(loaded["model"]); re_opt.load_state_dict(loaded["optimizer"]); re_sched.load_state_dict(loaded["scheduler"]); restore_rng(loaded["RNG"])
    reload_seconds=time.perf_counter()-t0; re_model.eval()
    with torch.no_grad(),sdpa_kernel(SDPBackend.MATH): reloaded_next=float(re_adapter(train_cases))
    reloaded_rng=next_rng(); phases["checkpoint_reload_peak"]=rss_peak()
    equality={"parameter_bitwise":q.parameter_hash(re_model)==before,"empty_pre_step_optimizer_identity":len(re_opt.state_dict()["state"])==0 and re_opt.state_dict()==opt.state_dict(),
              "scheduler_identity":re_sched.state_dict()==sched.state_dict(),"RNG_exact":original_rng==reloaded_rng,
              "exact_next_TRAIN_forward":original_next==reloaded_next,"protocol_hash":loaded["protocol_hash"]==protocol["protocol_sha256"],
              "run_id":loaded["run_id"]==run_id,"architecture_hash":loaded["architecture_hash"]==run["architecture_sha256"],
              "parameter_hash_field":loaded["parameter_hash"]==before,"batch_order_state":loaded["batch_order_state"]==checkpoint["batch_order_state"],
              "scale_hash":loaded["scale_hash"]==SCALE_HASH,"target_manifest_hash":loaded["target_manifest_hash"]==run["target_manifest_sha256"],
              "backend":loaded["backend"]==run["backend"],"update_zero":loaded["update"]==0}
    peak=max(phases.values()); peak_delta=peak-baseline
    passed=bool(np.isfinite(float(train_loss.detach())) and np.isfinite(validation_L) and train_safe and all(val_safety.values())
                and gradient_finite and gradient_norm>0 and parameter_unchanged and optimizer_empty and abs(scheduler_lr-1e-6)<=1e-20
                and structure["pass"] and sealed["pass"] and all(equality.values()) and peak_delta<=RESOURCE_GATE)
    result={"schema":"sph-pio-poc.stage07c.zero-step-identity.v1","run_id":run_id,"arm":arm,"formal_seed":seed,
        "fresh_OS_process":True,"pid":PROCESS.pid,"protocol_sha256":protocol["protocol_sha256"],"initial_parameter_sha256":before,
        "first_TRAIN_batch":first_batch_id,"train_case_count":112,"validation_case_count":256,
        "train_L_def_v2":float(train_loss.detach()),"train_Q_def_v2":float(torch.sqrt(train_loss.detach())),
        "validation_L_def_v2":validation_L,"validation_Q_def_v2":validation_Q,"validation_per_lineage_L_def_v2":val_losses,
        "gradient":{"finite":gradient_finite,"L2":gradient_norm,"clip_return":clip_return,"clipped_L2":clipped_norm},
        "parameter_hash_unchanged":parameter_unchanged,"optimizer_created":True,"optimizer_state_empty_pre_step":optimizer_empty,
        "scheduler_created":True,"scheduler_lr_update0":scheduler_lr,"structure_smoke":structure,"sealed_test_denial":sealed,
        "checkpoint":{"schema_fields":sorted(checkpoint),"sha256":sha_bytes(payload),"bytes":len(payload),"equality":equality,
                      "temporary_payload_destroyed_after_result":True},
        "timing_seconds":{"train_forward":train_forward_seconds,"backward":backward_seconds,"validation_chunks":validation_seconds,
                          "checkpoint_serialization":serialization_seconds,"checkpoint_reload":reload_seconds,"total":time.perf_counter()-started},
        "memory":{"rss_baseline_bytes":baseline,"phases":phases,"peak_rss_bytes":peak,"peak_rss_delta_bytes":peak_delta,
                  "gate_bytes":RESOURCE_GATE,"pass":peak_delta<=RESOURCE_GATE},
        "counters":{"formal_optimizer_steps":0,"formal_parameter_updates":0,"formal_training_runs":0,
                    "saved_training_checkpoints":0,"sealed_test_evaluations":0,"rollouts":0},"pass":passed}
    out=C/f"zero_step_preflight/identities/{run_id}.json"; write_json(out,result)
    del model,adapter,opt,sched,checkpoint,payload,loaded,re_model,re_adapter,re_opt,re_sched,train_cases,val_by_lineage; gc.collect()
    result["memory"]["post_destruction_rss_bytes"]=PROCESS.memory_info().rss; write_json(out,result)
    print(json.dumps({"run_id":run_id,"pass":passed,"train_Q":result["train_Q_def_v2"],"validation_Q":validation_Q,
                      "peak_delta":peak_delta,"checkpoint_bytes":result["checkpoint"]["bytes"],"wall":result["timing_seconds"]["total"]},sort_keys=True),flush=True)


def math_fsum(values: Any) -> float:
    import math
    return math.fsum(values)


if __name__=="__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("--arm",choices=ARMS,required=True); parser.add_argument("--seed",type=int,choices=SEEDS,required=True)
    args=parser.parse_args(); main(args.arm,args.seed)
