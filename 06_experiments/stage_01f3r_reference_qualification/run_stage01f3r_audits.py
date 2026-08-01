"""Cutoff, dense equivalence, and saved-topology event audits."""

from __future__ import annotations
import csv,hashlib,json,math
from pathlib import Path
import subprocess,sys
from typing import Any
import numpy as np,torch,yaml

ROOT=Path(__file__).resolve().parents[2];SOLVER=ROOT/"01_solver";sys.path.insert(0,str(SOLVER));STAGE=ROOT/"06_experiments/stage_01f3r_reference_qualification";CONFIG=STAGE/"configs/preregistered_stage01f3r.yml"
from dynamic_solver.acceleration import DynamicPhysicalParameters,evaluate_internal_acceleration,force_structure_audit
from dynamic_solver.sourced_acceleration import initialize_mms_state
from dynamic_solver.state import DynamicSPHState
from manufactured_solutions.cutoff_smoothness import cutoff_probe
from manufactured_solutions.dense_all_pairs_rhs import dense_pair_acceleration_contributions,evaluate_dense_all_pairs
from manufactured_solutions.dynamic_source_adapter import evaluate_mms_source
from manufactured_solutions.sparse_dense_equivalence import difference_metrics,equivalence_gate
from manufactured_solutions.topology_event_audit import topology_events

def sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()
def git_hash()->str:return subprocess.check_output(("git","rev-parse","HEAD"),cwd=ROOT,text=True).strip()
def write_json(path:Path,value:dict[str,Any])->None:
    if path.exists():raise RuntimeError(f"refusing to overwrite {path}")
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2,sort_keys=True)+"\n")
def write_csv(path:Path,rows:list[dict[str,Any]])->None:
    if path.exists():raise RuntimeError(f"refusing to overwrite {path}")
    with path.open("x",newline="",encoding="utf-8") as stream:writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator="\n");writer.writeheader();writer.writerows(rows)
def sparse_dense(solution:str,positions:torch.Tensor,velocities:torch.Tensor,masses:torch.Tensor,supports:torch.Tensor,time:float,label:str)->dict[str,Any]:
    state=DynamicSPHState(positions=torch.remainder(positions+1.,2.)-1.,velocities=velocities,masses=masses,densities=torch.ones_like(masses),pressures=torch.zeros_like(masses),supports=supports,domain_min=torch.full((2,),-1.,dtype=torch.float64),domain_max=torch.full((2,),1.,dtype=torch.float64),time=time)
    sparse=evaluate_internal_acceleration(state,DynamicPhysicalParameters());source=evaluate_mms_source(solution,state.positions,time);dense=evaluate_dense_all_pairs(solution,state.positions,velocities,masses,supports,time)
    values={"density":(sparse.densities,dense.density),"pressure":(sparse.pressures,dense.pressure),"pressure_acceleration":(sparse.pressure_force/masses[:,None],dense.pressure_acceleration),"viscosity_acceleration":(sparse.viscosity_force/masses[:,None],dense.viscosity_acceleration),"source":(source,dense.source_acceleration),"total_acceleration":(sparse.acceleration+source,dense.total_acceleration),"dx_dt":(velocities,velocities),"dv_dt":(sparse.acceleration+source,dense.total_acceleration)}
    result={"label":label,"solution":solution,"time":time}
    for name,(left,right) in values.items():
        metrics=difference_metrics(left,right);result[f"{name}_absolute_linf"]=metrics["absolute_linf"];result[f"{name}_relative_linf"]=metrics["relative_linf"]
    result["finite"]=all(math.isfinite(float(v)) for v in result.values() if isinstance(v,float));return result
def cutoff()->bool:
    rows=cutoff_probe();write_csv(STAGE/"results/cutoff_smoothness.csv",rows);left=rows[3];at=rows[4];right=rows[5]
    checks={"kernel_value_continuous":left["W"]<=1e-50 and at["W"]==right["W"]==0.,"kernel_first_derivative_continuous":left["dW_dr"]<=1e-38 and at["dW_dr"]==right["dW_dr"]==0.,"pressure_pair_continuous":left["pressure_pair_l2"]<=1e-30 and at["pressure_pair_l2"]==0.,"viscosity_pair_continuous":left["viscosity_pair_l2"]<=1e-30 and at["viscosity_pair_l2"]==0.,"pair_acceleration_negligible":left["acceleration_contribution_l2"]<=1e-30}
    payload={"schema_version":"sph-pio-poc.stage01f3r.cutoff.v1","checks":checks,"left_limit_probe_q":left["q"],"maximum_near_cutoff_acceleration_contribution":max(row["acceleration_contribution_l2"] for row in rows[1:5]),"inclusion_convention":"dense excludes r>=H; sparse may retain tolerance-shell edges, whose W, gradient and pair terms evaluate to zero at q>=1","status":"PASS" if all(checks.values()) else "FAIL"};write_json(STAGE/"results/cutoff_smoothness_summary.json",payload);return payload["status"]=="PASS"
def equivalence()->bool:
    ratio=(4+17**.5)/2;rows=[]
    for solution in ("MMS_A","MMS_B"):
        initial=initialize_mms_state(solution,16,support_ratio=ratio)
        rows.append(sparse_dense(solution,initial.positions,initial.velocities,initial.masses,initial.supports,0.,f"{solution}_initial"))
        if solution=="MMS_B":
            old=np.load(ROOT/"06_experiments/stage_01f3_mms_convergence/references/semidiscrete_mms_b_n16_dop853.npz");states=old["baseline"];times=old["times"];count=len(initial.positions)
            expanded=[]
            for index in range(len(times)-1):expanded.extend([(float(times[index]),states[index]),(float(.5*(times[index]+times[index+1])),.5*(states[index]+states[index+1]))])
            expanded.append((float(times[-1]),states[-1]))
            for index,(time_value,state_value) in enumerate(expanded):
                p=torch.from_numpy(state_value[:2*count].reshape(count,2).copy());v=torch.from_numpy(state_value[2*count:].reshape(count,2).copy());rows.append(sparse_dense(solution,p,v,initial.masses,initial.supports,time_value,f"baseline_replay_{index:02d}"))
            generator=torch.Generator().manual_seed(20260802)
            for index in range(3):
                p=initial.positions+1e-4*(2*torch.rand(initial.positions.shape,dtype=torch.float64,generator=generator)-1);v=initial.velocities+1e-4*(2*torch.rand(initial.velocities.shape,dtype=torch.float64,generator=generator)-1);rows.append(sparse_dense(solution,p,v,initial.masses,initial.supports,0.,f"random_perturbation_{index}"))
            positions=states[:,:2*count].reshape(len(times),count,2);velocities=states[:,2*count:].reshape(len(times),count,2)
            for event_index,event in enumerate(topology_events(times,positions,float(initial.supports[0]))):
                k=int(np.searchsorted(times,event["estimated_event_time"])-1);k=max(0,min(k,len(times)-2));fraction=float((event["estimated_event_time"]-times[k])/(times[k+1]-times[k]))
                for side,local in (("before",max(0.,fraction-1e-8)),("after",min(1.,fraction+1e-8))):
                    p=torch.from_numpy(((1-local)*positions[k]+local*positions[k+1]).copy());v=torch.from_numpy(((1-local)*velocities[k]+local*velocities[k+1]).copy());t=float((1-local)*times[k]+local*times[k+1]);rows.append(sparse_dense(solution,p,v,initial.masses,initial.supports,t,f"edge_switch_{event_index:02d}_{side}"))
    support=.4;mass=torch.full((4,),.1,dtype=torch.float64);velocity=torch.tensor([[.1,.2],[-.3,.4],[.2,-.1],[-.2,-.3]],dtype=torch.float64);supports=torch.full((4,),support,dtype=torch.float64)
    for epsilon in (-1e-10,0.,1e-10):
        positions=torch.tensor([[-.2,0.],[-.2+support*(1+epsilon),0.],[.65,.65],[-.65,-.65]],dtype=torch.float64);rows.append(sparse_dense("MMS_B",positions,velocity,mass,supports,0.,f"cutoff_{epsilon:+.0e}"))
    write_csv(STAGE/"results/sparse_dense_equivalence.csv",rows)
    maxima={f"{name}_{kind}":max(row[f"{name}_{kind}"] for row in rows) for name in ("density","pressure","pressure_acceleration","viscosity_acceleration","source","total_acceleration","dx_dt","dv_dt") for kind in ("absolute_linf","relative_linf")}
    checks={"density":maxima["density_relative_linf"]<=1e-13,"pressure":maxima["pressure_relative_linf"]<=1e-13,"acceleration_relative":maxima["total_acceleration_relative_linf"]<=1e-11,"acceleration_absolute":maxima["total_acceleration_absolute_linf"]<=1e-12,"finite":all(row["finite"] for row in rows),"baseline_state_count":sum(row["label"].startswith("baseline_replay") for row in rows)>=20,"edge_switch_states_present":sum(row["label"].startswith("edge_switch") for row in rows)>=2}
    payload={"schema_version":"sph-pio-poc.stage01f3r.sparse-dense.v1","case_count":len(rows),"maxima":maxima,"checks":checks,"cutoff_inclusion_convention":"r=H sparse tolerance edge may exist but aggregated RHS is unchanged because kernel and pair terms are zero","status":"PASS" if all(checks.values()) else "FAIL"};write_json(STAGE/"results/sparse_dense_equivalence_summary.json",payload);return payload["status"]=="PASS"
def events()->bool:
    ratio=(4+17**.5)/2;initial=initialize_mms_state("MMS_B",16,support_ratio=ratio);old=np.load(ROOT/"06_experiments/stage_01f3_mms_convergence/references/semidiscrete_mms_b_n16_dop853.npz");states=old["baseline"];times=old["times"];count=len(initial.positions);positions=states[:,:2*count].reshape(len(times),count,2);velocities=states[:,2*count:].reshape(len(times),count,2);found=topology_events(times,positions,float(initial.supports[0]));rows=[];max_structural=0
    for event in found:
        k=int(np.searchsorted(times,event["estimated_event_time"])-1);k=max(0,min(k,len(times)-2));fraction=(event["estimated_event_time"]-times[k])/(times[k+1]-times[k]);epsilon=1e-8
        contributions=[];accelerations=[];local_ratios=[];directed_presence=[]
        for local in (max(0.,fraction-epsilon),min(1.,fraction+epsilon)):
            p=torch.from_numpy(((1-local)*positions[k]+local*positions[k+1]).copy());v=torch.from_numpy(((1-local)*velocities[k]+local*velocities[k+1]).copy());t=float((1-local)*times[k]+local*times[k+1]);wrapped=torch.remainder(p+1.,2.)-1.;dense=evaluate_dense_all_pairs("MMS_B",wrapped,v,initial.masses,initial.supports,t);pair=dense_pair_acceleration_contributions(dense,int(event["particle_i"]),int(event["particle_j"]),initial.masses,v);contributions.append(pair);accelerations.append(dense.total_acceleration);local_ratios.append(float(dense.distance[int(event["particle_i"]),int(event["particle_j"])]/dense.support[int(event["particle_i"]),int(event["particle_j"])]))
            state=DynamicSPHState(positions=wrapped,velocities=v,masses=initial.masses,densities=torch.ones_like(initial.masses),pressures=torch.zeros_like(initial.masses),supports=initial.supports,domain_min=initial.domain_min,domain_max=initial.domain_max,time=t);sparse=evaluate_internal_acceleration(state,DynamicPhysicalParameters());i=int(event["particle_i"]);j=int(event["particle_j"]);edges=set(zip(sparse.neighborhood.row.tolist(),sparse.neighborhood.col.tolist()));directed_presence.append(((i,j) in edges,(j,i) in edges))
        reciprocal=all(forward==reverse for forward,reverse in directed_presence)
        row={**event,"evaluation_ratio_before":local_ratios[0],"evaluation_ratio_after":local_ratios[1],"directed_edge_before":directed_presence[0][0],"reverse_edge_before":directed_presence[0][1],"directed_edge_after":directed_presence[1][0],"reverse_edge_after":directed_presence[1][1],"reciprocal":reciprocal,"pressure_before_l2":float(torch.linalg.vector_norm(contributions[0]["pressure"])),"pressure_after_l2":float(torch.linalg.vector_norm(contributions[1]["pressure"])),"viscosity_before_l2":float(torch.linalg.vector_norm(contributions[0]["viscosity"])),"viscosity_after_l2":float(torch.linalg.vector_norm(contributions[1]["viscosity"])),"pair_total_max_l2":max(float(torch.linalg.vector_norm(value["total"])) for value in contributions),"aggregated_rhs_jump_linf":float((accelerations[1]-accelerations[0]).abs().max())};rows.append(row)
    for time_value,state_value in zip(times,states):
        p=torch.from_numpy(state_value[:2*count].reshape(count,2).copy());v=torch.from_numpy(state_value[2*count:].reshape(count,2).copy());state=DynamicSPHState(positions=torch.remainder(p+1.,2.)-1.,velocities=v,masses=initial.masses,densities=torch.ones_like(initial.masses),pressures=torch.zeros_like(initial.masses),supports=initial.supports,domain_min=initial.domain_min,domain_max=initial.domain_max,time=float(time_value));audit=force_structure_audit(state,evaluate_internal_acceleration(state,DynamicPhysicalParameters()),DynamicPhysicalParameters());max_structural=max(max_structural,sum(int(audit[key]) for key in ("neighbor_duplicate_edge_count","neighbor_missing_self_edge_count","neighbor_nonreciprocal_nonself_edge_count","neighbor_out_of_bounds_edge_count","neighbor_omitted_strict_support_edge_count","neighbor_unexpected_edge_count")))
    write_csv(STAGE/"results/topology_events.csv",rows);checks={"events_present":len(rows)>0,"all_bracket_cutoff":all((row["ratio_before"]-1)*(row["ratio_after"]-1)<=0 for row in rows),"evaluation_points_at_cutoff":all(max(abs(row["evaluation_ratio_before"]-1),abs(row["evaluation_ratio_after"]-1))<=1e-7 for row in rows),"all_reciprocal":all(row["reciprocal"] for row in rows),"structural_defects_zero":max_structural==0,"pair_contribution_negligible":max(row["pair_total_max_l2"] for row in rows)<=1e-12,"aggregated_rhs_no_finite_jump":max(row["aggregated_rhs_jump_linf"] for row in rows)<=1e-6}
    payload={"schema_version":"sph-pio-poc.stage01f3r.topology-events.v1","event_count":len(rows),"maximum_pair_contribution":max(row["pair_total_max_l2"] for row in rows),"maximum_aggregated_rhs_jump":max(row["aggregated_rhs_jump_linf"] for row in rows),"maximum_structural_defects":max_structural,"checks":checks,"status":"PASS" if all(checks.values()) else "FAIL"};write_json(STAGE/"results/topology_event_summary.json",payload);return payload["status"]=="PASS"
def freeze()->bool:
    cfg=yaml.safe_load(CONFIG.read_text());manifest=STAGE/"configs/stage01f3_frozen_sha256_manifest.csv"
    with manifest.open() as stream:rows=list(csv.DictReader(stream))
    checks={row["path"]:sha(ROOT/row["path"])==row["sha256"] for row in rows};tag=subprocess.check_output(("git","rev-list","-n","1",cfg["frozen_stage01f3"]["tag"]),cwd=ROOT,text=True).strip();status=json.loads((ROOT/"06_experiments/stage_01f3_mms_convergence/results/stage01f3_evaluation.json").read_text())["status"]
    payload={"manifest_checks":checks,"tag_target":tag,"tag_pass":tag==cfg["frozen_stage01f3"]["evidence_commit"],"stage01f3_status":status,"status":"PASS" if all(checks.values()) and tag==cfg["frozen_stage01f3"]["evidence_commit"] and status=="MMS_CONVERGENCE_VERIFICATION_FAIL" else "FAIL"};write_json(STAGE/"results/stage01f3_freeze_audit.json",payload);return payload["status"]=="PASS"
def main()->int:
    ok=freeze() and cutoff() and equivalence() and events();print(json.dumps({"status":"PASS" if ok else "FAIL"}));return 0 if ok else 1
if __name__=="__main__":raise SystemExit(main())
