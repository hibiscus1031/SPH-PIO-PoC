"""Persist Stage 01C and full-dynamic native-PyTorch AD regressions."""

from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOLVER_ROOT = PROJECT_ROOT / "01_solver"
if str(SOLVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SOLVER_ROOT))

from dynamic_solver.native_autograd import (  # noqa: E402
    run_dynamic_autograd_matrix,
)
from structure_preserving.native_autograd_ops import (  # noqa: E402
    run_native_autograd_matrix,
)


CONFIG_PATH = (
    PROJECT_ROOT
    / "06_experiments"
    / "stage_01d_fixed_physics_tgv"
    / "configs"
    / "preregistered_primary_tgv.yml"
)
RESULTS_DIR = (
    PROJECT_ROOT
    / "06_experiments"
    / "stage_01d_fixed_physics_tgv"
    / "results"
)


def _write_rows(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError("cannot write an empty AD regression")
    if path.exists():
        raise FileExistsError(f"refusing to overwrite AD evidence: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=RESULTS_DIR,
    )
    args = parser.parse_args()
    output_paths = (
        args.results_dir / "dynamic_autograd_fd.csv",
        args.results_dir / "stage01c_autograd_regression.csv",
    )
    existing = [str(path) for path in output_paths if path.exists()]
    if existing:
        raise FileExistsError(
            "refusing to overwrite AD evidence: " + ", ".join(existing)
        )
    config_hash = hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest()
    git_hash = subprocess.check_output(
        ("git", "rev-parse", "HEAD"),
        cwd=PROJECT_ROOT,
        text=True,
    ).strip()

    dynamic_rows = [
        {
            **row,
            "git_hash": git_hash,
            "config_sha256": config_hash,
        }
        for row in run_dynamic_autograd_matrix()
    ]
    stage01c_rows = [
        {
            **row,
            "regression_context": "stage01d_no_regression_check",
            "git_hash": git_hash,
            "stage01d_config_sha256": config_hash,
        }
        for row in run_native_autograd_matrix()
    ]
    _write_rows(
        output_paths[0],
        dynamic_rows,
    )
    _write_rows(
        output_paths[1],
        stage01c_rows,
    )
    dynamic_pass = sum(row["status"] == "PASS" for row in dynamic_rows)
    stage01c_pass = sum(row["status"] == "PASS" for row in stage01c_rows)
    print(f"dynamic_ad_pass={dynamic_pass}/{len(dynamic_rows)}")
    print(f"stage01c_ad_pass={stage01c_pass}/{len(stage01c_rows)}")
    print(f"config_sha256={config_hash}")
    print(f"git_hash={git_hash}")
    return 0 if (
        dynamic_pass == len(dynamic_rows)
        and stage01c_pass == len(stage01c_rows)
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
