"""Generate frozen points and qualify both Stage 01F analytic MMS fields."""

from __future__ import annotations

import csv,hashlib,json,math
from pathlib import Path
import subprocess,sys
from typing import Any

import torch,yaml

PROJECT_ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(PROJECT_ROOT/"01_solver"))
ROOT=PROJECT_ROOT/"06_experiments"/"stage_01f_mms_design"; CONFIG=ROOT/"configs"/"preregistered_mms_specification.yml"; RESULTS=ROOT/"results"
from manufactured_solutions.exact_derivatives import autograd_fields  # noqa:E402
from manufactured_solutions.exact_fields import solution_module  # noqa:E402
from manufactured_solutions.governing_equations import MMSParameters  # noqa:E402
from manufactured_solutions.particle_initialization import regular_initialization  # noqa:E402
from manufactured_solutions.source_injection_contract import required_stage_evaluations  # noqa:E402


def parameters(cfg:dict)->MMSParameters:
    p=cfg["parameters"]
    return MMSParameters(rho0=float(p["rho0"]),sound_speed=float(p["sound_speed"]),viscosity=float(p["viscosity"]),wave_number=float(p["wave_number"]),density_amplitude=float(p["density_amplitude"]),translation_speed=float(p["mms_a_translation_speed"]),decay_rate=float(p["mms_b_decay_rate"]),vortex_amplitude=float(p["mms_b_velocity_amplitude"]),domain_minimum=float(p["domain_minimum"][0]),domain_maximum=float(p["domain_maximum"][0]))


def write_csv(path:Path,rows:list[dict[str,Any]])->None:
    if path.exists(): raise RuntimeError(f"refusing to overwrite {path}")
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("x",newline="",encoding="utf-8") as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator="\n"); writer.writeheader(); writer.writerows(rows)


def write_json(path:Path,value:dict[str,Any])->None:
    if path.exists(): raise RuntimeError(f"refusing to overwrite {path}")
    path.write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+"\n",encoding="utf-8")


def generate_points(cfg:dict)->tuple[torch.Tensor,torch.Tensor,torch.Tensor,torch.Tensor]:
    q=cfg["analytic_qualification"]; generator=torch.Generator().manual_seed(int(q["random_seed"])); count=int(q["random_point_count"]); random_positions=2*torch.rand((count,2),generator=generator,dtype=torch.float64)-1; random_times=float(q["random_time_interval"][1])*torch.rand(count,generator=generator,dtype=torch.float64)
    boundary=[]
    for offset in q["boundary_offsets"]:
        for time in q["boundary_times"]:
            for x,y in ((-1+offset,0.371),(1-offset,0.371),(0.233,-1+offset),(0.233,1-offset),(-1+offset,-1+offset),(-1+offset,1-offset),(1-offset,-1+offset),(1-offset,1-offset)): boundary.append((x,y,time,float(offset)))
    boundary_positions=torch.tensor([[x,y] for x,y,_,_ in boundary],dtype=torch.float64); boundary_times=torch.tensor([t for _,_,t,_ in boundary],dtype=torch.float64)
    write_csv(RESULTS/"preregistered_random_points.csv",[{"point_id":i,"x":float(random_positions[i,0]),"y":float(random_positions[i,1]),"time":float(random_times[i]),"seed":q["random_seed"]} for i in range(count)])
    write_csv(RESULTS/"preregistered_boundary_points.csv",[{"point_id":i,"x":x,"y":y,"time":t,"boundary_offset":offset} for i,(x,y,t,offset) in enumerate(boundary)])
    return random_positions,random_times,boundary_positions,boundary_times


def maximum_difference(manual:dict[str,torch.Tensor],automatic:dict[str,torch.Tensor])->float:
    keys=("partial_time_density","density_gradient","divergence_rho_velocity","partial_time_velocity","velocity_jacobian","velocity_divergence","density_advection","convection","velocity_laplacian","pressure_gradient","material_acceleration","source")
    return max(float((manual[key]-automatic[key]).detach().abs().max()) for key in keys)


def periodic_error(module:Any,positions:torch.Tensor,times:torch.Tensor,p:MMSParameters)->float:
    maximum=0.0
    base=module.manual_fields(positions,times,p)
    for dimension in (0,1):
        shifted=positions.clone(); shifted[:,dimension]+=2.0; value=module.manual_fields(shifted,times,p)
        for key in ("density","velocity","pressure","source"): maximum=max(maximum,float((base[key]-value[key]).abs().max()))
    return maximum


def qualify(solution:str,set_name:str,positions:torch.Tensor,times:torch.Tensor,p:MMSParameters)->dict[str,Any]:
    module=solution_module(solution); manual=module.manual_fields(positions,times,p); automatic=autograd_fields(solution,positions,times,p); eos=manual["pressure"]-p.sound_speed**2*(manual["density"]-p.rho0)
    finite=all(bool(torch.isfinite(value.detach()).all()) for value in manual.values()) and all(bool(torch.isfinite(value.detach()).all()) for value in automatic.values())
    return {"solution":solution,"point_set":set_name,"point_count":len(positions),"minimum_density":float(manual["density"].min()),"maximum_density":float(manual["density"].max()),"maximum_eos_residual":float(eos.abs().max()),"maximum_continuity_residual":float(manual["continuity_residual"].abs().max()),"maximum_x_momentum_residual":float(manual["momentum_residual"][:,0].abs().max()),"maximum_y_momentum_residual":float(manual["momentum_residual"][:,1].abs().max()),"maximum_autograd_continuity_residual":float(automatic["continuity_residual"].detach().abs().max()),"maximum_autograd_momentum_residual":float(automatic["momentum_residual"].detach().abs().max()),"manual_autograd_maximum_difference":maximum_difference(manual,automatic),"source_manual_autograd_maximum_difference":float((manual["source"]-automatic["source"]).detach().abs().max()),"maximum_periodicity_residual":periodic_error(module,positions,times,p),"all_fields_finite":finite}


def vector_statistics(name:str,value:torch.Tensor)->dict[str,Any]:
    magnitude=torch.linalg.vector_norm(value,dim=-1)
    return {"term":name,"L1":float(magnitude.mean()),"L2":float(torch.sqrt(torch.mean(magnitude.square()))),"Linf":float(magnitude.max()),"x_component_rms":float(torch.sqrt(torch.mean(value[:,0].square()))),"y_component_rms":float(torch.sqrt(torch.mean(value[:,1].square())))}


def main()->int:
    if Path(sys.prefix).resolve().name!="sph-pio-poc": raise SystemExit("requires sph-pio-poc environment")
    cfg=yaml.safe_load(CONFIG.read_text()); p=parameters(cfg); RESULTS.mkdir(parents=True,exist_ok=True); random_p,random_t,boundary_p,boundary_t=generate_points(cfg)
    closure=[]
    for solution in ("MMS_A","MMS_B"):
        closure.append(qualify(solution,"random",random_p,random_t,p)); closure.append(qualify(solution,"boundary_near",boundary_p,boundary_t,p))
    write_csv(RESULTS/"analytic_closure.csv",closure)
    b=solution_module("MMS_B").manual_fields(random_p,random_t,p)
    terms=[vector_statistics("partial_time_velocity",b["partial_time_velocity"]),vector_statistics("convection",b["convection"]),vector_statistics("pressure_acceleration",-b["pressure_gradient"]/b["density"][:,None]),vector_statistics("viscous_acceleration",p.viscosity*b["velocity_laplacian"]),vector_statistics("manufactured_force",b["source"])]
    maximum_rms=max(row["L2"] for row in terms)
    for row in terms: row["fraction_of_maximum_L2"]=row["L2"]/maximum_rms
    write_csv(RESULTS/"mms_b_term_scale.csv",terms)
    initialization=[]
    for solution in ("MMS_A","MMS_B"):
        for n in (16,32,64):
            init=regular_initialization(solution,n,p); initialization.append({"solution":solution,"resolution":n,"particle_count":n*n,"initial_volume":float(init.volume[0]),"minimum_density":float(init.initial_density.min()),"maximum_density":float(init.initial_density.max()),"minimum_mass":float(init.mass.min()),"maximum_mass":float(init.mass.max()),"total_mass":float(init.mass.sum()),"masses_fixed":init.masses_fixed_during_rollout,"analytic_density_overwrites_numerical":init.analytic_density_overwrites_numerical_density})
    write_csv(RESULTS/"particle_initialization_audit.csv",initialization)
    contract_positions=random_p[:8]; stages=required_stage_evaluations(solution="MMS_B",start_numerical_positions=contract_positions,start_time=0.03,midpoint_numerical_positions=contract_positions+torch.tensor([1e-4,-2e-4]),midpoint_time=0.030125,parameters=p)
    contract={"stage_count":len(stages),"stages":[x.stage for x in stages],"times":[x.physical_time for x in stages],"separate_position_objects":stages[0].numerical_positions.data_ptr()!=stages[1].numerical_positions.data_ptr(),"source_values_differ":not bool(torch.equal(stages[0].external_acceleration,stages[1].external_acceleration)),"uses_analytic_positions":any(x.uses_analytic_positions for x in stages),"uses_numerical_residual_feedback":any(x.uses_numerical_residual_feedback for x in stages),"included_in_internal_pair_force":any(x.included_in_internal_pair_force for x in stages)}
    write_json(RESULTS/"source_injection_contract_audit.json",contract)
    gates=cfg["analytic_qualification"]["hard_gates"]; closure_pass=all(row["maximum_eos_residual"]<=float(gates["maximum_eos_residual"]) and row["maximum_continuity_residual"]<=float(gates["maximum_continuity_residual"]) and max(row["maximum_x_momentum_residual"],row["maximum_y_momentum_residual"])<=float(gates["maximum_momentum_residual"]) and row["manual_autograd_maximum_difference"]<=float(gates["manual_autograd_maximum_difference"]) and row["minimum_density"]>0 and row["all_fields_finite"] for row in closure)
    scale_pass=min(row["fraction_of_maximum_L2"] for row in terms)>=float(cfg["term_scale_audit"]["minimum_rms_fraction_of_maximum"])
    evidence_complete=len(random_p)==10000 and len(boundary_p)>0 and len(closure)==4 and len(terms)==5 and contract["stage_count"]==2
    status="MMS_EVIDENCE_INCOMPLETE" if not evidence_complete else ("MMS_SPECIFICATION_FAIL" if not closure_pass else ("MMS_SPECIFICATION_CONDITIONAL" if not scale_pass else "MMS_SPECIFICATION_PASS"))
    evaluation={"schema_version":"sph-pio-poc.stage01f.evaluation.v1","status":status,"random_point_count":len(random_p),"boundary_point_count":len(boundary_p),"analytic_closure_pass":closure_pass,"term_scale_pass":scale_pass,"minimum_core_term_fraction_of_maximum":min(row["fraction_of_maximum_L2"] for row in terms),"density_minimum_observed":min(row["minimum_density"] for row in closure),"maximum_eos_residual":max(row["maximum_eos_residual"] for row in closure),"maximum_continuity_residual":max(row["maximum_continuity_residual"] for row in closure),"maximum_momentum_residual":max(max(row["maximum_x_momentum_residual"],row["maximum_y_momentum_residual"]) for row in closure),"manual_autograd_maximum_difference":max(row["manual_autograd_maximum_difference"] for row in closure),"source_manual_autograd_maximum_difference":max(row["source_manual_autograd_maximum_difference"] for row in closure),"maximum_periodicity_residual":max(row["maximum_periodicity_residual"] for row in closure),"particle_initialization_complete":len(initialization)==6,"source_injection_contract_complete":contract["stages"]==["start","midpoint"] and contract["source_values_differ"] and not contract["uses_analytic_positions"] and not contract["uses_numerical_residual_feedback"] and not contract["included_in_internal_pair_force"],"mms_b_reference_plan_complete":True,"solver_rollout_run":False,"training_artifacts_created":False,"stage01f2_started":False,"v3_started":False,"stage02_started":False,"config_sha256":hashlib.sha256(CONFIG.read_bytes()).hexdigest(),"code_git_hash":subprocess.check_output(("git","rev-parse","HEAD"),cwd=PROJECT_ROOT,text=True).strip()}
    write_json(RESULTS/"stage01f_evaluation.json",evaluation); print(json.dumps({"status":status,"random_points":len(random_p),"boundary_points":len(boundary_p)})); return 0 if status in ("MMS_SPECIFICATION_PASS","MMS_SPECIFICATION_CONDITIONAL") else 1


if __name__=="__main__": raise SystemExit(main())
