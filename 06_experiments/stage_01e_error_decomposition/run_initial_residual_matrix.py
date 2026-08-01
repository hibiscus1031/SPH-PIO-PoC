"""Run the preregistered 210-case Stage 01E t=0 residual matrix."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path
import subprocess
import sys
import time

import yaml

PROJECT_ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(PROJECT_ROOT/"01_solver"))
ROOT=PROJECT_ROOT/"06_experiments"/"stage_01e_error_decomposition"; CONFIG=ROOT/"configs"/"preregistered_stage01e.yml"; OUTPUT=ROOT/"results"/"initial_residual_matrix.csv"
from benchmark_alignment.residual_decomposition import compute_initial_case  # noqa: E402


def tasks(cfg: dict) -> list[dict]:
    result=[]
    for family, ratios in cfg["static_matrix"]["support_families"].items():
        for resolution in cfg["static_matrix"]["resolutions"]:
            for layout in cfg["static_matrix"]["layouts"]:
                seeds=[cfg["static_matrix"]["regular_seed"]] if layout=="regular" else cfg["static_matrix"]["frozen_seeds"]
                for seed in seeds:
                    result.append({"case_id":f"{family}_n{resolution}_{layout}_s{seed}","support_family":family,"resolution":resolution,"support_ratio":float(ratios[resolution]),"layout":layout,"jitter_fraction":float(cfg["static_matrix"]["jitter_fractions"][layout]),"seed":seed})
    return result


def main() -> int:
    if Path(sys.prefix).resolve().name!="sph-pio-poc": raise SystemExit("requires sph-pio-poc environment")
    if OUTPUT.exists(): raise SystemExit("refusing to overwrite initial residual evidence")
    cfg=yaml.safe_load(CONFIG.read_text()); matrix=tasks(cfg)
    assert len(matrix)==int(cfg["static_matrix"]["expected_cases"])
    config_hash=hashlib.sha256(CONFIG.read_bytes()).hexdigest(); git_hash=subprocess.check_output(("git","rev-parse","HEAD"),cwd=PROJECT_ROOT,text=True).strip()
    rows=[]; started=time.perf_counter()
    for index,task in enumerate(matrix,1):
        tick=time.perf_counter(); row=compute_initial_case(**{k:task[k] for k in ("resolution","support_ratio","jitter_fraction","seed")},reference_density=float(cfg["physics"]["reference_density"]),sound_speed=float(cfg["physics"]["sound_speed"]),velocity_amplitude=float(cfg["physics"]["velocity_amplitude"]),viscosity=float(cfg["physics"]["physical_viscosity"]))
        row.update(case_id=task["case_id"],support_family=task["support_family"],layout=task["layout"],case_wall_seconds=time.perf_counter()-tick,config_sha256=config_hash,code_git_hash=git_hash)
        rows.append(row)
        if index%10==0 or index==len(matrix): print(f"completed {index}/{len(matrix)}",flush=True)
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    with OUTPUT.open("x",newline="",encoding="utf-8") as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator="\n"); writer.writeheader(); writer.writerows(rows)
    print(f"wrote {len(rows)} cases in {time.perf_counter()-started:.3f}s")
    return 0


if __name__=="__main__": raise SystemExit(main())
