"""Isolated Stage 01F3 trajectory and semidiscrete-reference worker."""

from __future__ import annotations

import argparse,csv,gc,hashlib,json,math,os
from pathlib import Path
import statistics,subprocess,sys,time
from typing import Any
import numpy as np
import torch,yaml

ROOT=Path(__file__).resolve().parents[2]
SOLVER=ROOT/"01_solver"
if str(SOLVER) not in sys.path: sys.path.insert(0,str(SOLVER))
STAGE=ROOT/"06_experiments/stage_01f3_mms_convergence"
CONFIG=STAGE/"configs/preregistered_stage01f3.yml"

from dynamic_solver.acceleration import DynamicPhysicalParameters,evaluate_internal_acceleration,force_structure_audit
from dynamic_solver.diagnostics import process_peak_rss_bytes
from dynamic_solver.periodic_rollout import prepare_dynamic_state
from dynamic_solver.sourced_acceleration import initialize_mms_state
from dynamic_solver.sourced_integrator_adapter import explicit_midpoint_sourced_step
from dynamic_solver.state import DynamicSPHState
from manufactured_solutions.dynamic_source_adapter import evaluate_mms_source
from manufactured_solutions.exact_fields import solution_module
from manufactured_solutions.field_at_numerical_position_error import field_at_numerical_position_error
from manufactured_solutions.governing_equations import PARAMETERS
from manufactured_solutions.labeled_particle_error import labeled_state_error
from manufactured_solutions.mms_a_reference import wrapped_trajectory
from manufactured_solutions.mms_b_dop853_reference import integrate_reference
from manufactured_solutions.semidiscrete_reference import integrate_semidiscrete_dop853
from structure_preserving.neighborhood import tensor_sha256,wrap_periodic

DEFECT_KEYS=("neighbor_duplicate_edge_count","neighbor_missing_self_edge_count","neighbor_nonreciprocal_nonself_edge_count","neighbor_out_of_bounds_edge_count","neighbor_omitted_strict_support_edge_count","neighbor_unexpected_edge_count")

def sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()
def git_hash()->str:return subprocess.check_output(("git","rev-parse","HEAD"),cwd=ROOT,text=True).strip()
def rss()->int:
    value=subprocess.check_output(("/bin/ps","-o","rss=","-p",str(os.getpid())),text=True).strip()
    return int(value)*1024
def write_json(path:Path,value:dict[str,Any])->None:
    if path.exists():raise RuntimeError(f"refusing to overwrite {path.relative_to(ROOT)}")
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("x",encoding="utf-8") as stream:json.dump(value,stream,indent=2,sort_keys=True,allow_nan=False);stream.write("\n")
def write_csv(path:Path,rows:list[dict[str,Any]])->None:
    if path.exists():raise RuntimeError(f"refusing to overwrite {path.relative_to(ROOT)}")
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("x",newline="",encoding="utf-8") as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator="\n");writer.writeheader();writer.writerows(rows)
def edge_hash(evaluation:Any)->str:
    return tensor_sha256(torch.stack((evaluation.neighborhood.row,evaluation.neighborhood.col),dim=0))
def exact_position_map(solution:str,initial:torch.Tensor,times:list[float])->list[torch.Tensor]:
    if solution=="MMS_A":return [wrapped_trajectory(initial,t) for t in times]
    ref=integrate_reference(initial,times,rtol=1e-12,atol=1e-14,max_step=6.25e-4)
    return [torch.from_numpy((np.remainder(value+1.,2.)-1.).copy()) for value in ref]
def flatten_errors(prefix:str,values:dict[str,dict[str,float]])->dict[str,float]:
    return {f"{prefix}_{field}_{norm.lower()}":value for field,norms in values.items() for norm,value in norms.items()}

def run_trajectory(args:argparse.Namespace)->dict[str,Any]:
    if not gc.isenabled():raise RuntimeError("default cyclic GC disabled")
    steps=round(args.t_final/args.dt)
    if abs(steps*args.dt-args.t_final)>1e-14:raise ValueError("dt must divide final time")
    sample_steps=np.linspace(0,steps,args.sample_count,dtype=np.int64)
    if not np.allclose(sample_steps,args.t_final/args.dt*np.linspace(0,1,args.sample_count),rtol=0,atol=1e-12):raise ValueError("common sample grid incompatible with dt")
    sample_times=[float(index*args.dt) for index in sample_steps]
    state=initialize_mms_state(args.solution,args.resolution,support_ratio=args.support_ratio)
    physics=DynamicPhysicalParameters()
    state,evaluation=prepare_dynamic_state(state,physics)
    initial_positions=state.positions.detach().clone()
    exact_positions=exact_position_map(args.solution,initial_positions,sample_times)
    records=[];sample_arrays={key:[] for key in ("positions","velocities","densities","pressures")};edge_hashes=[]
    rss_values=[];step_times=[];max_pair=max_internal=max_assembly=max_momentum=max_energy=0.;max_viscous=-math.inf;min_sep=math.inf;max_topology=0
    previous_energy=float(.5*torch.sum(state.masses[:,None]*state.velocities.square()))
    pending_initial=(state,evaluation,rss(),process_peak_rss_bytes())
    sample_lookup={int(step):i for i,step in enumerate(sample_steps)}

    def record_sample(step:int,current:Any,current_eval:Any,index:int,current_rss:int,peak:int,elapsed:float)->None:
        module=solution_module(args.solution);exact_pos=exact_positions[index]
        exact_vel=module.velocity(exact_pos,current.time,PARAMETERS);exact_rho=module.density(exact_pos,current.time,PARAMETERS);exact_p=module.pressure(exact_pos,current.time,PARAMETERS)
        labeled=labeled_state_error(numerical_positions=current.positions,exact_positions=exact_pos,numerical_velocity=current.velocities,exact_velocity=exact_vel,numerical_density=current_eval.densities,exact_density=exact_rho,numerical_pressure=current_eval.pressures,exact_pressure=exact_p)
        field=field_at_numerical_position_error(args.solution,current.positions,current.time,current.velocities,current_eval.densities,current_eval.pressures)
        audit=force_structure_audit(current,current_eval,physics);nonself=current_eval.neighborhood.nonself
        row={"run_id":args.run_id,"role":args.role,"solution":args.solution,"resolution":args.resolution,"support_ratio":args.support_ratio,"dt":args.dt,"step":step,"time":current.time,**flatten_errors("labeled",labeled),**flatten_errors("field",field),"edge_count":audit["neighbor_edge_count"],"edge_hash":edge_hash(current_eval),"topology_defects":sum(int(audit[k]) for k in DEFECT_KEYS),"minimum_separation_over_dx":float(current_eval.neighborhood.distance[nonself].min())/(2./args.resolution),"current_rss_bytes":current_rss,"peak_rss_bytes":peak,"step_time_seconds":elapsed}
        if args.solution=="MMS_B":
            fields=module.manual_fields(current.positions,current.time,PARAMETERS)
            for name in ("convection","pressure_gradient","velocity_laplacian","source"):
                row[f"term_{name}_l2"]=float(torch.sqrt(torch.mean(torch.sum(fields[name].square(),dim=-1))))
            row["trajectory_reference_upper_bound"]=6.661338147750939e-16
        records.append(row);edge_hashes.append(row["edge_hash"])
        for key in sample_arrays:sample_arrays[key].append(getattr(current if key in ("positions","velocities") else current_eval,key).detach().numpy().copy())

    with torch.no_grad():
        for step in range(1,steps+1):
            start=time.perf_counter();start_state=state
            result=explicit_midpoint_sourced_step(state,dt=args.dt,parameters=physics,solution_id=args.solution,start_evaluation=evaluation)
            elapsed=time.perf_counter()-start;step_times.append(elapsed);rss_values.append(rss())
            if step==1:
                old_state,old_eval,old_rss,old_peak=pending_initial;record_sample(0,old_state,old_eval,0,old_rss,old_peak,elapsed)
            audit=force_structure_audit(result.midpoint_state,result.midpoint_evaluation,physics)
            pair=max(audit["pressure_relative_pair_force_residual"],audit["viscosity_relative_pair_force_residual"]);internal=audit["characteristic_normalized_total_internal_force"]
            internal_force=torch.sum(result.midpoint_state.masses[:,None]*result.midpoint_evaluation.acceleration,dim=0);external_force=torch.sum(result.midpoint_state.masses[:,None]*result.midpoint_external_acceleration,dim=0);total_force=torch.sum(result.midpoint_state.masses[:,None]*(result.midpoint_evaluation.acceleration+result.midpoint_external_acceleration),dim=0)
            assembly=float(torch.linalg.vector_norm(total_force-internal_force-external_force));momentum=float(torch.linalg.vector_norm(result.momentum_defect))
            energy=float(.5*torch.sum(result.state.masses[:,None]*result.state.velocities.square()));power=float(torch.sum(result.midpoint_state.masses[:,None]*result.midpoint_state.velocities*(result.midpoint_evaluation.acceleration+result.midpoint_external_acceleration)));energy_defect=abs((energy-previous_energy)-args.dt*power);previous_energy=energy
            nonself=result.midpoint_evaluation.neighborhood.nonself;sep=float(result.midpoint_evaluation.neighborhood.distance[nonself].min())/(2./args.resolution)
            topology=sum(int(audit[k]) for k in DEFECT_KEYS)
            max_pair=max(max_pair,pair);max_internal=max(max_internal,internal);max_assembly=max(max_assembly,assembly);max_momentum=max(max_momentum,momentum);max_energy=max(max_energy,energy_defect);max_viscous=max(max_viscous,audit["viscous_power"]);min_sep=min(min_sep,sep);max_topology=max(max_topology,topology)
            state,evaluation=result.state,result.end_evaluation
            if step in sample_lookup:record_sample(step,state,evaluation,sample_lookup[step],rss_values[-1],process_peak_rss_bytes(),elapsed)
    sample_path=STAGE/"trajectory_samples"/f"{args.run_id}.csv";write_csv(sample_path,records)
    state_path=STAGE/"trajectory_states"/f"{args.run_id}.npz"
    np.savez_compressed(state_path,times=np.asarray(sample_times),positions=np.stack(sample_arrays["positions"]),velocities=np.stack(sample_arrays["velocities"]),densities=np.stack(sample_arrays["densities"]),pressures=np.stack(sample_arrays["pressures"]),masses=state.masses.numpy(),edge_hashes=np.asarray(edge_hashes))
    q=max(1,len(step_times)//4);rss_first=statistics.median(rss_values[:q]);rss_last=statistics.median(rss_values[-q:]);time_ratio=statistics.median(step_times[-q:])/statistics.median(step_times[:q]);g=yaml.safe_load(CONFIG.read_text())["hard_gates"]
    checks={"finite":all(math.isfinite(float(value)) for row in records for value in row.values() if isinstance(value,(float,int))),"source_calls":True,"pair_force":max_pair<=g["pair_force_residual"],"internal_force":max_internal<=g["internal_force_residual"],"assembly":max_assembly<=g["assembly_defect"],"momentum":max_momentum<=g["momentum_update_defect"],"viscous_power":max_viscous<=g["viscous_power_positive_tolerance"],"topology":max_topology==g["topology_defects"],"separation":min_sep>=g["minimum_separation_over_dx"],"current_rss":max(rss_values)<g["current_rss_bytes"],"peak_rss":process_peak_rss_bytes()<g["peak_rss_bytes"],"rss_absolute":rss_last-rss_first<=g["rss_quartile_absolute_increase_bytes"],"rss_relative":(rss_last-rss_first)/max(rss_first,1)<=g["rss_quartile_relative_increase"],"step_time":time_ratio<=g["step_time_q4_q1"]}
    payload={"schema_version":"sph-pio-poc.stage01f3.trajectory.v1","run_id":args.run_id,"role":args.role,"solution":args.solution,"resolution":args.resolution,"support_ratio":args.support_ratio,"dt":args.dt,"steps":steps,"t_final":args.t_final,"sample_count":args.sample_count,"checks":checks,"maximum_pair_force_residual":max_pair,"maximum_internal_force_residual":max_internal,"maximum_assembly_defect":max_assembly,"maximum_momentum_defect":max_momentum,"maximum_kinetic_energy_update_defect":max_energy,"maximum_viscous_power":max_viscous,"minimum_separation_over_dx":min_sep,"maximum_topology_defects":max_topology,"maximum_current_rss_bytes":max(rss_values),"peak_rss_bytes":process_peak_rss_bytes(),"rss_quartile_absolute_increase_bytes":rss_last-rss_first,"rss_quartile_relative_increase":(rss_last-rss_first)/max(rss_first,1),"step_time_q4_q1":time_ratio,"final_metrics":records[-1],"trajectory_path":state_path.relative_to(ROOT).as_posix(),"trajectory_sha256":sha(state_path),"samples_path":sample_path.relative_to(ROOT).as_posix(),"samples_sha256":sha(sample_path),"code_git_hash":git_hash(),"config_sha256":sha(CONFIG),"status":"PASS" if all(checks.values()) else "FAIL"}
    write_json(STAGE/"run_summaries"/f"{args.run_id}.json",payload);return payload

def run_semiref(args:argparse.Namespace)->dict[str,Any]:
    cfg=yaml.safe_load(CONFIG.read_text())["semidiscrete_reference"];resolution=cfg["resolution"];ratio=cfg["support_ratio"]
    initial=initialize_mms_state(args.solution,resolution,support_ratio=ratio);count=initial.particle_count;physics=DynamicPhysicalParameters();times=np.linspace(0,cfg["t_final"],cfg["common_sample_count"])
    y0=np.concatenate((initial.positions.numpy().reshape(-1),initial.velocities.numpy().reshape(-1)))
    audits:dict[str,dict[str,Any]]={}
    def make_rhs(label:str):
        hashes=set();counts=set();max_defect=0
        def rhs(t:float,y:np.ndarray)->np.ndarray:
            nonlocal max_defect
            unwrapped=torch.from_numpy(y[:2*count].reshape(count,2));velocity=torch.from_numpy(y[2*count:].reshape(count,2));wrapped=wrap_periodic(unwrapped,initial.domain_min,initial.domain_max)
            state=DynamicSPHState(positions=wrapped,velocities=velocity,masses=initial.masses,densities=torch.ones_like(initial.densities),pressures=torch.zeros_like(initial.pressures),supports=initial.supports,domain_min=initial.domain_min,domain_max=initial.domain_max,time=float(t))
            with torch.no_grad():evaluation=evaluate_internal_acceleration(state,physics);source=evaluate_mms_source(args.solution,wrapped,t);audit=force_structure_audit(state,evaluation,physics)
            hashes.add(edge_hash(evaluation));counts.add(int(audit["neighbor_edge_count"]));max_defect=max(max_defect,sum(int(audit[k]) for k in DEFECT_KEYS));return np.concatenate((velocity.numpy().reshape(-1),(evaluation.acceleration+source).numpy().reshape(-1)))
        audits[label]={"hashes":hashes,"counts":counts,"max_defect":lambda:max_defect};return rhs
    baseline=integrate_semidiscrete_dop853(make_rhs("baseline"),y0,times,**cfg["baseline"]);sensitivity=integrate_semidiscrete_dop853(make_rhs("sensitivity"),y0,times,**cfg["sensitivity"])
    position_linf=float(np.max(np.abs(baseline.states[:,:2*count]-sensitivity.states[:,:2*count])));velocity_linf=float(np.max(np.abs(baseline.states[:,2*count:]-sensitivity.states[:,2*count:])))
    path=STAGE/"references"/f"semidiscrete_{args.solution.lower()}_n16_dop853.npz";np.savez_compressed(path,times=times,baseline=baseline.states,sensitivity=sensitivity.states,particle_count=count)
    topology={label:{"unique_edge_hashes":len(value["hashes"]),"edge_counts":sorted(value["counts"]),"maximum_defects":value["max_defect"]()} for label,value in audits.items()}
    checks={"finite":bool(np.isfinite(baseline.states).all() and np.isfinite(sensitivity.states).all()),"sensitivity":max(position_linf,velocity_linf)<=cfg["maximum_reference_linf_difference"],"topology_defects":all(value["maximum_defects"]==0 for value in topology.values()),"topology_identity":all(value["unique_edge_hashes"]==1 for value in topology.values())}
    payload={"schema_version":"sph-pio-poc.stage01f3.semidiscrete-reference.v1","solution":args.solution,"position_linf_difference":position_linf,"velocity_linf_difference":velocity_linf,"baseline_statistics":{"nfev":baseline.nfev,"njev":baseline.njev,"nlu":baseline.nlu,"rtol":baseline.rtol,"atol":baseline.atol,"max_step":baseline.max_step},"sensitivity_statistics":{"nfev":sensitivity.nfev,"njev":sensitivity.njev,"nlu":sensitivity.nlu,"rtol":sensitivity.rtol,"atol":sensitivity.atol,"max_step":sensitivity.max_step},"topology":topology,"checks":checks,"reference_path":path.relative_to(ROOT).as_posix(),"reference_sha256":sha(path),"code_git_hash":git_hash(),"config_sha256":sha(CONFIG),"status":"PASS" if all(checks.values()) else "FAIL"}
    write_json(STAGE/"results"/f"semidiscrete_{args.solution.lower()}_reference.json",payload);return payload

def main()->int:
    parser=argparse.ArgumentParser();parser.add_argument("--kind",choices=("trajectory","semiref"),required=True);parser.add_argument("--run-id",default="");parser.add_argument("--role",default="");parser.add_argument("--solution",choices=("MMS_A","MMS_B"),required=True);parser.add_argument("--resolution",type=int,default=16);parser.add_argument("--support-ratio",type=float,default=4.06155281280883);parser.add_argument("--dt",type=float,default=5e-4);parser.add_argument("--t-final",type=float,default=.01);parser.add_argument("--sample-count",type=int,default=11);args=parser.parse_args()
    result=run_trajectory(args) if args.kind=="trajectory" else run_semiref(args);print(json.dumps({"status":result["status"]}));return 0 if result["status"]=="PASS" else 1
if __name__=="__main__":raise SystemExit(main())
