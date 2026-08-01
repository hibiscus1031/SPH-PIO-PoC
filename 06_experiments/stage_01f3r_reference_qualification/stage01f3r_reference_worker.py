"""Three-level dense DOP853 reference and 41-time sparse replay comparison."""

from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import subprocess,sys
from typing import Any
import numpy as np,torch,yaml

ROOT=Path(__file__).resolve().parents[2];SOLVER=ROOT/"01_solver";sys.path.insert(0,str(SOLVER));STAGE=ROOT/"06_experiments/stage_01f3r_reference_qualification";CONFIG=STAGE/"configs/preregistered_stage01f3r.yml"
from dynamic_solver.acceleration import DynamicPhysicalParameters,evaluate_internal_acceleration
from dynamic_solver.sourced_acceleration import initialize_mms_state
from dynamic_solver.state import DynamicSPHState
from manufactured_solutions.dense_all_pairs_rhs import evaluate_dense_all_pairs
from manufactured_solutions.dense_semidiscrete_reference import integrate_dense_reference
from manufactured_solutions.dynamic_source_adapter import evaluate_mms_source
from manufactured_solutions.mms_b_dop853_reference import parameter_hash
from manufactured_solutions.semidiscrete_reference import integrate_semidiscrete_dop853
from structure_preserving.neighborhood import wrap_periodic

def sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()
def git_hash()->str:return subprocess.check_output(("git","rev-parse","HEAD"),cwd=ROOT,text=True).strip()
def write_json(path:Path,value:dict[str,Any])->None:
    if path.exists():raise RuntimeError(f"refusing to overwrite {path}")
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+"\n")
def linf(a:np.ndarray,b:np.ndarray)->float:return float(np.max(np.abs(a-b)))
def sparse_reference(solution:str,initial:DynamicSPHState,times:np.ndarray,settings:dict[str,float]):
    count=initial.particle_count;physics=DynamicPhysicalParameters();y0=np.concatenate((initial.positions.numpy().reshape(-1),initial.velocities.numpy().reshape(-1)))
    def rhs(time:float,value:np.ndarray)->np.ndarray:
        p=torch.from_numpy(value[:2*count].reshape(count,2));v=torch.from_numpy(value[2*count:].reshape(count,2));wrapped=wrap_periodic(p,initial.domain_min,initial.domain_max);state=DynamicSPHState(positions=wrapped,velocities=v,masses=initial.masses,densities=torch.ones_like(initial.masses),pressures=torch.zeros_like(initial.masses),supports=initial.supports,domain_min=initial.domain_min,domain_max=initial.domain_max,time=time)
        with torch.no_grad():evaluation=evaluate_internal_acceleration(state,physics);source=evaluate_mms_source(solution,wrapped,time)
        return np.concatenate((v.numpy().reshape(-1),(evaluation.acceleration+source).numpy().reshape(-1)))
    return integrate_semidiscrete_dop853(rhs,y0,times,**settings)
def fields(solution:str,states:np.ndarray,times:np.ndarray,initial:DynamicSPHState,path:str)->dict[str,np.ndarray]:
    count=initial.particle_count;density=[];pressure=[];acceleration=[];physics=DynamicPhysicalParameters()
    for time_value,value in zip(times,states):
        p=torch.from_numpy(value[:2*count].reshape(count,2).copy());v=torch.from_numpy(value[2*count:].reshape(count,2).copy());wrapped=wrap_periodic(p,initial.domain_min,initial.domain_max)
        with torch.no_grad():
            if path=="dense":evaluation=evaluate_dense_all_pairs(solution,wrapped,v,initial.masses,initial.supports,float(time_value));rho=evaluation.density;pres=evaluation.pressure;acc=evaluation.total_acceleration
            else:
                state=DynamicSPHState(positions=wrapped,velocities=v,masses=initial.masses,densities=torch.ones_like(initial.masses),pressures=torch.zeros_like(initial.masses),supports=initial.supports,domain_min=initial.domain_min,domain_max=initial.domain_max,time=float(time_value));evaluation=evaluate_internal_acceleration(state,physics);rho=evaluation.densities;pres=evaluation.pressures;acc=evaluation.acceleration+evaluate_mms_source(solution,wrapped,float(time_value))
        density.append(rho.numpy().copy());pressure.append(pres.numpy().copy());acceleration.append(acc.numpy().copy())
    return {"density":np.stack(density),"pressure":np.stack(pressure),"total_acceleration":np.stack(acceleration)}
def compare_states(label:str,left:np.ndarray,right:np.ndarray,left_fields:dict[str,np.ndarray],right_fields:dict[str,np.ndarray],count:int)->dict[str,float]:
    result={"position_linf":linf(left[:,:2*count],right[:,:2*count]),"velocity_linf":linf(left[:,2*count:],right[:,2*count:])}
    for key in left_fields:result[f"{key}_linf"]=linf(left_fields[key],right_fields[key])
    return {f"{label}_{key}":value for key,value in result.items()}
def main()->int:
    parser=argparse.ArgumentParser();parser.add_argument("--solution",required=True,choices=("MMS_A","MMS_B"));args=parser.parse_args();cfg=yaml.safe_load(CONFIG.read_text())["dense_reference"];initial=initialize_mms_state(args.solution,cfg["resolution"],support_ratio=cfg["support_ratio"]);times=np.linspace(0,cfg["t_final"],cfg["sample_count"])
    dense={name:integrate_dense_reference(args.solution,initial.positions,initial.velocities,initial.masses,initial.supports,times,**cfg[name]) for name in ("baseline","tighter","third")}
    dense_fields={name:fields(args.solution,reference.states,times,initial,"dense") for name,reference in dense.items()}
    sparse={name:sparse_reference(args.solution,initial,times,cfg[name]) for name in ("baseline","tighter")};sparse_fields={name:fields(args.solution,reference.states,times,initial,"sparse") for name,reference in sparse.items()}
    count=initial.particle_count;comparisons={}
    comparisons.update(compare_states("dense_baseline_tighter",dense["baseline"].states,dense["tighter"].states,dense_fields["baseline"],dense_fields["tighter"],count));comparisons.update(compare_states("dense_tighter_third",dense["tighter"].states,dense["third"].states,dense_fields["tighter"],dense_fields["third"],count));comparisons.update(compare_states("sparse_baseline_dense_baseline",sparse["baseline"].states,dense["baseline"].states,sparse_fields["baseline"],dense_fields["baseline"],count));comparisons.update(compare_states("sparse_tighter_dense_tighter",sparse["tighter"].states,dense["tighter"].states,sparse_fields["tighter"],dense_fields["tighter"],count))
    old=np.load(ROOT/f"06_experiments/stage_01f3_mms_convergence/references/semidiscrete_{args.solution.lower()}_n16_dop853.npz");old_indices=[int(round(value/(cfg["t_final"]/(cfg["sample_count"]-1)))) for value in old["times"]];old_identity={"baseline_linf":linf(sparse["baseline"].states[old_indices],old["baseline"]),"tighter_linf":linf(sparse["tighter"].states[old_indices],old["sensitivity"])}
    dense_path=STAGE/"references"/f"dense_{args.solution.lower()}_three_level.npz";sparse_path=STAGE/"references"/f"sparse_{args.solution.lower()}_41_time_replay.npz";np.savez_compressed(dense_path,times=times,baseline=dense["baseline"].states,tighter=dense["tighter"].states,third=dense["third"].states);np.savez_compressed(sparse_path,times=times,baseline=sparse["baseline"].states,tighter=sparse["tighter"].states)
    sensitivity_keys=["position_linf","velocity_linf"]
    checks={"all_finite":all(np.isfinite(reference.states).all() for reference in (*dense.values(),*sparse.values())),"dense_baseline_tighter":all(comparisons[f"dense_baseline_tighter_{key}"]<=1e-9 for key in sensitivity_keys),"dense_tighter_third":all(comparisons[f"dense_tighter_third_{key}"]<=1e-9 for key in sensitivity_keys),"sparse_dense_baseline_state":all(comparisons[f"sparse_baseline_dense_baseline_{key}"]<=1e-9 for key in sensitivity_keys),"sparse_dense_tighter_state":all(comparisons[f"sparse_tighter_dense_tighter_{key}"]<=1e-9 for key in sensitivity_keys),"old_sparse_replay_identity":max(old_identity.values())<=1e-12}
    stats={path:{name:{"nfev":ref.nfev,"rtol":ref.rtol,"atol":ref.atol,"max_step":ref.max_step} for name,ref in refs.items()} for path,refs in (("dense",dense),("sparse",sparse))}
    payload={"schema_version":"sph-pio-poc.stage01f3r.reference.v1","solution":args.solution,"comparisons":comparisons,"old_sparse_replay_identity":old_identity,"statistics":stats,"checks":checks,"parameter_sha256":parameter_hash(),"code_git_hash":git_hash(),"config_sha256":sha(CONFIG),"dense_reference_path":dense_path.relative_to(ROOT).as_posix(),"dense_reference_sha256":sha(dense_path),"sparse_replay_path":sparse_path.relative_to(ROOT).as_posix(),"sparse_replay_sha256":sha(sparse_path),"status":"PASS" if all(checks.values()) else "FAIL"};write_json(STAGE/"results"/f"{args.solution.lower()}_reference_qualification.json",payload);print(json.dumps({"status":payload["status"]}));return 0 if payload["status"]=="PASS" else 1
if __name__=="__main__":raise SystemExit(main())
