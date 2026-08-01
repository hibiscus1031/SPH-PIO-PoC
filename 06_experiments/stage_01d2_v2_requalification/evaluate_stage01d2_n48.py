"""Pre-registered conditional N48 decision, before and after the smoke."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import statistics
import yaml

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "configs" / "preregistered_stage01d2_v2.yml"


def fitted_slope_ci_lower(dx: list[float], errors: list[float]) -> tuple[float, float]:
    x = [math.log(v) for v in dx]; y = [math.log(v) for v in errors]
    xm = statistics.mean(x); ym = statistics.mean(y)
    slope = sum((a-xm)*(b-ym) for a,b in zip(x,y)) / sum((a-xm)**2 for a in x)
    residual = [b - (ym + slope*(a-xm)) for a,b in zip(x,y)]
    se = math.sqrt(sum(v*v for v in residual) / max(1, len(x)-2) / sum((a-xm)**2 for a in x))
    return slope, slope - 12.706 * se


def primary_decision(cfg: dict) -> dict:
    ids = cfg["space_study"]["run_ids"]
    paths = [ROOT / "run_summaries" / f"{run}.json" for run in ids]
    complete = all(path.exists() for path in paths)
    rows = [json.loads(path.read_text()) for path in paths] if complete else []
    resources = complete and all(row["status"] == "PASS" and row["resource_policy_pass"] for row in rows)
    errors = [float(row["final_velocity_relative_l2"]) for row in rows] if resources else []
    monotone = bool(errors) and errors[0] > errors[1] > errors[2]
    slope, lower = fitted_slope_ci_lower([2/n for n in cfg["space_study"]["resolutions"]], errors) if resources and all(v > 0 for v in errors) else (math.nan, math.nan)
    trigger = resources and (not monotone or lower <= 0)
    n32_peak = int(rows[-1]["peak_rss_bytes"]) if rows else 0
    authorize = trigger and n32_peak < int(cfg["n48_policy"]["n32_peak_rss_limit_bytes"])
    return {"phase": "primary", "main_complete": complete, "main_resource_pass": resources, "velocity_errors": errors, "strictly_monotone": monotone, "fitted_slope": slope, "slope_95pct_ci_lower": lower, "n48_triggered": trigger, "n32_peak_rss_bytes": n32_peak, "n48_smoke_authorized": authorize, "decision": "RUN_N48_SMOKE" if authorize else "DO_NOT_RUN_N48"}


def smoke_decision(cfg: dict) -> dict:
    path = ROOT / "run_summaries" / f"{cfg['n48_policy']['smoke_run_id']}.json"
    if not path.exists():
        return {"phase": "smoke", "decision": "N48_SMOKE_EVIDENCE_MISSING", "n48_full_authorized": False}
    row = json.loads(path.read_text())
    projected = float(row["mean_step_time_seconds"]) * 1600
    authorize = row["status"] == "PASS" and int(row["peak_rss_bytes"]) < int(cfg["n48_policy"]["smoke_peak_rss_limit_bytes"]) and projected < float(cfg["n48_policy"]["projected_full_wall_limit_seconds"])
    return {"phase": "smoke", "smoke_status": row["status"], "smoke_peak_rss_bytes": row["peak_rss_bytes"], "projected_full_wall_seconds": projected, "n48_full_authorized": authorize, "decision": "RUN_N48_FULL" if authorize else "DO_NOT_RUN_N48_FULL"}


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--phase", choices=("primary", "smoke"), required=True); args = parser.parse_args()
    cfg = yaml.safe_load(CONFIG.read_text())
    result = primary_decision(cfg) if args.phase == "primary" else smoke_decision(cfg)
    path = ROOT / "results" / f"n48_{args.phase}_decision.json"
    if path.exists(): raise SystemExit("refusing to overwrite N48 decision")
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps(result, sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
