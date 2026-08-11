"""Freeze Stage 05C model identities, groups, batches, probes, and YAML before target decode."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import torch
import yaml


HERE=Path(__file__).resolve(); STAGE05C=HERE.parents[1]; STAGE05=HERE.parents[3]; ROOT=HERE.parents[4]
STAGE03C=ROOT/"stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c"
sys.path[:0]=[str(STAGE03C),str(ROOT/"01_solver")]
from arm_d1.model import D1InstantaneousPairMLP
from arm_d2.model import D2CausalRecurrentPairPIO
from arm_d3.model import D3CausalTemporalTransformerPIO


SEEDS=[20500501,20500502,20500503]; LINEAGES=["LCDF_01","LCDF_04","LCDF_05","LCDF_06","LCDF_07","LCDF_08"]
VARIANTS=["VARIANT_LOW","VARIANT_MAIN"]; ARMS={"D1":D1InstantaneousPairMLP,"D2":D2CausalRecurrentPairPIO,"D3":D3CausalTemporalTransformerPIO}


def canonical(value:Any)->bytes: return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def sha_bytes(value:bytes)->str: return "sha256:"+hashlib.sha256(value).hexdigest()
def sha_file(path:Path)->str: return sha_bytes(path.read_bytes())
def write_json(path:Path,value:Any)->None:
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(value,indent=2,sort_keys=True,ensure_ascii=False)+"\n",encoding="utf-8")
def tensor_bytes(value:torch.Tensor)->bytes:
    a=value.detach().contiguous().cpu().numpy(); return str(a.dtype).encode()+b"\0"+np.asarray(a.shape,dtype=np.int64).tobytes()+a.tobytes()
def parameter_hash(model:torch.nn.Module)->str:
    h=hashlib.sha256()
    for name,p in model.named_parameters(): h.update(name.encode()); h.update(tensor_bytes(p))
    return "sha256:"+h.hexdigest()


def group_for(arm:str,name:str)->tuple[str,dict[str,Any]]:
    entry={"tensor_path":name,"slice":"all"}
    if arm=="D1": return (("D1_TOKEN_ENCODER" if name.startswith("encoder.") else "D1_PAIR_HEAD"),entry)
    if arm=="D2":
        if name.startswith("encoder."): group="D2_TOKEN_ENCODER"
        elif name.startswith("recurrent."): group="D2_GRU"
        else: group="D2_PAIR_HEAD"
        return group,entry
    if name=="relative_offset_embedding" or name.startswith("encoder."): return "D3_TOKEN_ENCODER",entry
    if name.startswith("pair_head."): return "D3_PAIR_HEAD",entry
    if ".self_attn.in_proj_" in name: raise RuntimeError("split tensor requires explicit slices")
    if ".self_attn.out_proj." in name: return "D3_ATTENTION_O",entry
    return "D3_FEED_FORWARD",entry


models=[]; group_maps={}; schema_by_arm={}
for arm,cls in ARMS.items():
    torch.manual_seed(SEEDS[0]); schema_model=cls().to(dtype=torch.float64,device="cpu")
    groups:dict[str,list[dict[str,Any]]]={}
    named=dict(schema_model.named_parameters())
    for name,p in named.items():
        if arm=="D3" and ".self_attn.in_proj_" in name:
            width=p.shape[0]//3
            for label,start in (("Q",0),("K",width),("V",2*width)):
                entry={"tensor_path":name,"slice_dim0":[start,start+width],"slice":f"dim0[{start}:{start+width}]",
                       "shape":[width,*p.shape[1:]],"element_count":int(width*np.prod(p.shape[1:] or (1,)))}
                groups.setdefault(f"D3_ATTENTION_{label}",[]).append(entry)
        else:
            group,entry=group_for(arm,name); entry.update({"shape":list(p.shape),"element_count":p.numel()}); groups.setdefault(group,[]).append(entry)
    expected={"D1":["D1_TOKEN_ENCODER","D1_PAIR_HEAD"],"D2":["D2_TOKEN_ENCODER","D2_GRU","D2_PAIR_HEAD"],
              "D3":["D3_TOKEN_ENCODER","D3_ATTENTION_Q","D3_ATTENTION_K","D3_ATTENTION_V","D3_ATTENTION_O","D3_FEED_FORWARD","D3_PAIR_HEAD"]}[arm]
    assert set(groups)==set(expected)
    group_rows=[]
    for group in expected:
        entries=groups[group]; count=sum(e["element_count"] for e in entries)
        group_rows.append({"group":group,"entries":entries,"element_count":count,"flatten_order":"named_parameters then C-order within frozen slice",
                           "group_schema_sha256":sha_bytes(canonical(entries))})
    assert sum(g["element_count"] for g in group_rows)==sum(p.numel() for p in schema_model.parameters())
    group_maps[arm]=group_rows
    schema=[{"name":n,"shape":list(p.shape),"count":p.numel()} for n,p in schema_model.named_parameters()]
    sources=[STAGE03C/f"arm_{arm.lower()}/model.py",STAGE03C/"pair_force_head/head.py"]
    schema_by_arm[arm]={"parameter_count":sum(p.numel() for p in schema_model.parameters()),"parameter_schema":schema,
        "architecture_sha256":sha_bytes(canonical({"schema":schema,"sources":[sha_file(p) for p in sources]}))}
    del schema_model
    for seed in SEEDS:
        torch.manual_seed(seed); model=cls().to(dtype=torch.float64,device="cpu")
        module_hashes={name or "<root>":sha_bytes(b"".join(tensor_bytes(p) for p in module.parameters(recurse=False)))
                       for name,module in model.named_modules() if any(True for _ in module.parameters(recurse=False))}
        models.append({"arm":arm,"seed":seed,"architecture_sha256":schema_by_arm[arm]["architecture_sha256"],
            "complete_parameter_sha256":parameter_hash(model),"parameter_count":sum(p.numel() for p in model.parameters()),"module_hashes":module_hashes,
            "backend":"CPU_FLOAT64_SDPBackend.MATH"})
        del model
write_json(STAGE05C/"model_instantiation/preregistered_model_identities.json",{"prefreeze_introspection_model_instances":3,"freeze_model_instances":9,
    "formal_model_instances_planned":9,"seeds":SEEDS,"models":models,"architecture":schema_by_arm,"fresh_initialization":True,"historical_weights_read":False})
write_json(STAGE05C/"parameter_groups/preregistered_parameter_groups.json",{"groups":group_maps,"coverage_unique":True,"coverage_complete":True})

selection=[]
for lineage in LINEAGES:
    for variant in VARIANTS:
        ranked=sorted((hashlib.sha256(("stage05c_origin_selection_v1"+lineage+variant+str(o)).encode()).hexdigest(),o) for o in range(32))
        selection.append({"lineage":lineage,"variant":variant,"origins":[o for _,o in ranked[:4]],"keys":["sha256:"+h for h,_ in ranked[:4]]})
resolution=[]
for N in (12,16):
    for lineage in LINEAGES:
        h=hashlib.sha256(("stage05c_resolution_origin_v1"+str(N)+lineage).encode()).hexdigest()
        resolution.append({"resolution":N,"lineage":lineage,"variant":"VARIANT_MAIN","origin":int(h[:16],16)%32,"key":"sha256:"+h})
batches={"schema":"sph-pio-poc.stage05c.batch-selection.v1","rule":"four smallest SHA256 keys per lineage/variant","selection":selection,
         "lineage_context_count_per_arm":18,"global_context_count_per_arm":3,"global_origin_count":48,"resolution_diagnostics":resolution}
write_json(STAGE05C/"batch_selection/preregistered_batches.json",batches)

probe_contexts=[]
for arm,rows in group_maps.items():
    for group_row in rows:
        group=group_row["group"]; count=group_row["element_count"]
        for lineage in LINEAGES:
            for seed in SEEDS:
                used=[]; coords=[]
                for slot in range(3):
                    key=hashlib.sha256(("stage05c_coordinate_v1"+arm+group+lineage+str(seed)+str(slot)).encode()).hexdigest(); index=int(key[:16],16)%count
                    while index in used: index=(index+1)%count
                    used.append(index); coords.append({"slot":slot,"group_flat_index":index,"key":"sha256:"+key})
                starts=[]; blocks=[]; size=min(32,count)
                for slot in range(2):
                    key=hashlib.sha256(("stage05c_block_v1"+arm+group+lineage+str(seed)+str(slot)).encode()).hexdigest(); start=int(key[:16],16)%count
                    while start in starts: start=(start+1)%count
                    starts.append(start); indices=[(start+j)%count for j in range(size)]
                    dkey=hashlib.sha256(("stage05c_block_direction_v1"+arm+group+lineage+str(seed)+str(slot)).encode()).digest()
                    raw=b""; counter=0
                    while len(raw)*8<size: raw+=hashlib.sha256(dkey+counter.to_bytes(8,"big")).digest(); counter+=1
                    bits=np.unpackbits(np.frombuffer(raw,dtype=np.uint8))[:size]; signs=(2*bits.astype(int)-1).tolist()
                    blocks.append({"slot":slot,"start":start,"indices":indices,"rademacher_signs":signs,"l2_normalization":float(math.sqrt(size)) if False else f"sqrt({size})",
                                   "key":"sha256:"+key,"direction_key":"sha256:"+dkey.hex()})
                probe_contexts.append({"arm":arm,"group":group,"lineage":lineage,"seed":seed,"group_element_count":count,"coordinates":coords,"blocks":blocks})
probe_plan={"schema":"sph-pio-poc.stage05c.probe-plan.v1","context_count":len(probe_contexts),"probe_count":len(probe_contexts)*5,
            "epsilon_ladder":[1e-2,3e-3,1e-3,3e-4,1e-4,3e-5],"contexts":probe_contexts}
write_json(STAGE05C/"parameter_groups/preregistered_probe_plan.json",probe_plan)

model_path=STAGE05C/"model_instantiation/preregistered_model_identities.json"; groups_path=STAGE05C/"parameter_groups/preregistered_parameter_groups.json"
batch_path=STAGE05C/"batch_selection/preregistered_batches.json"; probe_path=STAGE05C/"parameter_groups/preregistered_probe_plan.json"
contract={
 "contract_id":"optimizer_aligned_defect_gradient_contract_v0_1","schema":"sph-pio-poc.stage05c.contract.v1",
 "authorization":{"required_status":"CONSERVATIVE_DISCRETE_DEFECT_TARGET_AND_SCALE_QUALIFIED","stage05b_contract_sha256":"sha256:6992ce3e9e7aa76b2b29fc3e6b15ac5533386ce9bee07c5d7316b5ee9609b9dc",
   "s_a":3.45632855338432798e-1,"s_a_hash":"sha256:78beec16affbae72345d220b7f7c1455f85c212ad006c4d29516946d5c76f296","u_a":7.27595761418342590e-10,"target_records":384},
 "backend":{"device":"CPU","dtype":"float64","sdpa":"SDPBackend.MATH","flash":False,"memory_efficient":False,"auto_selection":False},
 "models":{"seeds":SEEDS,"identity_manifest":str(model_path.relative_to(ROOT)),"identity_manifest_sha256":sha_file(model_path),"fresh":True,"checkpoint_reads":False},
 "parameter_groups":{"manifest":str(groups_path.relative_to(ROOT)),"manifest_sha256":sha_file(groups_path),"unique_complete":True},
 "batches":{"manifest":str(batch_path.relative_to(ROOT)),"manifest_sha256":sha_file(batch_path),"N8_lineage_batch":"2 variants x 4 origins","global":"6 lineages x 2 variants x 4 origins"},
 "probes":{"manifest":str(probe_path.relative_to(ROOT)),"manifest_sha256":sha_file(probe_path),"coordinates_per_context":3,"blocks_per_context":2,"block_size":"min(32,group_count)","cyclic_indices":True,"block_direction":"hash Rademacher normalized to L2=1"},
 "loss":{"identity":"nested mean over lineage/variant/origin/node/component of ((a_eff-a_cons)/s_a)^2","a_eff":"(v_theta^(n+1)-v_0^(n+1))/dt","zero_correction_loss":1.0,"tolerance":1e-12},
 "full_gradient":{"repeats":2,"noise":"max(RMS(g1-g2),128*eps*max(1,RMS(g1)))","activity_ratio_min":100,"finite":True,"parameter_hash_unchanged":True},
 "reverse_jvp":{"genuine_forward_jvp":True,"abs_max":1e-10,"rel_max":1e-7,"near_zero_below":1e-12,"near_zero_abs_max":1e-12,"required_fraction":1.0},
 "finite_difference":{"epsilon_ladder":[1e-2,3e-3,1e-3,3e-4,1e-4,3e-5],"central":True,"plus_minus_repeats":2,"coordinate_scale":"max(1,abs(theta_j))",
   "block_scale":"max(1,block_parameter_RMS)","fd_ad_abs_max":1e-8,"fd_ad_rel_max":1e-4,"adjacent_relative_change_max":1e-3,"minimum_smooth_epsilons":3,"stable_adjacent_count_min":2,
   "near_zero_fd_abs_max":1e-8,"fresh_state_history":True,"fixed_rng":True,"complete_RK2":True},
 "aggregation":{"group_lineage_seed":"active and 5/5 probes stable and >=1 nonzero and safe deterministic restored","group_lineage":"at least 2/3 seeds","group":"6/6 lineages","arm":"all groups"},
 "local_descent":{"radii":[1e-6,3e-6,1e-5,3e-5,1e-4,3e-4],"direction":"-g/max(norm(g),1e-30)","theta_norm_ref":"max(norm(theta),sqrt(P)*1e-3)",
   "loss_floor":"max(abs(L1-L2),128*eps*max(1,abs(Lbase)))","observed_below":"-100*u_L","ratio_range":[.20,1.80],"adjacent_pass_min":2,
   "lineage":"at least 2/3 seeds for each of 6/6","global":"3/3 seeds","optimizer":False,"writeback":False},
 "structure_safety":{"contexts":"arm x seed x lineage","force_residual_max":1e-10,"transforms":["permutation","edge_reorder","translation","Galilean","SO2","reflection","periodic_shift"],
   "positive_density":True,"finite_hidden_coefficients":True,"deterministic_topology":True,"accepted_commit":"one for D2/D3, zero for D1","midpoint_commit":0},
 "resolution_diagnostics":{"N12":"6 MAIN lineages x 3 arms x seed20500501 x hashed origin","N16":"D3 x 6 MAIN lineages x seed20500501 x hashed origin","role":"diagnostic_only","uses_N8_s_a":True},
 "access":{"TRAIN_only":True,"start_end_denial":True,"validation_and_sealed_decode_counts":0},
 "resources":{"peak_rss_delta_max_bytes":1610612736,"no_monotonic_retained_autograd":True,"no_persistent_mutation":True,"no_dense_particle_N_by_N":True,"all_hashes":True},
 "prohibitions":{"optimizer_instances":0,"optimizer_steps":0,"persistent_parameter_updates":0,"training_runs":0,"neural_rollouts":0,"performance_evaluations":0,"checkpoint_selection":0,"model_ranking":0},
 "terminal_statuses":{"qualified":"OPTIMIZER_ALIGNED_DEFECT_GRADIENT_AND_LOCAL_DESCENT_QUALIFIED","not_qualified":"OPTIMIZER_ALIGNED_DEFECT_GRADIENT_AND_LOCAL_DESCENT_NOT_QUALIFIED","incomplete":"OPTIMIZER_ALIGNED_DEFECT_GRADIENT_AND_LOCAL_DESCENT_EVIDENCE_INCOMPLETE"}
}
contract_path=STAGE05C/"contracts/optimizer_aligned_defect_gradient_contract_v0_1.yaml"; contract_path.write_text(yaml.safe_dump(contract,sort_keys=False,allow_unicode=True),encoding="utf-8")
inputs=[
 "stage_05_Scale_Aware_Discrete_Defect_Training/09_manifests/stage05b_final_manifest.json",
 "stage_05_Scale_Aware_Discrete_Defect_Training/09_manifests/stage05b_target_manifest.json",
 "stage_05_Scale_Aware_Discrete_Defect_Training/09_manifests/stage05b_scale_manifest.json",
 "stage_05_Scale_Aware_Discrete_Defect_Training/09_manifests/stage05b_uncertainty_manifest.json",
 "stage_05_Scale_Aware_Discrete_Defect_Training/09_manifests/stage05b_origin_manifest.json",
 "stage_05_Scale_Aware_Discrete_Defect_Training/08_reports/stage05b_final_report.md",
 "stage_04_Local_Causal_Dynamic_Training/09_manifests/stage04b_role_assignment_manifest.json",
 "stage_04_Local_Causal_Dynamic_Training/09_manifests/stage04b_test_seal_manifest.json",
 "stage_04_Local_Causal_Dynamic_Training/09_manifests/stage04cs_final_manifest.json",
 "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c/arm_d1/model.py",
 "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c/arm_d2/model.py",
 "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c/arm_d3/model.py",
 "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c/rk2_core/solver.py",
 "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c/graph_rebuild/graph.py",
 "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c/temporal_history/history.py",
]
freeze={"schema":"sph-pio-poc.stage05c.freeze-record.v1","contract_path":str(contract_path.relative_to(ROOT)),"contract_sha256":sha_file(contract_path),
 "contract_size_bytes":contract_path.stat().st_size,"frozen_before_first_target_record_decode":True,"target_record_decode_count_at_freeze":0,
 "model_identity_sha256":sha_file(model_path),"parameter_group_sha256":sha_file(groups_path),"batch_sha256":sha_file(batch_path),"probe_plan_sha256":sha_file(probe_path),
 "inputs":[{"path":p,"sha256":sha_file(ROOT/p),"size_bytes":(ROOT/p).stat().st_size} for p in inputs],"historical_files_modified":0}
write_json(STAGE05C/"freeze/stage05c_freeze_record.json",freeze)
print(json.dumps({"contract_sha256":freeze["contract_sha256"],"groups":sum(len(v) for v in group_maps.values()),"probe_contexts":len(probe_contexts),"probes":len(probe_contexts)*5}))
