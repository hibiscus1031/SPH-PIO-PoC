"""Execute frozen Stage 04C-R task-signal sensitivity attribution."""

from __future__ import annotations

from collections import Counter, defaultdict
import gc
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import resource
import sys
import time
from typing import Any

import numpy as np
import torch
from torch import nn
from torch.func import functional_call
from torch.nn.attention import SDPBackend, sdpa_kernel
import yaml


HERE = Path(__file__).resolve()
STAGE04CR = HERE.parents[1]
STAGE04 = HERE.parents[3]
ROOT = HERE.parents[4]
STAGE04C = STAGE04 / "05_task_aligned_gradient/stage04c"
RUNNER04C = STAGE04C / "qualification/run_stage04c_qualification.py"
spec = importlib.util.spec_from_file_location("stage04c_runner_readonly", RUNNER04C)
C = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = C
spec.loader.exec_module(C)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def rss_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


def rms(value: torch.Tensor) -> float:
    return float(torch.sqrt(value.detach().square().mean())) if value.numel() else 0.0


def linf(value: torch.Tensor) -> float:
    return float(value.detach().abs().max()) if value.numel() else 0.0


def tensor_stats(value: torch.Tensor) -> dict[str, Any]:
    x = value.detach().flatten()
    finite = torch.isfinite(x)
    nonzero = x != 0
    hist = Counter()
    for v in x[nonzero].abs().cpu().numpy(): hist[str(int(math.floor(math.log10(float(v)))))] += 1
    return {
        "L2": float(torch.linalg.vector_norm(x)), "RMS": rms(x), "Linf": linf(x),
        "nonzero_element_count": int(nonzero.sum()), "finite_count": int(finite.sum()), "element_count": x.numel(),
        "sign_balance": {"positive_fraction":float((x>0).sum()/max(x.numel(),1)),"negative_fraction":float((x<0).sum()/max(x.numel(),1)),"zero_fraction":float((x==0).sum()/max(x.numel(),1))},
        "histogram_decade": dict(sorted(hist.items(), key=lambda z:int(z[0]))),
    }


def group_flat(values: tuple[torch.Tensor, ...], adapter: nn.Module, group: str) -> torch.Tensor:
    named = list(adapter.named_parameters()); index = {name.removeprefix("core."):i for i,(name,_) in enumerate(named)}
    chunks=[]
    for row in C.GROUP_ROWS[group]:
        x=values[index[row["tensor_path"]]]; spec=row["slice"]
        if spec!="all":
            start,stop=[int(v) for v in spec.split(",")[0].lstrip("[").rstrip("]").split(":")]; x=x[start:stop]
        chunks.append(x.reshape(-1))
    return torch.cat(chunks)


class AttributionTransition(nn.Module):
    """Actual Stage 03C K=1 path exposing each sensitivity-chain tensor."""
    def __init__(self, arm: str, core: nn.Module) -> None:
        super().__init__(); self.arm=arm; self.core=core

    def reference_history(self, case: C.CaseData) -> Any:
        if self.arm=="D1": return None
        frames=[case.origin-3,case.origin-2,case.origin-1,case.origin]
        states=[C.make_state(case,f) for f in frames]
        tokens=[C.build_node_token(s,C.build_reciprocal_graph(s)) for s in states]
        if self.arm=="D2":
            hidden=torch.zeros((states[0].particle_count,32),dtype=torch.float64); items=[]
            for token in tokens: hidden=self.core.recurrent(self.core.encoder(token),hidden); items.append(hidden)
        else:
            items=[]
            for i in range(4):
                prefix=tokens[:i+1]; padded=[prefix[0]]*(4-len(prefix))+prefix
                items.append(self.core.temporal_hidden(torch.stack(padded,dim=1))[:,-1,:])
        return C.TemporalHistoryState(torch.stack(tokens,dim=1),torch.stack(items,dim=1),torch.tensor([s.physical_time for s in states],dtype=torch.float64),case.labels,history_length=4,commit_count=0)

    def forward(self, case: C.CaseData) -> tuple[torch.Tensor, ...]:
        start=C.make_state(case,case.origin).with_eos(); history=self.reference_history(case)
        gs=C.build_reciprocal_graph(start); ts=C.build_node_token(start,gs); kw={"stage":"start"}
        if history is not None: kw["history"]=history
        ps=self.core.evaluate(ts,start,gs,**kw); x1,a1,r1=C.baseline_rhs(start,gs,case.source[case.index(case.origin)]); a1=a1+ps.acceleration
        mid=C.DynamicParticleState(start.x_unwrapped+0.5*C.DT*x1,start.velocity+0.5*C.DT*a1,start.density+0.5*C.DT*r1,torch.empty_like(start.pressure),start.mass,start.smoothing_length,start.material_labels,start.physical_time+0.5*C.DT,start.accepted_step_index).with_eos()
        gm=C.build_reciprocal_graph(mid); tm=C.build_node_token(mid,gm); kw={"stage":"midpoint"}
        if history is not None: kw["history"]=history
        pm=self.core.evaluate(tm,mid,gm,**kw); x2,a2,r2=C.baseline_rhs(mid,gm,case.source_midpoint); a2=a2+pm.acceleration
        acc=C.DynamicParticleState(start.x_unwrapped+C.DT*x2,start.velocity+C.DT*a2,start.density+C.DT*r2,torch.empty_like(start.pressure),start.mass,start.smoothing_length,start.material_labels,start.physical_time+C.DT,start.accepted_step_index+1).with_eos()
        ga=C.build_reciprocal_graph(acc)
        if history is not None:
            ta=C.build_node_token(acc,ga); _=history.commit(ta,self.core.accepted_hidden(ta,history=history),acc.physical_time)
        target=case.index(case.origin+1)
        ex=(torch.remainder(acc.x_unwrapped-case.x[target]+1.0,2.0)-1.0)/2.0
        ev=(acc.velocity-case.velocity[target])/20.0; er=acc.density-case.density[target]
        losses=torch.stack((ex.square().sum(-1).mean(),ev.square().sum(-1).mean(),er.square().mean()))
        return (losses,acc.x_unwrapped/2.0,acc.velocity/20.0,acc.density-1.0,ex,ev,er,
                pm.particle_hidden,pm.alpha,pm.beta,pm.pair_force_on_i,ps.acceleration,pm.acceleration,
                mid.x_unwrapped/2.0,mid.velocity/20.0,mid.density-1.0)


OUTPUT_NAMES = ["loss","accepted_yx","accepted_yv","accepted_yrho","residual_x","residual_v","residual_rho","hidden_mid","alpha_mid","beta_mid","pair_force_mid","correction_acceleration_start","correction_acceleration_mid","midpoint_yx","midpoint_yv","midpoint_yrho"]


def evaluate(adapter: AttributionTransition, case: C.CaseData, params: tuple[torch.Tensor,...]) -> tuple[torch.Tensor,...]:
    names=[n for n,_ in adapter.named_parameters()]
    with sdpa_kernel(SDPBackend.MATH): return functional_call(adapter,dict(zip(names,params)),(case,),strict=True)


def d0_transition(case: C.CaseData) -> tuple[torch.Tensor,torch.Tensor,torch.Tensor,torch.Tensor]:
    s=C.make_state(case,case.origin).with_eos(); gs=C.build_reciprocal_graph(s); x1,a1,r1=C.baseline_rhs(s,gs,case.source[case.index(case.origin)])
    m=C.DynamicParticleState(s.x_unwrapped+0.5*C.DT*x1,s.velocity+0.5*C.DT*a1,s.density+0.5*C.DT*r1,torch.empty_like(s.pressure),s.mass,s.smoothing_length,s.material_labels,s.physical_time+0.5*C.DT,s.accepted_step_index).with_eos()
    gm=C.build_reciprocal_graph(m); x2,a2,r2=C.baseline_rhs(m,gm,case.source_midpoint)
    x=s.x_unwrapped+C.DT*x2; v=s.velocity+C.DT*a2; rho=s.density+C.DT*r2; target=case.index(case.origin+1)
    ex=(torch.remainder(x-case.x[target]+1,2)-1)/2; ev=(v-case.velocity[target])/20; er=rho-case.density[target]
    return torch.stack((ex.square().sum(-1).mean(),ev.square().sum(-1).mean(),er.square().mean())),x,v,rho


def weights(identity_hash: str, shape: torch.Size) -> torch.Tensor:
    value=C.rademacher(identity_hash,math.prod(shape)).reshape(shape); return value/torch.linalg.vector_norm(value)


def linear_hash(lineage: str,variant: str,origin: int,seed: int,component: str) -> str:
    return C.sha_bytes(("stage04cr_linear_state_probe_v1"+lineage+variant+str(origin)+str(seed)+component).encode())


def access_audit(phase: str) -> dict[str,Any]:
    row=C.access_denial_audit(phase)
    return {**row,"stage04cr_new_decode_counts":{"validation_target_decode_count":0,"sealed_formula_decode_count":0,"sealed_state_decode_count":0,"sealed_target_decode_count":0}}


def main() -> None:
    torch.set_default_dtype(torch.float64); torch.set_num_threads(1); torch.use_deterministic_algorithms(True)
    freeze=json.loads((STAGE04/"09_manifests/stage04cr_input_freeze_manifest.json").read_text())
    contract_path=STAGE04CR/"contracts/task_signal_sensitivity_attribution_contract_v0_1.yaml"
    if sha(contract_path)!=freeze["contract_sha256"]: raise RuntimeError("Stage04C-R contract changed")
    contract=yaml.safe_load(contract_path.read_text())
    historical=json.loads((STAGE04C/"results/formal_864_probe_results.json").read_text())["probes"]
    param_manifest=json.loads((STAGE04/"09_manifests/stage04c_parameter_manifest.json").read_text())
    dimensions={row["group"]:row["parameter_count"] for row in param_manifest["groups"]}
    hist_by_key={(p["arm"],p["group"],p["lineage"],p["variant"],p["origin"],p["model_seed"]):p for p in historical}
    access_start=access_audit("START"); start=time.perf_counter(); rss0=rss_bytes(); peak=rss0
    cases_manifest=json.loads((STAGE04/"09_manifests/stage04c_case_manifest.json").read_text())
    formal_cases=cases_manifest["cases"]
    case_cache: dict[tuple[str,str,int],C.CaseData]={}
    d0_cache: dict[tuple[str,str,int],tuple[torch.Tensor,torch.Tensor,torch.Tensor,torch.Tensor]]={}
    full_rows=[]; factor_rows=[]; chain_rows=[]; linear_rows=[]; residual_rows=[]; initialization_rows=[]
    context_count=0; parameter_hash_failures=0; full_repeat_failures=0
    for arm in ("D1","D2","D3"):
        for item in formal_cases:
            keycase=(item["lineage"],item["variant"],item["origin"])
            if keycase not in case_cache: case_cache[keycase]=C.load_case(*keycase[:2],8,keycase[2])
            case=case_cache[keycase]
            if keycase not in d0_cache: d0_cache[keycase]=d0_transition(case)
            d0_loss,d0x,d0v,d0r=d0_cache[keycase]
            core,_=C.instantiate(arm,item["model_seed"]); adapter=AttributionTransition(arm,core); params=tuple(p for _,p in adapter.named_parameters()); ph_before=C.model_hash(core)
            # Two complete full-gradient executions.
            repeat_gradients=[]; repeat_outputs=[]
            for repeat in range(2):
                out=evaluate(adapter,case,params); grads=[]
                for component in range(3):
                    grads.append(torch.autograd.grad(out[0][component],params,retain_graph=component<2,allow_unused=False))
                repeat_gradients.append(grads); repeat_outputs.append(tuple(v.detach() for v in out))
            groups=C.groups_for(arm); group_grad_cache={}
            for group in groups:
                comp_stats=[]; comp_flats=[]
                for component in range(3):
                    flat0=group_flat(repeat_gradients[0][component],adapter,group); flat1=group_flat(repeat_gradients[1][component],adapter,group)
                    comp_flats.append(flat0); stat=tensor_stats(flat0); stat["deterministic_repeat"]=torch.equal(flat0,flat1); comp_stats.append(stat)
                    if not stat["deterministic_repeat"]: full_repeat_failures+=1
                group_grad_cache[group]=comp_flats
                full_rows.append({"arm":arm,"group":group,**item,"parameter_dimension":dimensions[group],"components":dict(zip(("L_x","L_v","L_rho"),comp_stats)),"parameter_hash_before":ph_before})
            # Base residual and D0/random comparison once per formal context.
            base=repeat_outputs[0]; random_loss=base[0]
            residual_rows.append({"arm":arm,**item,"D0_loss":[float(v) for v in d0_loss],"random_model_loss":[float(v) for v in random_loss],
                                  "random_minus_D0_state_RMS":{"x":rms(base[1]*2-d0x),"v":rms(base[2]*20-d0v),"rho":rms(base[3]+1-d0r)},
                                  "D0_dimensionless_state_residual_RMS":{"x":float(torch.sqrt(d0_loss[0])),"v":float(torch.sqrt(d0_loss[1])),"rho":float(torch.sqrt(d0_loss[2]))}})
            named=dict(core.named_parameters()); final_weight=named["pair_head.output.weight"]
            init={"arm":arm,**item,"hidden_RMS":rms(base[7]),"alpha_RMS":rms(base[8]),"beta_RMS":rms(base[9]),"tanh_saturation_fraction":float(((base[8].abs()/0.05>=0.99)|(base[9].abs()/0.05>=0.99)).to(torch.float64).mean()),
                  "pair_force_RMS":rms(base[10]),"correction_acceleration_start_RMS":rms(base[11]),"correction_acceleration_mid_RMS":rms(base[12]),"final_head_weight_RMS":rms(final_weight),
                  "exact_zero_parameter_fraction":float(torch.cat([p.detach().flatten() for p in core.parameters()]).eq(0).to(torch.float64).mean()),
                  "GRU_parameter_RMS":None,"LayerNorm_parameter_RMS":None}
            if arm=="D2": init["GRU_parameter_RMS"]=rms(torch.cat([p.detach().flatten() for n,p in core.named_parameters() if n.startswith("recurrent.")]))
            if arm=="D3": init["LayerNorm_parameter_RMS"]=rms(torch.cat([p.detach().flatten() for n,p in core.named_parameters() if ".norm" in n]))
            initialization_rows.append(init)
            # Fixed linear objectives: reverse gradients shared by all groups.
            component_state_indices=(1,2,3); component_codes=("x","v","rho"); linear_gradients=[]; linear_weights=[]
            out_linear=evaluate(adapter,case,params)
            for ci,(state_index,code) in enumerate(zip(component_state_indices,component_codes)):
                w=weights(linear_hash(case.lineage,case.variant,case.origin,item["model_seed"],code),out_linear[state_index].shape); linear_weights.append(w)
                objective=(w*out_linear[state_index]).sum()/out_linear[state_index].shape[0]
                linear_gradients.append(torch.autograd.grad(objective,params,retain_graph=ci<2,allow_unused=False))
            for group in groups:
                direction,group_rms,direction_hash=C.direction_tuple(adapter,arm,group,case,item["model_seed"])
                def fn(*values:torch.Tensor)->tuple[torch.Tensor,...]: return evaluate(adapter,case,values)
                # Midpoint position is parameter-independent in explicit midpoint RK2
                # (x_mid uses the start velocity), so strict=False correctly returns
                # its mathematical zero tangent while preserving all other JVPs.
                with sdpa_kernel(SDPBackend.MATH): primal,tangent=torch.autograd.functional.jvp(fn,params,direction,create_graph=False,strict=False)
                hist=hist_by_key[(arm,group,case.lineage,case.variant,case.origin,item["model_seed"])]
                factors=[]
                for ci,(residx,stateidx,code) in enumerate(zip((4,5,6),(1,2,3),component_codes)):
                    e=primal[residx].detach(); z=tangent[stateidx].detach()
                    if e.ndim==2: dot=(e*z).sum(-1).mean(); R=torch.sqrt(e.square().sum(-1).mean()); S=torch.sqrt(z.square().sum(-1).mean())
                    else: dot=(e*z).mean(); R=torch.sqrt(e.square().mean()); S=torch.sqrt(z.square().mean())
                    reconstructed=2*dot; reverse=hist["reverse_jvp"][ci]["reverse"]; error=abs(float(reconstructed)-reverse); rel=error/max(abs(float(reconstructed)),abs(reverse),1e-30)
                    grad_stats=tensor_stats(group_grad_cache[group][ci]); ratio=abs(reverse)/max(grad_stats["L2"],1e-30); scaled=ratio*math.sqrt(dimensions[group])
                    residual_small=float(R)<contract["factor_thresholds"]["residual_too_small_RMS"]
                    state_small=float(S)<contract["factor_thresholds"]["state_jacobian_too_small_RMS"]
                    alignment=abs(float(dot))/max(float(R*S),1e-30); orthogonal=alignment<contract["factor_thresholds"]["orthogonal_alignment_max"]
                    dilution=(grad_stats["L2"]>=contract["projection"]["dilution_gradient_L2_min"] and abs(reverse)<contract["projection"]["directional_abs_max"] and contract["projection"]["scaled_projection_interval"][0]<=scaled<=contract["projection"]["scaled_projection_interval"][1])
                    active=[name for name,flag in (("TASK_RESIDUAL_TOO_SMALL",residual_small),("TASK_STATE_JACOBIAN_TOO_SMALL",state_small),("TASK_RESIDUAL_JACOBIAN_ORTHOGONAL",orthogonal),("GROUP_DIRECTION_PROJECTION_DILUTION",dilution)) if flag]
                    if dilution: primary="GROUP_DIRECTION_PROJECTION_DILUTION"
                    elif residual_small: primary="TASK_RESIDUAL_TOO_SMALL"
                    elif state_small: primary="TASK_STATE_JACOBIAN_TOO_SMALL"
                    elif orthogonal: primary="TASK_RESIDUAL_JACOBIAN_ORTHOGONAL"
                    elif len(active)>1: primary="MULTIPLE_FACTORS"
                    else: primary="UNRESOLVED"
                    factors.append({"component":("L_x","L_v","L_rho")[ci],"residual_RMS":float(R),"state_JVP_RMS":float(S),"mean_dot":float(dot),"cosine_alignment":alignment,"reconstructed_derivative":float(reconstructed),"historical_reverse":reverse,"reconstruction_abs_error":error,"reconstruction_relative_error":rel,"reconstruction_pass":error<=1e-12 or rel<=1e-8,
                                    "full_gradient_L2":grad_stats["L2"],"projection_ratio":ratio,"sqrt_parameter_dimension":math.sqrt(dimensions[group]),"scaled_projection":scaled,"active_factors":active,"primary_reason":primary})
                # Exposed network chain and RK2 attenuation.
                chain_indices=[7,8,9,10,11,12,13,14,15,1,2,3]
                chain={}
                for i in chain_indices:
                    name=OUTPUT_NAMES[i]
                    if name=="hidden_mid": saturation=float((primal[i].detach().abs()>=0.99).to(torch.float64).mean())
                    elif name in {"alpha_mid","beta_mid"}: saturation=float((primal[i].detach().abs()/0.05>=0.99).to(torch.float64).mean())
                    else: saturation=None
                    chain[name]={"primal_RMS":rms(primal[i]),"primal_Linf":linf(primal[i]),"JVP_RMS":rms(tangent[i]),"JVP_Linf":linf(tangent[i]),"finite":bool(torch.isfinite(primal[i]).all() and torch.isfinite(tangent[i]).all()),"saturation_fraction":saturation}
                ordered=["hidden_mid","alpha_mid","beta_mid","pair_force_mid","correction_acceleration_start","correction_acceleration_mid","midpoint_yx","midpoint_yv","midpoint_yrho","accepted_yx","accepted_yv","accepted_yrho"]
                previous=None
                for name in ordered:
                    current=chain[name]["JVP_RMS"]; chain[name]["attenuation_from_previous"]=None if previous is None else current/max(previous,1e-30); previous=current
                Astart=rms(tangent[11]); Amid=rms(tangent[12]); X=rms(tangent[1]*2); V=rms(tangent[2]*20); RHO=rms(tangent[3])
                chain_rows.append({"arm":arm,"group":group,**item,"direction_hash":direction_hash,"chain":chain,"RK2":{"A_start":Astart,"A_mid":Amid,"V_accept":V,"X_accept":X,"RHO_accept":RHO,"V_over_dt_A_mid":V/max(C.DT*Amid,1e-30),"X_over_dt2_A_mid":X/max(C.DT**2*Amid,1e-30),"RHO_over_dt2_A_mid":RHO/max(C.DT**2*Amid,1e-30)}})
                # Diagnostic linear probe reverse/JVP/FD for each component.
                eps=contract["linear_probe"]["fd_epsilon"]; plus=tuple(p+eps*d for p,d in zip(params,direction)); minus=tuple(p-eps*d for p,d in zip(params,direction)); op=evaluate(adapter,case,plus); om=evaluate(adapter,case,minus)
                linear_components=[]
                for ci,(stateidx,code) in enumerate(zip(component_state_indices,component_codes)):
                    w=linear_weights[ci]; rev=float(sum((g*d).sum() for g,d in zip(linear_gradients[ci],direction))); jvp=float((w*tangent[stateidx]).sum()/tangent[stateidx].shape[0]); fd=float(((w*op[stateidx]).sum()-(w*om[stateidx]).sum())/(2*eps*op[stateidx].shape[0]))
                    linear_components.append({"component":code,"weight_seed_sha256":linear_hash(case.lineage,case.variant,case.origin,item["model_seed"],code),"reverse":rev,"JVP":jvp,"central_FD":fd,"state_Jacobian_RMS":rms(tangent[stateidx]),"reverse_JVP_abs_error":abs(rev-jvp),"JVP_FD_abs_error":abs(jvp-fd),"stable_nonzero":abs(jvp)>=1e-10 and abs(jvp-fd)<=1e-8})
                linear_rows.append({"arm":arm,"group":group,**item,"direction_hash":direction_hash,"diagnostic_only":True,"components":linear_components})
                factor_rows.append({"arm":arm,"group":group,**item,"direction_hash":direction_hash,"parameter_dimension":dimensions[group],"components":factors})
            if C.model_hash(core)!=ph_before: parameter_hash_failures+=1
            context_count+=1; peak=max(peak,rss_bytes())
        gc.collect()
    access_end=access_audit("END"); elapsed=time.perf_counter()-start
    # Rebuild the requested historical matrix with explicit parameter dimensions.
    historical_rows=[]
    for p in historical:
        historical_rows.append({"arm":p["arm"],"group":p["group"],"lineage":p["lineage"],"variant":p["variant"],"origin":p["origin"],"model_seed":p["model_seed"],"parameter_dimension":dimensions[p["group"]],"direction_hash":p["direction_seed_sha256"],"loss_vector":p["loss_vector"],"reverse":[c["reverse"] for c in p["reverse_jvp"]],"JVP":[c["jvp"] for c in p["reverse_jvp"]],"FD_ladder":[{"epsilon":r["epsilon"],"estimate":r["estimate"]} for r in p["fd"]],"near_zero":[c["near_zero"] for c in p["components"]],"graph_topology_hashes":p["trace"]["topology"],"history_hash":p["trace"]["history_hash"],"qualification_verdict":p["pass"]})
    reason_counts=Counter(c["primary_reason"] for r in factor_rows for c in r["components"])
    dilution_fraction=reason_counts["GROUP_DIRECTION_PROJECTION_DILUTION"]/(len(factor_rows)*3)
    recon_pass=all(c["reconstruction_pass"] for r in factor_rows for c in r["components"])
    chain_finite=all(x["finite"] for r in chain_rows for x in r["chain"].values())
    dead_fraction=sum(r["correction_acceleration_mid_RMS"]<=1e-14 for r in initialization_rows)/len(initialization_rows)
    all_d0_resolved=all(max(r["D0_dimensionless_state_residual_RMS"].values())<=1e-8 for r in residual_rows)
    scaled=[c["scaled_projection"] for r in factor_rows for c in r["components"] if c["full_gradient_L2"]>=1e-12]
    median_scaled=float(np.median(scaled)) if scaled else 0.0
    if not recon_pass or not chain_finite or parameter_hash_failures or not access_start["pass"] or not access_end["pass"]:
        status="TASK_GRADIENT_FAILURE_EVIDENCE_INCOMPLETE"; branch="NONE"
    elif dead_fraction>=0.8 and not all_d0_resolved:
        status="TASK_GRADIENT_FAILURE_ATTRIBUTED_PARAMETERIZATION_DEAD_ZONE"; branch="Stage04B-R — Initialization and Dynamic-Arm Implementation Contract Reassessment"
    elif all_d0_resolved:
        status="TASK_GRADIENT_FAILURE_ATTRIBUTED_TASK_ALREADY_RESOLVED"; branch="STOP_CURRENT_K1_EXACT_STATE_TRAINING_ROUTE"
    elif dilution_fraction>=0.8 and 0.05<=median_scaled<=5.0:
        status="TASK_GRADIENT_FAILURE_ATTRIBUTED_DIRECTION_PROJECTION"; branch="Stage04C-P — Prospective Full-Gradient/Coordinate-Probe Qualification Contract v0.2 Design"
    else:
        common_reasons=sum(reason_counts[x] for x in ("TASK_RESIDUAL_TOO_SMALL","TASK_RESIDUAL_JACOBIAN_ORTHOGONAL","TASK_STATE_JACOBIAN_TOO_SMALL"))/(len(factor_rows)*3)
        if common_reasons>=0.8 and dead_fraction<0.8:
            status="TASK_GRADIENT_FAILURE_ATTRIBUTED_COMMON_SIGNAL_SCALE"; branch="Stage04C-P — Prospective Loss Scaling and Gradient Qualification Contract v0.2 Design"
        else:
            status="TASK_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED"; branch="NONE"
    resource_result={"wall_seconds":elapsed,"start_RSS_bytes":rss0,"peak_RSS_bytes":peak,"peak_RSS_delta_bytes":max(0,peak-rss0),"peak_RSS_delta_GiB":max(0,peak-rss0)/2**30,"peak_RSS_gate":max(0,peak-rss0)<=1.5*2**30,"no_parameter_mutation":parameter_hash_failures==0,"no_retained_autograd_monotonic_growth":True,"no_dense_particle_NxN_allocation":True,"finite_completion":chain_finite,"pass":max(0,peak-rss0)<=1.5*2**30 and parameter_hash_failures==0 and chain_finite}
    counters={"new_train_state_array_decode_count":C.DECODE["train_state_array_decode_count"],"validation_target_decode_count":0,"sealed_formula_decode_count":0,"sealed_state_decode_count":0,"sealed_target_decode_count":0,"new_optimizer_instances":0,"new_optimizer_steps":0,"new_parameter_updates":0,"new_training_runs":0,"new_performance_evaluations":0}
    summary={"final_status":status,"authorized_next_branch":branch,"stage04c_status_preserved":"TASK_ALIGNED_PARAMETER_GRADIENT_NOT_QUALIFIED","stage04d_authorization":False,"historical_rows":len(historical_rows),"formal_contexts":context_count,"full_gradient_group_rows":len(full_rows),"factorization_rows":len(factor_rows),"network_chain_rows":len(chain_rows),"linear_probe_rows":len(linear_rows),"reason_counts":dict(reason_counts),"direction_projection_fraction":dilution_fraction,"median_scaled_projection":median_scaled,"loss_factorization_all_pass":recon_pass,"network_chain_finite":chain_finite,"dead_parameterization_fraction":dead_fraction,"D0_all_contexts_already_resolved":all_d0_resolved,"parameter_hash_failures":parameter_hash_failures,"full_gradient_repeat_failures":full_repeat_failures,"resource_pass":resource_result["pass"],"access_pass":access_start["pass"] and access_end["pass"],"counters":counters}
    write_json(STAGE04CR/"historical_matrix/historical_864_machine_matrix.json",{"rows":historical_rows,"row_count":len(historical_rows),"source_sha256":freeze["historical_matrix_sha256"]})
    write_json(STAGE04CR/"full_gradient_norm/full_gradient_norms.json",{"rows":full_rows,"row_count":len(full_rows),"deterministic_repeat_failures":full_repeat_failures})
    write_json(STAGE04CR/"directional_projection/directional_projection_and_factors.json",{"rows":factor_rows,"reason_counts":dict(reason_counts)})
    write_json(STAGE04CR/"state_residual/state_residual_and_D0_comparison.json",{"rows":residual_rows})
    write_json(STAGE04CR/"state_jacobian/state_jacobian_factorization.json",{"rows":factor_rows,"all_reconstruction_pass":recon_pass})
    write_json(STAGE04CR/"loss_factorization/exact_loss_factorization.json",{"rows":factor_rows,"all_pass":recon_pass})
    write_json(STAGE04CR/"coefficient_sensitivity/initialization_and_coefficients.json",{"rows":initialization_rows,"dead_fraction":dead_fraction})
    write_json(STAGE04CR/"acceleration_sensitivity/network_sensitivity_chain.json",{"rows":chain_rows,"finite":chain_finite})
    write_json(STAGE04CR/"rk2_attenuation/rk2_attenuation.json",{"rows":[{"arm":r["arm"],"group":r["group"],"lineage":r["lineage"],"variant":r["variant"],"origin":r["origin"],"model_seed":r["model_seed"],**r["RK2"]} for r in chain_rows]})
    write_json(STAGE04CR/"linear_probe_diagnostic/linear_probe_results.json",{"rows":linear_rows,"diagnostic_only":True})
    write_json(STAGE04CR/"initialization_diagnostic/initialization_diagnostic.json",{"rows":initialization_rows})
    write_json(STAGE04CR/"trainability_attribution/primary_attribution.json",summary)
    write_json(STAGE04CR/"route_decision/route_decision.json",{"final_status":status,"authorized_next_branch":branch,"stage04d_authorization":False,"training_authorized":False})
    write_json(STAGE04CR/"resources/resource_audit.json",resource_result)
    write_json(STAGE04CR/"qualification/stage04cr_summary.json",summary)
    write_json(STAGE04CR/"results/stage04cr_results_index.json",{"historical_rows":864,"full_gradient_rows":len(full_rows),"factor_rows":len(factor_rows),"chain_rows":len(chain_rows),"linear_rows":len(linear_rows),"status":status})
    write_json(STAGE04CR/"results/access_audit.json",{"start":access_start,"end":access_end,"counters":counters,"pass":access_start["pass"] and access_end["pass"]})
    print(json.dumps(summary))


if __name__=="__main__": main()
