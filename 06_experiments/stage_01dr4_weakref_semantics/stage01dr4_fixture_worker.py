"""One-process SPH-independent Stage 01D-R4 fixture worker."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOLVER_ROOT = PROJECT_ROOT / "01_solver"
if str(SOLVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SOLVER_ROOT))
EXPERIMENT_ROOT = PROJECT_ROOT / "06_experiments" / "stage_01dr4_weakref_semantics"
CONFIG_PATH = EXPERIMENT_ROOT / "configs" / "preregistered_weakref_semantics.yml"
RESULTS_ROOT = EXPERIMENT_ROOT / "results"

from resource_diagnostics.lifetime_gate_fixtures import run_lifetime_fixture  # noqa: E402


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: dict[str, object]) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path.relative_to(PROJECT_ROOT)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", choices=("A", "B", "C", "D"), required=True)
    parser.add_argument("--repeat", type=int, choices=(1, 2, 3), required=True)
    args = parser.parse_args()
    if Path(sys.prefix).resolve().name != "sph-pio-poc":
        raise SystemExit("R4 fixtures require sph-pio-poc")
    configuration = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    run_id = f"stage01dr4_fixture_{args.fixture.lower()}_r{args.repeat}"
    output = RESULTS_ROOT / "fixture_summaries" / f"{run_id}.json"
    failure = RESULTS_ROOT / "failures" / f"{run_id}.txt"
    summary: dict[str, object] = {
        "run_id": run_id,
        "repeat": args.repeat,
        "fixture": args.fixture,
        "pid": os.getpid(),
        "git_hash": subprocess.check_output(("git", "rev-parse", "HEAD"), cwd=PROJECT_ROOT, text=True).strip(),
        "config_sha256": _sha256(CONFIG_PATH),
        "status": "FAIL",
    }
    try:
        result = run_lifetime_fixture(
            args.fixture,
            steps=int(configuration["fixtures"]["steps"]),
        )
        summary.update(result)
        summary["status"] = "PASS" if result["classified_correctly"] else "FAIL"
    except BaseException as error:
        failure.parent.mkdir(parents=True, exist_ok=True)
        failure.write_text(
            "".join(traceback.format_exception(error)).replace(str(Path.home()), "<HOME>"),
            encoding="utf-8",
        )
        summary.update(
            failure_type=type(error).__name__,
            failure_message=str(error).replace(str(Path.home()), "<HOME>"),
            failure_path=failure.relative_to(PROJECT_ROOT).as_posix(),
        )
    _write(output, summary)
    print(json.dumps({"run_id": run_id, "status": summary["status"]}, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
