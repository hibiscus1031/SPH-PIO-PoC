"""After contract freeze, verify all TRAIN targets and cache the frozen 48-origin batch."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import torch


HERE=Path(__file__).resolve(); STAGE05C=HERE.parents[1]; STAGE05=HERE.parents[3]; ROOT=HERE.parents[4]
STAGE04B=ROOT/"stage_04_Local_Causal_Dynamic_Training/04_reference_family_pool/stage04b"; STAGE03C=ROOT/"stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c"
sys.path[:0]=[str(STAGE03C),str(ROOT/"01_solver"),str(STAGE04B/"formula_templates")]
from baseline_d0.state import DynamicParticleState,eos_pressure
from graph_rebuild.graph import build_reciprocal_graph
from stage04b_reference_core import CS,L,RHO0,SUPPORT_OVER_DX,evaluate_symbolic
from tokenization.tokens import build_node_token


def sha_file(path:Path)->str: return "sha256:"+hashlib.sha256(path.read_bytes()).hexdigest()
def write_json(path:Path,value:Any)->None: path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(value,indent=2,sort_keys=True)+"\n")
def import_access()->Any:
    p=STAGE05C/"access_control/stage05c_train_access.py"; s=importlib.util.spec_from_file_location("a",p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
ACCESS=import_access()
DECODE={"train_target_npz_decode_count":0,"train_target_json_decode_count":0,"train_trajectory_npz_decode_count":0,"train_trajectory_json_decode_count":0,
        "validation_state_decode_count":0,"validation_target_decode_count":0,"sealed_formula_decode_count":0,"sealed_state_decode_count":0,"sealed_source_decode_count":0,
        "sealed_target_decode_count":0,"sealed_origin_decode_count":0}


def denial(phase:str)->dict[str,Any]:
    probes={"validation_state":STAGE04B/"access_control/validation_private/lcdf_02_variant_main_n8.npz",
      "validation_target":STAGE04B/"access_control/validation_private/lcdf_09_variant_main_n8.npz",
      "sealed_formula":STAGE04B/"sealed_test/private/sealed_parameters.json","sealed_state":STAGE04B/"sealed_test/private/lcdf_03_variant_main_n8.npz",
      "sealed_source":STAGE04B/"sealed_test/private/lcdf_10_variant_main_n8.npz","sealed_target":STAGE04B/"sealed_test/private/lcdf_03_variant_low_n8.npz",
      "sealed_origin":STAGE04B/"sealed_test/private/lcdf_10_variant_low_n8.npz"}
    rows=[]
    for kind,path in probes.items():
        try: ACCESS.read_bytes(path); ok=False
        except PermissionError: ok=True
        rows.append({"kind":kind,"denied_before_payload_read":ok,"path":str(path.relative_to(ROOT))})
    out={"phase":phase,"rows":rows,"decode_counts":dict(DECODE),"pass":all(r["denied_before_payload_read"] for r in rows)}
    write_json(STAGE05C/f"access_control/{phase}_allowlist_denial_audit.json",out); return out


def tensor(a:np.ndarray)->torch.Tensor: return torch.from_numpy(np.ascontiguousarray(a)).to(torch.float64)
def make_state(arrays:dict[str,np.ndarray],N:int,frame:int)->DynamicParticleState:
    idx=int(np.flatnonzero(arrays["frame_n"]==frame)[0]); rho=tensor(arrays["density"][idx]); dx=L/N; count=N*N
    return DynamicParticleState(tensor(arrays["position_unwrapped"][idx]),tensor(arrays["velocity"][idx]),rho,eos_pressure(rho),
      torch.full((count,),RHO0*dx*dx,dtype=torch.float64),torch.full((count,),SUPPORT_OVER_DX*dx,dtype=torch.float64),tensor(arrays["material_labels"]),
      float(arrays["physical_time"][idx]),frame)


def main()->None:
    freeze=json.loads((STAGE05C/"freeze/stage05c_freeze_record.json").read_text()); assert freeze["frozen_before_first_target_record_decode"] and freeze["target_record_decode_count_at_freeze"]==0
    start=denial("start"); assert start["pass"]
    batches=json.loads((STAGE05C/"batch_selection/preregistered_batches.json").read_text()); selected={(r["lineage"],r["variant"],o) for r in batches["selection"] for o in r["origins"]}
    target_manifest=json.loads((STAGE05/"09_manifests/stage05b_target_manifest.json").read_text()); assert target_manifest["record_count"]==384
    target_values={}; loss=[]
    for entry in target_manifest["records"]:
        npz=ACCESS.load_npz(ROOT/entry["npz_path"]); DECODE["train_target_npz_decode_count"]+=1
        loss.append(float(np.mean(npz["y_def"]**2)))
        parts=entry["record_id"].split("_"); key=("_".join(parts[:2]),"_".join(parts[2:4]),int(parts[-1][1:]))
        if key in selected:
            meta=ACCESS.load_json(ROOT/entry["json_path"]); DECODE["train_target_json_decode_count"]+=1
            assert sha_file(ROOT/entry["npz_path"])==entry["npz_sha256"]
            target_values[key]={"a_cons":npz["a_cons"],"a_def":npz["a_def"],"y_def":npz["y_def"],"meta":meta}
    zero=float(np.mean(loss)); assert abs(zero-1)<=1e-12 and len(target_values)==48
    cache_dir=STAGE05C/"batch_selection/case_cache"; cache_dir.mkdir(parents=True,exist_ok=True); cache=[]
    for row in batches["selection"]:
        lineage,variant=row["lineage"],row["variant"]; stem=f"{lineage.lower()}_{variant.lower()}_n8"
        arrays=ACCESS.load_npz(STAGE04B/f"exact_trajectories/train/{stem}.npz"); meta=ACCESS.load_json(STAGE04B/f"exact_trajectories/train/{stem}.json")
        DECODE["train_trajectory_npz_decode_count"]+=1; DECODE["train_trajectory_json_decode_count"]+=1; assert meta["role"]=="TRAIN_LINEAGE"
        for origin in row["origins"]:
            key=(lineage,variant,origin); target=target_values[key]; frames=list(range(origin-3,origin+1)); states=[make_state(arrays,8,f) for f in frames]
            tokens=torch.stack([build_node_token(s,build_reciprocal_graph(s)) for s in states],dim=1).numpy()
            current_idx=int(np.flatnonzero(arrays["frame_n"]==origin)[0]); accepted_idx=int(np.flatnonzero(arrays["frame_n"]==origin+1)[0])
            source_mid=evaluate_symbolic(lineage,variant,arrays["material_labels"],(origin+.5)/256.)["source"]
            v0=arrays["velocity"][accepted_idx]-(L/CS/256.)*target["a_def"]
            rid=f"{lineage}_{variant}_N8_O{origin:02d}"; path=cache_dir/f"{rid}.npz"
            np.savez_compressed(path,frames=np.asarray(frames),physical_times=np.asarray([s.physical_time for s in states]),
              x=np.stack([s.x_unwrapped.numpy() for s in states]),velocity=np.stack([s.velocity.numpy() for s in states]),density=np.stack([s.density.numpy() for s in states]),
              material_labels=arrays["material_labels"],mass=states[-1].mass.numpy(),smoothing=states[-1].smoothing_length.numpy(),history_tokens=tokens,
              source_start=arrays["external_source"][current_idx],source_midpoint=source_mid,v0_accepted=v0,a_cons=target["a_cons"],y_def=target["y_def"])
            cache.append({"record_id":rid,"lineage":lineage,"variant":variant,"origin":origin,"path":str(path.relative_to(ROOT)),"sha256":sha_file(path),
                          "target_canonical_sha256":target["meta"]["canonical_sha256"]})
    out={"schema":"sph-pio-poc.stage05c.cached-formal-batch.v1","contract_sha256":freeze["contract_sha256"],"case_count":len(cache),"zero_correction_baseline_all384":zero,
         "zero_correction_absolute_error":abs(zero-1),"cases":cache,"decode_counts":DECODE,"target_values_enter_tokens":False,"pass":len(cache)==48 and abs(zero-1)<=1e-12}
    write_json(STAGE05C/"batch_selection/cached_formal_batch_manifest.json",out); print(json.dumps({"cases":len(cache),"zero_loss":zero,"decode_counts":DECODE}))


if __name__=="__main__": main()
