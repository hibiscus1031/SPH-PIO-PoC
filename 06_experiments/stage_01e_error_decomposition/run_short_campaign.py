"""Serial Stage 01E parent that launches and reaps 21 short children."""

from __future__ import annotations

import csv,hashlib,json,os
from pathlib import Path
import subprocess,sys,time
import yaml

PROJECT_ROOT=Path(__file__).resolve().parents[2]; ROOT=PROJECT_ROOT/"06_experiments"/"stage_01e_error_decomposition"; CONFIG=ROOT/"configs"/"preregistered_stage01e.yml"; WORKER=ROOT/"stage01e_short_worker.py"; INDEX=ROOT/"results"/"short_campaign_index.csv"; LOGS=ROOT/"logs"
FIELDS=["run_id","pid","return_code","child_reclaimed","child_rss_after_reap_bytes","parent_rss_before_bytes","parent_rss_after_bytes","result_path","log_path","config_sha256","code_git_hash","wall_time_seconds"]


def rss(pid:int)->int:
    r=subprocess.run(("/bin/ps","-o","rss=","-p",str(pid)),capture_output=True,text=True,check=False); return int(r.stdout.strip())*1024 if r.stdout.strip() else 0


def run_ids(cfg:dict)->list[str]:
    result=["stage01e_short_regular"]
    for prefix in ("stage01e_short_j05_s","stage01e_short_j10_s"): result.extend(f"{prefix}{seed}" for seed in cfg["short_rollout"]["frozen_seeds"])
    return result


def main()->int:
    cfg=yaml.safe_load(CONFIG.read_text()); ids=run_ids(cfg); assert len(ids)==int(cfg["short_rollout"]["expected_trajectories"])
    if INDEX.exists(): raise SystemExit("refusing to overwrite short campaign index")
    INDEX.parent.mkdir(parents=True,exist_ok=True); LOGS.mkdir(parents=True,exist_ok=True); ok=True
    with INDEX.open("x",newline="",encoding="utf-8") as index:
        writer=csv.DictWriter(index,fieldnames=FIELDS,lineterminator="\n"); writer.writeheader()
        for number,run_id in enumerate(ids,1):
            log=LOGS/f"{run_id}.log"; result=ROOT/"results"/"short_summaries"/f"{run_id}.json"
            if log.exists() or result.exists(): raise RuntimeError("refusing to overwrite short evidence")
            before=rss(os.getpid()); started=time.perf_counter()
            with log.open("x",encoding="utf-8") as stream:
                child=subprocess.Popen([sys.executable,str(WORKER),"--run-id",run_id],cwd=PROJECT_ROOT,stdout=stream,stderr=subprocess.STDOUT,text=True); pid=child.pid; code=child.wait()
            child_after=rss(pid); after=rss(os.getpid()); reclaimed=child_after==0; ok=ok and code==0 and reclaimed and result.exists()
            writer.writerow({"run_id":run_id,"pid":pid,"return_code":code,"child_reclaimed":reclaimed,"child_rss_after_reap_bytes":child_after,"parent_rss_before_bytes":before,"parent_rss_after_bytes":after,"result_path":result.relative_to(PROJECT_ROOT).as_posix() if result.exists() else "","log_path":log.relative_to(PROJECT_ROOT).as_posix(),"config_sha256":hashlib.sha256(CONFIG.read_bytes()).hexdigest(),"code_git_hash":subprocess.check_output(("git","rev-parse","HEAD"),cwd=PROJECT_ROOT,text=True).strip(),"wall_time_seconds":time.perf_counter()-started}); index.flush(); print(f"completed {number}/{len(ids)} {run_id} code={code}",flush=True)
    print(json.dumps({"status":"PASS" if ok else "FAIL","children":len(ids)})); return 0 if ok else 1


if __name__=="__main__": raise SystemExit(main())
