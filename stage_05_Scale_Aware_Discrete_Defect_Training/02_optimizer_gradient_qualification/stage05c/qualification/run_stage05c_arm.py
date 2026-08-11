"""Run one frozen Stage 05C arm across all seeds, lineages, probes, and descent contexts."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import gc
import hashlib
import json
import math
from pathlib import Path
import resource
import sys
import time
from typing import Any

import numpy as np
import psutil
import torch
from torch import nn
from torch.func import functional_call
from torch.nn.attention import SDPBackend,sdpa_kernel


HERE=Path(__file__).resolve(); STAGE05C=HERE.parents[1]; STAGE05=HERE.parents[3]; ROOT=HERE.parents[4]
STAGE03C=ROOT/"stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c"; sys.path[:0]=[str(STAGE03C),str(ROOT/"01_solver")]
from arm_d1.model import D1InstantaneousPairMLP
from arm_d2.model import D2CausalRecurrentPairPIO
from arm_d3.model import D3CausalTemporalTransformerPIO
from baseline_d0.state import DynamicParticleState,eos_pressure
from graph_rebuild.graph import ReciprocalGraph,build_reciprocal_graph
from pair_force_head.head import PairForceOutput
from structural_smoke.audit import audit_stage
from structure_preserving.conservative_pressure import conservative_pressure_forces
from structure_preserving.conservative_viscosity import conservative_viscosity_forces
from structure_preserving.kernels import edge_kernel_gradients,scatter_sum
from temporal_history.history import TemporalHistoryState
from tokenization.tokens import build_node_token


DT=2./20./256.; S_A=3.45632855338432798e-1; SEEDS=[20500501,20500502,20500503]; LINEAGES=["LCDF_01","LCDF_04","LCDF_05","LCDF_06","LCDF_07","LCDF_08"]
ARMS={"D1":D1InstantaneousPairMLP,"D2":D2CausalRecurrentPairPIO,"D3":D3CausalTemporalTransformerPIO}; EPS=[1e-2,3e-3,1e-3,3e-4,1e-4,3e-5]; RADII=[1e-6,3e-6,1e-5,3e-5,1e-4,3e-4]
PROCESS=psutil.Process()


def canonical(value:Any)->bytes: return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def sha_bytes(value:bytes)->str: return "sha256:"+hashlib.sha256(value).hexdigest()
def write_json(path:Path,value:Any)->None:
    def cv(x:Any)->Any:
        if isinstance(x,np.bool_): return bool(x)
        if isinstance(x,np.integer): return int(x)
        if isinstance(x,np.floating): return float(x)
        if isinstance(x,np.ndarray): return x.tolist()
        raise TypeError(type(x).__name__)
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(value,indent=2,sort_keys=True,default=cv)+"\n")
def tensor(a:np.ndarray)->torch.Tensor: return torch.from_numpy(np.ascontiguousarray(a)).to(torch.float64)
def tensor_bytes(value:torch.Tensor)->bytes:
    a=value.detach().contiguous().cpu().numpy(); return str(a.dtype).encode()+b"\0"+np.asarray(a.shape,dtype=np.int64).tobytes()+a.tobytes()
def parameter_hash(model:nn.Module)->str:
    h=hashlib.sha256()
    for name,p in model.named_parameters(): h.update(name.encode()); h.update(tensor_bytes(p))
    return "sha256:"+h.hexdigest()
def topology_id(graph:ReciprocalGraph)->str:
    h=hashlib.sha256()
    for x in (graph.row,graph.col,graph.reverse): h.update(tensor_bytes(x))
    return "sha256:"+h.hexdigest()
def force_residual(state:DynamicParticleState,out:PairForceOutput)->float:
    force=torch.zeros_like(state.velocity); force.index_add_(0,out.pair_i,out.pair_force_on_i); force.index_add_(0,out.pair_j,-out.pair_force_on_i)
    return float(torch.linalg.vector_norm(force.sum(0)).detach()/(out.pair_force_on_i.detach().abs().sum()+1e-30))


@dataclass(frozen=True)
class Case:
    record_id:str; lineage:str; variant:str; origin:int; frames:torch.Tensor; physical_times:torch.Tensor; x:torch.Tensor; velocity:torch.Tensor; density:torch.Tensor
    labels:torch.Tensor; mass:torch.Tensor; smoothing:torch.Tensor; history_tokens:torch.Tensor; source_start:torch.Tensor; source_mid:torch.Tensor; v0:torch.Tensor; target:torch.Tensor
    def state(self,index:int)->DynamicParticleState:
        rho=self.density[index]
        return DynamicParticleState(self.x[index],self.velocity[index],rho,eos_pressure(rho),self.mass,self.smoothing,self.labels,float(self.physical_times[index]),int(self.frames[index]))


def load_cases()->dict[str,Case]:
    manifest=json.loads((STAGE05C/"batch_selection/cached_formal_batch_manifest.json").read_text()); assert manifest["pass"] and manifest["case_count"]==48
    result={}
    for row in manifest["cases"]:
        with np.load(ROOT/row["path"],allow_pickle=False) as z: a={k:z[k] for k in z.files}
        result[row["record_id"]]=Case(row["record_id"],row["lineage"],row["variant"],row["origin"],torch.from_numpy(a["frames"]).to(torch.int64),tensor(a["physical_times"]),
          tensor(a["x"]),tensor(a["velocity"]),tensor(a["density"]),tensor(a["material_labels"]),tensor(a["mass"]),tensor(a["smoothing"]),tensor(a["history_tokens"]),
          tensor(a["source_start"]),tensor(a["source_midpoint"]),tensor(a["v0_accepted"]),tensor(a["a_cons"]))
    return result


def rhs(state:DynamicParticleState,graph:ReciprocalGraph,source:torch.Tensor)->tuple[torch.Tensor,torch.Tensor,torch.Tensor]:
    pf=conservative_pressure_forces(graph.neighborhood,mass=state.mass,density=state.density,pressure=state.pressure)
    vf=conservative_viscosity_forces(graph.neighborhood,mass=state.mass,density=state.density,velocity=state.velocity,physical_viscosity=.02)
    grad=edge_kernel_gradients(graph.neighborhood); dv=state.velocity[graph.row]-state.velocity[graph.col]
    drho=scatter_sum(graph.row,state.mass[graph.col]*torch.einsum("nd,nd->n",dv,grad),state.particle_count)
    return state.velocity,(pf+vf)/state.mass[:,None]+source,drho


class DefectAdapter(nn.Module):
    def __init__(self,arm:str,core:nn.Module)->None:
        super().__init__(); self.arm=arm; self.core=core; self.last_trace:dict[str,Any]={}; self.forward_count=0; self.graph_rebuild_count=0
    def history(self,case:Case)->TemporalHistoryState|None:
        if self.arm=="D1": return None
        tokens=case.history_tokens
        if self.arm=="D2":
            hidden=torch.zeros((len(case.labels),32),dtype=torch.float64); items=[]
            for token in tokens.unbind(1): hidden=self.core.recurrent(self.core.encoder(token),hidden); items.append(hidden)
            accepted_hidden=torch.stack(items,dim=1)
        else:
            # D3 evaluate/accepted_hidden depend only on accepted_tokens; stored hidden is observationally inert in this one-step API.
            accepted_hidden=torch.zeros((len(case.labels),4,32),dtype=torch.float64)
        return TemporalHistoryState(tokens,accepted_hidden,case.physical_times,case.labels,history_length=4,commit_count=0)
    def one(self,case:Case)->tuple[torch.Tensor,dict[str,Any]]:
        start=case.state(3).with_eos(); history=self.history(case); g0=build_reciprocal_graph(start); self.graph_rebuild_count+=1
        t0=build_node_token(start,g0); kw={"stage":"start"};
        if history is not None: kw["history"]=history
        p0=self.core.evaluate(t0,start,g0,**kw); x1,a1,r1=rhs(start,g0,case.source_start); a1=a1+p0.acceleration
        mid=DynamicParticleState(start.x_unwrapped+.5*DT*x1,start.velocity+.5*DT*a1,start.density+.5*DT*r1,torch.empty_like(start.pressure),
          start.mass,start.smoothing_length,start.material_labels,start.physical_time+.5*DT,start.accepted_step_index).with_eos()
        gm=build_reciprocal_graph(mid); self.graph_rebuild_count+=1; tm=build_node_token(mid,gm); kw={"stage":"midpoint"};
        if history is not None: kw["history"]=history
        pm=self.core.evaluate(tm,mid,gm,**kw); x2,a2,r2=rhs(mid,gm,case.source_mid); a2=a2+pm.acceleration
        acc=DynamicParticleState(start.x_unwrapped+DT*x2,start.velocity+DT*a2,start.density+DT*r2,torch.empty_like(start.pressure),
          start.mass,start.smoothing_length,start.material_labels,start.physical_time+DT,start.accepted_step_index+1).with_eos()
        ga=build_reciprocal_graph(acc); self.graph_rebuild_count+=1; commit=0
        if history is not None:
            ta=build_node_token(acc,ga); ha=self.core.accepted_hidden(ta,history=history); history=history.commit(ta,ha,acc.physical_time); commit=history.commit_count
        aeff=(acc.velocity-case.v0)/DT; loss=((aeff-case.target)/S_A).square().mean()
        trace={"record_id":case.record_id,"topology":[topology_id(g) for g in (g0,gm,ga)],"graph_hashes":[g.graph_hash for g in (g0,gm,ga)],
          "edge_counts":[g.edge_count for g in (g0,gm,ga)],"density_min":float(torch.stack((start.density.min(),mid.density.min(),acc.density.min())).detach().min()),
          "finite":bool(torch.isfinite(loss.detach()) and torch.isfinite(p0.acceleration.detach()).all() and torch.isfinite(pm.acceleration.detach()).all()
                        and torch.isfinite(p0.alpha.detach()).all() and torch.isfinite(pm.beta.detach()).all()),
          "force_residual_max":max(force_residual(start,p0),force_residual(mid,pm)),"history_commit_count":commit,"midpoint_commit_count":0}
        return loss,trace
    def forward(self,cases:list[Case])->torch.Tensor:
        self.forward_count+=1; losses=[]; traces=[]
        for case in cases:
            loss,trace=self.one(case); losses.append(loss); traces.append(trace)
        self.last_trace={"cases":traces,"topology":[x for t in traces for x in t["topology"]],"graph_hashes":[x for t in traces for x in t["graph_hashes"]],
          "safe":all(t["finite"] and t["density_min"]>0 and t["force_residual_max"]<=1e-10 and t["midpoint_commit_count"]==0 and
                     t["history_commit_count"]==(0 if self.arm=="D1" else 1) for t in traces)}
        return torch.stack(losses).mean()
    def start_audit(self,case:Case)->tuple[DynamicParticleState,TemporalHistoryState|None,PairForceOutput,ReciprocalGraph,torch.Tensor]:
        state=case.state(3).with_eos(); history=self.history(case); graph=build_reciprocal_graph(state); token=build_node_token(state,graph); kw={"stage":"start"}
        if history is not None: kw["history"]=history
        return state,history,self.core.evaluate(token,state,graph,**kw),graph,token


def batch_for(lineage:str,cases:dict[str,Case],batches:dict[str,Any])->list[Case]:
    rows=[]
    for item in batches["selection"]:
        if item["lineage"]==lineage:
            rows.extend(cases[f"{lineage}_{item['variant']}_N8_O{o:02d}"] for o in item["origins"])
    assert len(rows)==8; return rows
def global_batch(cases:dict[str,Case],batches:dict[str,Any])->list[Case]: return [c for f in LINEAGES for c in batch_for(f,cases,batches)]


def group_vector(values:tuple[torch.Tensor,...],names:list[str],group:dict[str,Any])->torch.Tensor:
    index={n.removeprefix("core."):i for i,n in enumerate(names)}; parts=[]
    for e in group["entries"]:
        v=values[index[e["tensor_path"]]]
        if "slice_dim0" in e: v=v[e["slice_dim0"][0]:e["slice_dim0"][1]]
        parts.append(v.reshape(-1))
    return torch.cat(parts)
def group_direction(params:tuple[torch.Tensor,...],names:list[str],group:dict[str,Any],indices:list[int],weights:list[float])->tuple[torch.Tensor,...]:
    directions=[torch.zeros_like(p) for p in params]; pindex={n.removeprefix("core."):i for i,n in enumerate(names)}; starts=[]; offset=0
    for e in group["entries"]: starts.append((offset,offset+e["element_count"],e)); offset+=e["element_count"]
    for gi,w in zip(indices,weights):
        for lo,hi,e in starts:
            if lo<=gi<hi:
                pi=pindex[e["tensor_path"]]; local=gi-lo
                if "slice_dim0" in e:
                    a,b=e["slice_dim0"]; view=directions[pi][a:b].reshape(-1)
                else: view=directions[pi].reshape(-1)
                view[local]=w; break
    return tuple(directions)


def decade_histogram(x:torch.Tensor)->dict[str,int]:
    v=x.detach().abs().cpu().numpy(); v=v[v>0]
    if not len(v): return {}
    dec=np.floor(np.log10(v)).astype(int); return {str(k):int(np.sum(dec==k)) for k in sorted(set(dec.tolist()))}
def group_stats(g1:tuple[torch.Tensor,...],g2:tuple[torch.Tensor,...],params:tuple[torch.Tensor,...],names:list[str],group:dict[str,Any])->dict[str,Any]:
    a=group_vector(g1,names,group); b=group_vector(g2,names,group); diff=a-b; rms=float(torch.sqrt(a.square().mean())); noise=max(float(torch.sqrt(diff.square().mean())),128*torch.finfo(torch.float64).eps*max(1.,rms))
    return {"group":group["group"],"element_count":a.numel(),"L2":float(torch.linalg.vector_norm(a)),"RMS":rms,"Linf":float(a.abs().max()),
      "finite_count":int(torch.isfinite(a).sum()),"exact_nonzero_count":int((a!=0).sum()),"positive_count":int((a>0).sum()),"negative_count":int((a<0).sum()),
      "decade_histogram":decade_histogram(a),"repeat_difference_RMS":float(torch.sqrt(diff.square().mean())),"u_g":noise,"activity_ratio":rms/noise,
      "active":bool(torch.isfinite(a).all() and rms>=100*noise)}


def evaluate_values(adapter:DefectAdapter,cases:list[Case],values:tuple[torch.Tensor,...],names:list[str],rng_seed:int)->tuple[float,dict[str,Any]]:
    torch.manual_seed(rng_seed)
    with sdpa_kernel(SDPBackend.MATH): loss=functional_call(adapter,dict(zip(names,values)),(cases,),strict=True)
    return float(loss.detach()),json.loads(json.dumps(adapter.last_trace))
def full_gradient(adapter:DefectAdapter,cases:list[Case])->tuple[list[float],list[tuple[torch.Tensor,...]],list[dict[str,Any]]]:
    params=tuple(p for _,p in adapter.named_parameters()); losses=[]; grads=[]; traces=[]
    for _ in range(2):
        with sdpa_kernel(SDPBackend.MATH): loss=adapter(cases)
        grad=torch.autograd.grad(loss,params,allow_unused=False); losses.append(float(loss.detach())); grads.append(tuple(g.detach().clone() for g in grad)); traces.append(json.loads(json.dumps(adapter.last_trace)))
    return losses,grads,traces


def reverse_jvp(adapter:DefectAdapter,cases:list[Case],params:tuple[torch.Tensor,...],names:list[str],direction:tuple[torch.Tensor,...],grad:tuple[torch.Tensor,...])->dict[str,Any]:
    reverse=float(sum((g*d).sum() for g,d in zip(grad,direction)))
    def fn(*values:torch.Tensor)->torch.Tensor:
        with sdpa_kernel(SDPBackend.MATH): return functional_call(adapter,dict(zip(names,values)),(cases,),strict=True)
    with sdpa_kernel(SDPBackend.MATH): _,tangent=torch.autograd.functional.jvp(fn,params,direction,create_graph=False,strict=True)
    jvp=float(tangent.detach()); ae=abs(reverse-jvp); near=abs(reverse)<1e-12 and abs(jvp)<1e-12; rel=ae/max(abs(reverse),abs(jvp),1e-30)
    passed=ae<=(1e-12 if near else 1e-10) or (not near and rel<=1e-7)
    return {"reverse":reverse,"jvp":jvp,"abs_difference":ae,"relative_difference":rel,"near_zero":near,"pass":passed}


def fd_probe(adapter:DefectAdapter,cases:list[Case],params:tuple[torch.Tensor,...],names:list[str],direction:tuple[torch.Tensor,...],scale:float,ad:float,near:bool,
             base_topology:list[str],seed:int)->dict[str,Any]:
    rows=[]
    for ei,epsilon in enumerate(EPS):
        actual=epsilon*scale; plus=[]; minus=[]; pt=[]; mt=[]; pg=[]; mg=[]; safe=[]
        for repeat in range(2):
            pv=tuple(p+actual*d for p,d in zip(params,direction)); mv=tuple(p-actual*d for p,d in zip(params,direction))
            lp,tp=evaluate_values(adapter,cases,pv,names,seed+ei*100+repeat*2); lm,tm=evaluate_values(adapter,cases,mv,names,seed+ei*100+repeat*2+1)
            plus.append(lp); minus.append(lm); pt.append(tp["topology"]); mt.append(tm["topology"]); pg.append(tp["graph_hashes"]); mg.append(tm["graph_hashes"]); safe.append(tp["safe"] and tm["safe"])
        fds=[(p-m)/(2*actual) for p,m in zip(plus,minus)]; fd=float(np.mean(fds)); ae=abs(fd-ad); rel=ae/max(abs(fd),abs(ad),1e-30)
        smooth=all(x==base_topology for x in pt+mt); deterministic=plus[0]==plus[1] and minus[0]==minus[1] and pt[0]==pt[1] and mt[0]==mt[1] and pg[0]==pg[1] and mg[0]==mg[1]
        rows.append({"epsilon":epsilon,"epsilon_actual":actual,"plus_losses":plus,"minus_losses":minus,"FD_repeats":fds,"FD":fd,"FD_AD_abs":ae,"FD_AD_rel":rel,
          "FD_AD_pass":ae<=1e-8 or rel<=1e-4,"topology_unchanged":smooth,"deterministic":deterministic,"safe":all(safe),
          "plus_graph_hash_sequences":pg,"minus_graph_hash_sequences":mg})
    stable_pairs=[]
    for i in range(len(rows)-1):
        change=abs(rows[i]["FD"]-rows[i+1]["FD"])/max(abs(rows[i]["FD"]),abs(rows[i+1]["FD"]),1e-30)
        base=all(rows[j]["topology_unchanged"] and rows[j]["deterministic"] and rows[j]["safe"] for j in (i,i+1))
        ok=(base and ((near and abs(rows[i]["FD"])<=1e-8 and abs(rows[i+1]["FD"])<=1e-8) or
                      (not near and rows[i]["FD_AD_pass"] and rows[i+1]["FD_AD_pass"] and change<=1e-3)))
        stable_pairs.append({"indices":[i,i+1],"relative_change":change,"pass":ok})
    smooth_count=sum(r["topology_unchanged"] and r["deterministic"] and r["safe"] for r in rows)
    return {"epsilon_rows":rows,"stable_pairs":stable_pairs,"smooth_epsilon_count":smooth_count,"stable":smooth_count>=3 and any(x["pass"] for x in stable_pairs)}


def local_descent(adapter:DefectAdapter,cases:list[Case],params:tuple[torch.Tensor,...],names:list[str],grad:tuple[torch.Tensor,...],base_losses:list[float],base_trace:dict[str,Any],seed:int)->dict[str,Any]:
    gnorm=float(torch.sqrt(sum(g.square().sum() for g in grad))); pnorm=float(torch.sqrt(sum(p.detach().square().sum() for p in params))); count=sum(p.numel() for p in params)
    tref=max(pnorm,math.sqrt(count)*1e-3); direction=tuple(-g/max(gnorm,1e-30) for g in grad); base=float(np.mean(base_losses)); uL=max(abs(base_losses[0]-base_losses[1]),128*np.finfo(float).eps*max(1.,abs(base)))
    rows=[]; before=parameter_hash(adapter.core)
    for i,radius in enumerate(RADII):
        step=radius*tref; values=tuple(p+step*d for p,d in zip(params,direction)); repeats=[]; traces=[]
        for rep in range(2):
            loss,trace=evaluate_values(adapter,cases,values,names,seed+i*10+rep); repeats.append(loss); traces.append(trace)
        obs=repeats[0]-base; pred=-step*gnorm; ratio=obs/pred if pred else math.inf
        safe=all(t["safe"] for t in traces); topology=all(t["topology"]==base_trace["topology"] for t in traces); deterministic=repeats[0]==repeats[1] and traces[0]["graph_hashes"]==traces[1]["graph_hashes"]
        restored=parameter_hash(adapter.core)==before
        passed=obs < -100*uL and pred<0 and .20<=ratio<=1.80 and np.isfinite(repeats).all() and safe and topology and deterministic and restored
        rows.append({"radius":radius,"step_norm":step,"loss_repeats":repeats,"Delta_obs":obs,"Delta_pred":pred,"ratio":ratio,"u_L":uL,"safe":safe,
          "topology_unchanged":topology,"deterministic":deterministic,"parameter_bitwise_restored":restored,"graph_hash_sequences":[t["graph_hashes"] for t in traces],"pass":passed})
    adjacent=[rows[i]["pass"] and rows[i+1]["pass"] for i in range(len(rows)-1)]
    return {"base_loss_repeats":base_losses,"gradient_L2":gnorm,"theta_norm_ref":tref,"radii":rows,"adjacent_pass_pairs":adjacent,"window":any(adjacent),
            "parameter_hash_before":before,"parameter_hash_after":parameter_hash(adapter.core),"optimizer_instances":0,"writeback":False}


def run_probe(adapter:DefectAdapter,cases:list[Case],params:tuple[torch.Tensor,...],names:list[str],grad:tuple[torch.Tensor,...],group:dict[str,Any],probe:dict[str,Any],
              kind:str,base_trace:dict[str,Any],seed:int)->dict[str,Any]:
    if kind=="coordinate": indices=[probe["group_flat_index"]]; weights=[1.]; scale=max(1.,abs(float(group_vector(params,names,group)[indices[0]].detach())))
    else:
        indices=probe["indices"]; weights=(np.asarray(probe["rademacher_signs"],dtype=float)/math.sqrt(len(indices))).tolist(); gv=group_vector(params,names,group)
        scale=max(1.,float(torch.sqrt(gv[indices].square().mean())))
    direction=group_direction(params,names,group,indices,weights); rj=reverse_jvp(adapter,cases,params,names,direction,grad)
    fd=fd_probe(adapter,cases,params,names,direction,scale,rj["reverse"],rj["near_zero"],base_trace["topology"],seed)
    return {"kind":kind,"selection":probe,"perturbation_scale":scale,"reverse_jvp":rj,"finite_difference":fd,
      "stable_nonzero":fd["stable"] and not rj["near_zero"],"pass":rj["pass"] and fd["stable"]}


def run_arm(arm:str,smoke:bool=False)->None:
    torch.set_num_threads(1); cases=load_cases(); batches=json.loads((STAGE05C/"batch_selection/preregistered_batches.json").read_text())
    group_all=json.loads((STAGE05C/"parameter_groups/preregistered_parameter_groups.json").read_text())["groups"][arm]
    probes=json.loads((STAGE05C/"parameter_groups/preregistered_probe_plan.json").read_text())["contexts"]
    identities=json.loads((STAGE05C/"model_instantiation/preregistered_model_identities.json").read_text())["models"]
    outdir=STAGE05C/"results"/arm.lower(); outdir.mkdir(parents=True,exist_ok=True); start=time.perf_counter(); rss0=PROCESS.memory_info().rss; peak=rss0; context_summaries=[]
    forward_count=backward_count=jvp_count=fd_path_count=local_forward_count=restoration_checks=0; retained=[]
    active_seeds=SEEDS[:1] if smoke else SEEDS; active_lineages=LINEAGES[:1] if smoke else LINEAGES
    for seed in active_seeds:
        torch.manual_seed(seed); model=ARMS[arm]().to(dtype=torch.float64,device="cpu"); model.eval(); expected=next(x for x in identities if x["arm"]==arm and x["seed"]==seed)
        assert parameter_hash(model)==expected["complete_parameter_sha256"]
        adapter=DefectAdapter(arm,model); params=tuple(p for _,p in adapter.named_parameters()); names=[n for n,_ in adapter.named_parameters()]
        for lineage in active_lineages:
            path=outdir/f"{arm}_{seed}_{lineage}.json"
            selected=batch_for(lineage,cases,batches); before=parameter_hash(model); losses,grads,traces=full_gradient(adapter,selected); backward_count+=2
            stats=[group_stats(grads[0],grads[1],params,names,g) for g in group_all]
            local=local_descent(adapter,selected,params,names,grads[0],losses,traces[0],seed+LINEAGES.index(lineage)*10000); local_forward_count+=12; restoration_checks+=6
            # The reference and every repeated/transformed audit evaluation must
            # use the same explicitly locked SDPA backend.  In particular, D3's
            # reference cannot be produced before entering the MATH context.
            with sdpa_kernel(SDPBackend.MATH):
                state,history,output,graph,token=adapter.start_audit(selected[0])
                structure=audit_stage(arm=arm,model=model,state=state,history=history,stage="start",reference_output=output,reference_graph=graph,reference_token=token)
            probe_rows=[]
            for group in group_all[:1] if smoke else group_all:
                plan=next(p for p in probes if p["arm"]==arm and p["group"]==group["group"] and p["lineage"]==lineage and p["seed"]==seed)
                directions=[("coordinate",x) for x in plan["coordinates"]]+[("block",x) for x in plan["blocks"]]
                for pi,(kind,probe) in enumerate(directions[:1] if smoke else directions):
                    row=run_probe(adapter,selected,params,names,grads[0],group,probe,kind,traces[0],seed+pi*100000+LINEAGES.index(lineage)*1000)
                    row.update({"arm":arm,"seed":seed,"lineage":lineage,"group":group["group"]}); probe_rows.append(row); jvp_count+=1; fd_path_count+=24; restoration_checks+=12
            group_context=[]
            for stat in stats:
                rows=[r for r in probe_rows if r["group"]==stat["group"]]; passed=stat["active"] and len(rows)==5 and all(r["pass"] for r in rows) and any(r["stable_nonzero"] for r in rows)
                group_context.append({"group":stat["group"],"full_gradient":stat,"probe_count":len(rows),"pass":passed})
            result={"arm":arm,"seed":seed,"lineage":lineage,"batch_record_ids":[c.record_id for c in selected],"loss_repeats":losses,"loss_repeat_exact":losses[0]==losses[1],
              "full_gradient_groups":stats,"probes":probe_rows,"group_contexts":group_context,"local_descent":local,"structure":structure,
              "parameter_hash_before":before,"parameter_hash_after":parameter_hash(model),"parameter_unchanged":before==parameter_hash(model),
              "pass":all(x["pass"] for x in group_context) and local["window"] and structure["pass"] and before==parameter_hash(model)}
            if not smoke: write_json(path,result)
            context_summaries.append({"seed":seed,"lineage":lineage,"pass":result["pass"],"local":local["window"],"structure":structure["pass"],
                "groups":{x["group"]:x["pass"] for x in group_context}})
            peak=max(peak,PROCESS.memory_info().rss); del losses,grads,traces,probe_rows; gc.collect(); retained.append({"seed":seed,"lineage":lineage,"rss":PROCESS.memory_info().rss})
            print(json.dumps({"arm":arm,"seed":seed,"lineage":lineage,"pass":result["pass"],"elapsed":time.perf_counter()-start}),flush=True)
        if not smoke:
            selected=global_batch(cases,batches); losses,grads,traces=full_gradient(adapter,selected); backward_count+=2
            local=local_descent(adapter,selected,params,names,grads[0],losses,traces[0],seed+900000); local_forward_count+=12; restoration_checks+=6
            glob={"arm":arm,"seed":seed,"batch_size":48,"loss_repeats":losses,"gradient_L2":float(torch.sqrt(sum(g.square().sum() for g in grads[0]))),
                  "local_descent":local,"parameter_unchanged":parameter_hash(model)==expected["complete_parameter_sha256"],"pass":local["window"] and parameter_hash(model)==expected["complete_parameter_sha256"]}
            write_json(outdir/f"{arm}_{seed}_GLOBAL.json",glob); context_summaries.append({"seed":seed,"lineage":"GLOBAL","pass":glob["pass"],"local":local["window"]})
        forward_count+=adapter.forward_count; peak=max(peak,PROCESS.memory_info().rss); del adapter,model,params; gc.collect()
    if smoke:
        print(json.dumps({"smoke":True,"contexts":context_summaries,"forward_count":forward_count})); return
    # Arm aggregation uses frozen 2/3 seed and 6/6 lineage rules.
    context_files=[json.loads(p.read_text()) for p in outdir.glob(f"{arm}_*_LCDF_*.json")]
    group_lineage={}
    for group in [g["group"] for g in group_all]:
        group_lineage[group]={}
        for lineage in LINEAGES:
            passes=[]
            for row in context_files:
                if row["lineage"]==lineage: passes.append(next(x["pass"] for x in row["group_contexts"] if x["group"]==group))
            group_lineage[group][lineage]={"seed_pass_count":sum(passes),"pass":sum(passes)>=2}
    group_pass={g:all(v["pass"] for v in rows.values()) for g,rows in group_lineage.items()}
    local_lineage={lineage:{"seed_pass_count":sum(r["local_descent"]["window"] for r in context_files if r["lineage"]==lineage)} for lineage in LINEAGES}
    for v in local_lineage.values(): v["pass"]=v["seed_pass_count"]>=2
    globals_=[json.loads(p.read_text()) for p in outdir.glob(f"{arm}_*_GLOBAL.json")]; global_pass=len(globals_)==3 and all(r["pass"] for r in globals_)
    summary={"arm":arm,"group_lineage":group_lineage,"group_pass":group_pass,"local_descent_lineage":local_lineage,"global_seed_pass_count":sum(r["pass"] for r in globals_),
      "global_pass":global_pass,"reverse_jvp_probe_count":sum(len(r["probes"]) for r in context_files),"reverse_jvp_pass_count":sum(p["reverse_jvp"]["pass"] for r in context_files for p in r["probes"]),
      "FD_probe_pass_count":sum(p["finite_difference"]["stable"] for r in context_files for p in r["probes"]),"context_count":len(context_files),
      "full_gradient_backward_count":backward_count,"JVP_count":jvp_count,"FD_path_count":fd_path_count,"local_descent_forward_count":local_forward_count,
      "parameter_restoration_checks":restoration_checks,"graph_rebuild_count":sum(json.loads(p.read_text()).get("graph_rebuild_count",0) for p in []),
      "wall_time_seconds":time.perf_counter()-start,"rss_start_bytes":rss0,"peak_rss_bytes":peak,"peak_rss_delta_bytes":peak-rss0,"retention_samples":retained,
      "optimizer_instances":0,"optimizer_steps":0,"persistent_updates":0,"training_runs":0,"neural_rollouts":0,"performance_evaluations":0,
      "pass":all(group_pass.values()) and all(v["pass"] for v in local_lineage.values()) and global_pass and all(r["structure"]["pass"] for r in context_files)}
    write_json(STAGE05C/f"qualification/{arm.lower()}_qualification_summary.json",summary); print(json.dumps({"arm":arm,"pass":summary["pass"],"wall":summary["wall_time_seconds"]}),flush=True)


if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--arm",choices=sorted(ARMS),required=True); p.add_argument("--smoke",action="store_true"); a=p.parse_args(); run_arm(a.arm,a.smoke)
