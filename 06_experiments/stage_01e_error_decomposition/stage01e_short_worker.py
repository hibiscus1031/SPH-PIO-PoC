"""One independent 40-step Stage 01E diagnostic trajectory."""

from __future__ import annotations

import argparse,csv,gc,hashlib,json,math,os
from pathlib import Path
import statistics,subprocess,sys,time,traceback

import torch,yaml

PROJECT_ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(PROJECT_ROOT/"01_solver"))
ROOT=PROJECT_ROOT/"06_experiments"/"stage_01e_error_decomposition"; CONFIG=ROOT/"configs"/"preregistered_stage01e.yml"
SAMPLES=ROOT/"results"/"short_samples"; SUMMARIES=ROOT/"results"/"short_summaries"; FAILURES=ROOT/"results"/"failures"
from benchmark_alignment.incompressible_tgv_exact import velocity as exact_velocity  # noqa: E402
from benchmark_alignment.residual_decomposition import decompose_state  # noqa: E402
from dynamic_solver.acceleration import DynamicPhysicalParameters  # noqa: E402
from dynamic_solver.diagnostics import density_statistics,mass_weighted_modal_amplitude,process_peak_rss_bytes,tgv_exact_modal_amplitude,tgv_modal_basis,velocity_error_metrics  # noqa: E402
from dynamic_solver.periodic_rollout import explicit_midpoint_dynamic_step,prepare_dynamic_state  # noqa: E402
from dynamic_solver.taylor_green import initialize_taylor_green_state  # noqa: E402


def current_rss() -> int:
    result=subprocess.run(("/bin/ps","-o","rss=","-p",str(os.getpid())),capture_output=True,text=True,check=False)
    return int(result.stdout.strip())*1024 if result.stdout.strip() else 0


def task_for(cfg:dict,run_id:str)->dict:
    short=cfg["short_rollout"]
    if run_id=="stage01e_short_regular": return {"run_id":run_id,"layout":"regular","jitter_fraction":0.0,"seed":0}
    for layout,fraction,prefix in (("jitter_05",0.05,"stage01e_short_j05_s"),("jitter_10",0.10,"stage01e_short_j10_s")):
        for seed in short["frozen_seeds"]:
            if run_id==f"{prefix}{seed}": return {"run_id":run_id,"layout":layout,"jitter_fraction":fraction,"seed":seed}
    raise ValueError("run_id not preregistered")


def write_json(path:Path,value:dict)->None:
    if path.exists(): raise RuntimeError("refusing to overwrite evidence")
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+"\n")


def main()->int:
    parser=argparse.ArgumentParser(); parser.add_argument("--run-id",required=True); args=parser.parse_args()
    if Path(sys.prefix).resolve().name!="sph-pio-poc": raise SystemExit("requires sph-pio-poc environment")
    cfg=yaml.safe_load(CONFIG.read_text()); short=cfg["short_rollout"]; task=task_for(cfg,args.run_id)
    sample_path=SAMPLES/f"{args.run_id}.csv"; summary_path=SUMMARIES/f"{args.run_id}.json"; failure_path=FAILURES/f"{args.run_id}.txt"
    if sample_path.exists() or summary_path.exists() or failure_path.exists(): raise SystemExit("refusing to overwrite short evidence")
    if not gc.isenabled(): raise SystemExit("default cyclic GC must be enabled")
    rows=[]; rss_values=[]; edge_values=[]; step_times=[]; started=time.perf_counter(); status="PASS"; failure_type=""; failure_message=""; completed=0
    try:
        with torch.no_grad():
            state=initialize_taylor_green_state(int(short["resolution"]),support_ratio=float(short["support_ratio"]),reference_density=1.0,velocity_amplitude=1.0,physical_viscosity=float(short["physical_viscosity"]),sound_speed=float(short["sound_speed"]),jitter_fraction=task["jitter_fraction"],seed=task["seed"])
            params=DynamicPhysicalParameters(reference_density=1.0,sound_speed=float(short["sound_speed"]),physical_viscosity=float(short["physical_viscosity"])); state,evaluation=prepare_dynamic_state(state,params)
            for step in range(int(short["steps"])+1):
                decomp=decompose_state(state,evaluation,reference_density=1.0,velocity_amplitude=1.0,viscosity=float(short["physical_viscosity"]))
                exact=exact_velocity(state.positions,float(state.time),velocity_amplitude=1.0,viscosity=float(short["physical_viscosity"])); errors=velocity_error_metrics(state.velocities,exact)
                modal=mass_weighted_modal_amplitude(state.velocities,tgv_modal_basis(state.positions),state.masses); exact_modal=tgv_exact_modal_amplitude(float(state.time),initial_velocity=1.0,kinematic_viscosity=float(short["physical_viscosity"])); density=density_statistics(evaluation.densities,reference_density=1.0); rss=current_rss(); rss_values.append(rss); edge_values.append(decomp["mean_edge_count"])
                rows.append({"run_id":args.run_id,"layout":task["layout"],"seed":task["seed"],"step":step,"time":float(state.time),"velocity_relative_l2":errors["velocity_relative_l2"],"modal_error":abs(modal-exact_modal),"density_fluctuation_relative_rms":density["density_fluctuation_relative_rms"],"EOS_pressure_rms":decomp["EOS_pressure_rms"],"pressure_operator_residual_l2":decomp["R_pressure_operator_L2"],"EOS_initialization_residual_l2":decomp["R_EOS_initialization_L2"],"viscosity_residual_l2":decomp["R_viscosity_L2"],"total_material_residual_l2":decomp["R_total_L2"],"closure_linf":decomp["closure_Linf"],"minimum_separation":decomp["minimum_separation"],"edge_count":decomp["mean_edge_count"],"current_rss_bytes":rss,"peak_rss_bytes":process_peak_rss_bytes()})
                if step==int(short["steps"]): break
                tick=time.perf_counter(); result=explicit_midpoint_dynamic_step(state,dt=float(short["dt"]),parameters=params,start_evaluation=evaluation); step_times.append(time.perf_counter()-tick); state=result.state; evaluation=result.end_evaluation; completed=step+1; del result
                if not gc.isenabled(): raise RuntimeError("cyclic GC disabled in loop")
    except Exception as error:
        status="FAIL"; failure_type=type(error).__name__; failure_message=str(error).replace(str(Path.home()),"<HOME>"); failure_path.parent.mkdir(parents=True,exist_ok=True); failure_path.write_text("".join(traceback.format_exception(error)).replace(str(Path.home()),"<HOME>"))
    sample_path.parent.mkdir(parents=True,exist_ok=True)
    with sample_path.open("x",newline="",encoding="utf-8") as stream:
        fields=list(rows[0]) if rows else ["run_id"]; writer=csv.DictWriter(stream,fieldnames=fields,lineterminator="\n"); writer.writeheader(); writer.writerows(rows)
    q=max(1,len(rss_values)//4); first=statistics.median(rss_values[:q]); final=statistics.median(rss_values[-q:]); final_row=rows[-1] if rows else {}
    summary={"schema_version":"sph-pio-poc.stage01e.short.v1","run_id":args.run_id,"layout":task["layout"],"seed":task["seed"],"status":status,"failure_type":failure_type,"failure_message":failure_message,"pid":os.getpid(),"completed_steps":completed,"expected_steps":int(short["steps"]),"final_time":final_row.get("time"),"final_velocity_relative_l2":final_row.get("velocity_relative_l2"),"initial_velocity_relative_l2":rows[0].get("velocity_relative_l2") if rows else None,"final_modal_error":final_row.get("modal_error"),"initial_density_rms":rows[0].get("density_fluctuation_relative_rms") if rows else None,"initial_EOS_pressure_rms":rows[0].get("EOS_pressure_rms") if rows else None,"initial_pressure_operator_residual_l2":rows[0].get("pressure_operator_residual_l2") if rows else None,"initial_EOS_initialization_residual_l2":rows[0].get("EOS_initialization_residual_l2") if rows else None,"initial_viscosity_residual_l2":rows[0].get("viscosity_residual_l2") if rows else None,"initial_total_material_residual_l2":rows[0].get("total_material_residual_l2") if rows else None,"current_rss_bytes":current_rss(),"peak_rss_bytes":process_peak_rss_bytes(),"first_quartile_rss_median_bytes":first,"final_quartile_rss_median_bytes":final,"absolute_rss_increase_bytes":final-first,"relative_rss_increase":(final-first)/max(first,1),"allocator_warmup_bytes":first-rss_values[0] if rss_values else None,"edge_count_change":edge_values[-1]-edge_values[0] if edge_values else None,"mean_step_time_seconds":statistics.mean(step_times) if step_times else None,"wall_time_seconds":time.perf_counter()-started,"default_gc_enabled_throughout":gc.isenabled(),"torch_no_grad":True,"formal_v2_evidence":False,"sample_path":sample_path.relative_to(PROJECT_ROOT).as_posix(),"failure_path":failure_path.relative_to(PROJECT_ROOT).as_posix() if failure_path.exists() else "","config_sha256":hashlib.sha256(CONFIG.read_bytes()).hexdigest(),"code_git_hash":subprocess.check_output(("git","rev-parse","HEAD"),cwd=PROJECT_ROOT,text=True).strip()}
    write_json(summary_path,summary); print(json.dumps({"run_id":args.run_id,"status":status,"summary_path":summary_path.relative_to(PROJECT_ROOT).as_posix()})); return 0 if status=="PASS" else 1


if __name__=="__main__": raise SystemExit(main())
