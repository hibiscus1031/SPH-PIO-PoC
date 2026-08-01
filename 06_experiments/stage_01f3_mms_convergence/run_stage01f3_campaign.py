"""Serial scalar-only coordinator for Stage 01F3 isolated processes."""

from __future__ import annotations
import argparse,csv,hashlib,json,os
from pathlib import Path
import subprocess,sys,time
from typing import Any
import yaml

ROOT=Path(__file__).resolve().parents[2];STAGE=ROOT/"06_experiments/stage_01f3_mms_convergence";CONFIG=STAGE/"configs/preregistered_stage01f3.yml";WORKER=STAGE/"stage01f3_worker.py";INDEX=STAGE/"results/campaign_index.csv";LOGS=STAGE/"logs"
FIELDS=("kind","case_id","pid","return_code","child_reclaimed","child_rss_after_reap_bytes","parent_rss_before_bytes","parent_rss_after_bytes","scalar_only_summary","result_path","log_path","config_sha256","code_git_hash","wall_time_seconds")
def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def rss(pid:int|None=None)->int:
    result=subprocess.run(("/bin/ps","-o","rss=","-p",str(os.getpid() if pid is None else pid)),text=True,capture_output=True)
    return int(result.stdout.strip())*1024 if result.stdout.strip() else 0
def append(row:dict[str,Any])->None:
    new=not INDEX.exists();INDEX.parent.mkdir(parents=True,exist_ok=True)
    with INDEX.open("a",newline="",encoding="utf-8") as stream:
        writer=csv.DictWriter(stream,fieldnames=FIELDS,lineterminator="\n");
        if new:writer.writeheader()
        writer.writerow({k:row.get(k,"") for k in FIELDS})
def run_child(kind:str,case_id:str,command:list[str],result:Path)->bool:
    if result.exists():return json.loads(result.read_text())["status"]=="PASS"
    log=LOGS/f"{case_id}.log";LOGS.mkdir(parents=True,exist_ok=True)
    if log.exists():raise RuntimeError(f"refusing to overwrite {log}")
    before=rss();started=time.perf_counter()
    with log.open("x",encoding="utf-8") as stream:child=subprocess.Popen(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,text=True);pid=child.pid;code=child.wait()
    after=rss();child_after=rss(pid);reclaimed=child_after==0;scalar=False
    if result.exists():scalar=all(not isinstance(v,(list,tuple)) for v in json.loads(result.read_text()).values())
    append({"kind":kind,"case_id":case_id,"pid":pid,"return_code":code,"child_reclaimed":reclaimed,"child_rss_after_reap_bytes":child_after,"parent_rss_before_bytes":before,"parent_rss_after_bytes":after,"scalar_only_summary":scalar,"result_path":result.relative_to(ROOT).as_posix() if result.exists() else "","log_path":log.relative_to(ROOT).as_posix(),"config_sha256":sha(CONFIG),"code_git_hash":subprocess.check_output(("git","rev-parse","HEAD"),cwd=ROOT,text=True).strip(),"wall_time_seconds":time.perf_counter()-started})
    return code==0 and reclaimed and scalar and result.exists()
def command(run_id:str,role:str,solution:str,resolution:int,ratio:float,dt:float,t_final:float,count:int)->list[str]:
    return [sys.executable,str(WORKER),"--kind","trajectory","--run-id",run_id,"--role",role,"--solution",solution,"--resolution",str(resolution),"--support-ratio",repr(ratio),"--dt",repr(dt),"--t-final",repr(t_final),"--sample-count",str(count)]
def task(run_id:str,role:str,solution:str,resolution:int,ratio:float,dt:float,t_final:float,count:int)->bool:
    return run_child(role,run_id,command(run_id,role,solution,resolution,ratio,dt,t_final,count),STAGE/"run_summaries"/f"{run_id}.json")
def prereq(cfg:dict[str,Any])->bool:
    manifest=STAGE/"configs/stage01f2_frozen_sha256_manifest.csv";identities={row["path"]:sha(ROOT/row["path"])==row["sha256"] for row in csv.DictReader(manifest.open())}
    evaluator=json.loads((ROOT/cfg["frozen_stage01f2"]["evaluator"]).read_text());tag=subprocess.check_output(("git","rev-list","-n","1",cfg["frozen_stage01f2"]["tag"]),cwd=ROOT,text=True).strip()
    pytest_log=LOGS/"full_pytest.log";LOGS.mkdir(parents=True,exist_ok=True)
    if pytest_log.exists():raise RuntimeError("refusing to overwrite full pytest log")
    with pytest_log.open("x",encoding="utf-8") as stream:test=subprocess.run((sys.executable,"-m","pytest","-q"),cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,text=True)
    f2root=ROOT/"06_experiments/stage_01f2_mms_implementation/results";f2checks={name:json.loads((f2root/name).read_text())["status"]=="PASS" for name in ("zero_source_tgv_n16_20.json","zero_source_tgv_n32_20.json","mms_b_n16_reference_summary.json","mms_b_n32_reference_summary.json")}
    payload={"schema_version":"sph-pio-poc.stage01f3.prerequisite.v1","pytest_return_code":test.returncode,"manifest_identity":identities,"stage01f2_evaluator_status":evaluator["status"],"tag_target":tag,"stage01f2_checks":f2checks,"status":"PASS" if test.returncode==0 and all(identities.values()) and evaluator["status"]=="MMS_IMPLEMENTATION_VERIFIED_PASS" and tag==cfg["frozen_stage01f2"]["evidence_commit"] and all(f2checks.values()) else "FAIL"}
    path=STAGE/"results/prerequisite_static.json";path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n")
    if payload["status"]!="PASS":return False
    ratio=cfg["semidiscrete_reference"]["support_ratio"]
    return task("prereq_smoke_a","prerequisite_smoke","MMS_A",16,ratio,5e-4,.005,11) and task("prereq_smoke_b","prerequisite_smoke","MMS_B",16,ratio,5e-4,.005,11)
def select_space_dt(cfg:dict[str,Any])->bool:
    rows={}
    for solution in ("MMS_A","MMS_B"):
        for code in ("6p25e5","3p125e5"):
            rows[(solution,code)]=json.loads((STAGE/"run_summaries"/f"isolate_{solution[-1].lower()}_{code}.json").read_text())
    comparisons={};use_fine=False
    for solution in ("MMS_A","MMS_B"):
        coarse=rows[(solution,"6p25e5")]["final_metrics"];fine=rows[(solution,"3p125e5")]["final_metrics"]
        fields=("labeled_position_l2","labeled_velocity_l2","labeled_density_l2","labeled_pressure_l2")
        values={field:abs(coarse[field]-fine[field])/max(abs(fine[field]),1e-30) for field in fields};comparisons[solution]=values;use_fine=use_fine or max(values.values())>cfg["space"]["isolation_maximum_relative_difference"]
    selected=3.125e-5 if use_fine else 6.25e-5;payload={"schema_version":"sph-pio-poc.stage01f3.space-dt-selection.v1","comparisons":comparisons,"threshold":cfg["space"]["isolation_maximum_relative_difference"],"selected_dt":selected,"status":"PASS"}
    path=STAGE/"results/space_dt_selection.json";
    if path.exists():raise RuntimeError("refusing to overwrite space dt selection")
    path.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n");return True
def main()->int:
    parser=argparse.ArgumentParser();parser.add_argument("--phase",required=True,choices=("prerequisite","semiref","semitime","conttime","isolation","space","fixed","determinism","n64","all"));args=parser.parse_args();cfg=yaml.safe_load(CONFIG.read_text());phases=("prerequisite","semiref","semitime","conttime","isolation","space","fixed","determinism") if args.phase=="all" else (args.phase,);ok=True
    for phase in phases:
        if phase=="prerequisite":ok=prereq(cfg)
        elif phase=="semiref":
            for sol in ("MMS_A","MMS_B"):ok=run_child("semidiscrete_reference",f"semiref_{sol[-1].lower()}",[sys.executable,str(WORKER),"--kind","semiref","--solution",sol],STAGE/"results"/f"semidiscrete_{sol.lower()}_reference.json") and ok
        elif phase=="semitime":
            ratio=cfg["semidiscrete_reference"]["support_ratio"]
            for sol in ("MMS_A","MMS_B"):
                for dt in cfg["semidiscrete_rk2_dt"]:
                    code=f"{dt:.8f}".replace("0.","").rstrip("0");run=f"sd_{sol[-1].lower()}_{code}";ok=task(run,"semidiscrete_time",sol,16,ratio,float(dt),.01,11) and ok
        elif phase=="conttime":
            block=cfg["continuous_time"]
            for sol in ("MMS_A","MMS_B"):
                for dt in block["dt"]:
                    code=f"{dt:.8f}".replace("0.","").rstrip("0");run=f"ct_{sol[-1].lower()}_{code}";ok=task(run,"continuous_time",sol,32,block["support_ratio"],float(dt),block["t_final"],block["common_sample_count"]) and ok
        elif phase=="isolation":
            ratio=cfg["space"]["increasing_neighbor_path"][32]
            for sol in ("MMS_A","MMS_B"):
                for dt,code in ((6.25e-5,"6p25e5"),(3.125e-5,"3p125e5")):ok=task(f"isolate_{sol[-1].lower()}_{code}","space_dt_isolation",sol,32,ratio,dt,.02,21) and ok
            if ok:ok=select_space_dt(cfg)
        elif phase in ("space","fixed"):
            selection=json.loads((STAGE/"results/space_dt_selection.json").read_text());dt=selection["selected_dt"]
            for sol in ("MMS_A","MMS_B"):
                for n in (16,24,32,48):
                    ratio=cfg["space"]["increasing_neighbor_path"][n] if phase=="space" else cfg["space"]["fixed_ratio"]
                    ok=task(f"{phase}_{sol[-1].lower()}_n{n}","space_main" if phase=="space" else "fixed_ratio_diagnostic",sol,n,ratio,dt,.02,21) and ok
        elif phase=="determinism":
            selection=json.loads((STAGE/"results/space_dt_selection.json").read_text());space_dt=selection["selected_dt"];block=cfg["continuous_time"]
            for sol in ("MMS_A","MMS_B"):
                ok=task(f"repeat_time_{sol[-1].lower()}","deterministic_time_repeat",sol,32,block["support_ratio"],min(block["dt"]),.02,21) and ok
                ok=task(f"repeat_space_{sol[-1].lower()}","deterministic_space_repeat",sol,32,cfg["space"]["increasing_neighbor_path"][32],space_dt,.02,21) and ok
        elif phase=="n64":
            decision=json.loads((STAGE/"results/n64_decision.json").read_text())
            if decision["required"]:
                ratio=cfg["space"]["increasing_neighbor_path"][64];dt=json.loads((STAGE/"results/space_dt_selection.json").read_text())["selected_dt"]
                for sol in ("MMS_A","MMS_B"):
                    ok=task(f"n64_smoke_{sol[-1].lower()}","n64_smoke",sol,64,ratio,dt,20*dt,2) and ok
                    if ok:ok=task(f"space_{sol[-1].lower()}_n64","conditional_n64",sol,64,ratio,dt,.02,21) and ok
        if not ok:break
    print(json.dumps({"phase":args.phase,"status":"PASS" if ok else "FAIL"}));return 0 if ok else 1
if __name__=="__main__":raise SystemExit(main())
