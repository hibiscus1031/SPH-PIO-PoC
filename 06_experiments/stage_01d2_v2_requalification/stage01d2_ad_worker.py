"""Run exactly one preregistered Stage 01D2 AD/FD case."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOLVER_ROOT = PROJECT_ROOT / "01_solver"
sys.path.insert(0, str(SOLVER_ROOT))
ROOT = PROJECT_ROOT / "06_experiments" / "stage_01d2_v2_requalification"
CONFIG = ROOT / "configs" / "preregistered_stage01d2_v2.yml"
OUTPUT = ROOT / "results" / "ad_cases"

from dynamic_solver.native_autograd import dynamic_autograd_case  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parameter", required=True)
    parser.add_argument("--steps", required=True, type=int)
    args = parser.parse_args()
    if Path(sys.prefix).resolve().name != "sph-pio-poc":
        raise SystemExit("Stage 01D2 requires the sph-pio-poc environment")
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    ad = cfg["autograd_regression"]
    if args.parameter not in ad["parameters"] or args.steps not in ad["steps"]:
        raise SystemExit("case is not preregistered")
    path = OUTPUT / f"{args.parameter}_steps{args.steps}.json"
    failure = OUTPUT / f"{args.parameter}_steps{args.steps}.failure.txt"
    if path.exists() or failure.exists():
        raise SystemExit("refusing to overwrite AD evidence")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    try:
        row = dynamic_autograd_case(
            parameter_name=args.parameter,
            parameter_value=float(ad["parameter_values"][args.parameter]),
            finite_difference_step=float(ad["finite_difference_step"]),
            steps=args.steps,
        )
        row.update(
            schema_version="sph-pio-poc.stage01d2.ad.v1",
            pid=os.getpid(),
            wall_time_seconds=time.perf_counter() - started,
            config_sha256=hashlib.sha256(CONFIG.read_bytes()).hexdigest(),
            code_git_hash=subprocess.check_output(("git", "rev-parse", "HEAD"), cwd=PROJECT_ROOT, text=True).strip(),
            stage01c_baseline_regression_scope="frozen_identity_and_current_20_case_matrix",
        )
        with path.open("x", encoding="utf-8") as stream:
            json.dump(row, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
        print(json.dumps({"status": row["status"], "result_path": path.relative_to(PROJECT_ROOT).as_posix()}))
        return 0 if row["status"] == "PASS" else 1
    except Exception as error:
        failure.write_text("".join(traceback.format_exception(error)).replace(str(Path.home()), "<HOME>"), encoding="utf-8")
        raise


if __name__ == "__main__":
    raise SystemExit(main())
