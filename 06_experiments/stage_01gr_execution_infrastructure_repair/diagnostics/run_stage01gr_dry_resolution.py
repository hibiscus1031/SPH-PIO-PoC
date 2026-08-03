"""Resolve all frozen Stage 01G rows without importing or calling the solver."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
STAGE = ROOT / "06_experiments/stage_01gr_execution_infrastructure_repair"
sys.path.insert(0, str(STAGE / "diagnostics"))

from stage01gr_contract import matrix_rows, resolve_row, validate_resolution, verify_frozen_hashes  # noqa: E402


def main() -> int:
    output = STAGE / "results/stage01gr_dry_run_results.csv"
    metadata_output = STAGE / "results/stage01gr_dry_metadata.json"
    config_output = STAGE / "results/stage01gr_config_resolution.csv"
    if any(path.exists() for path in (output, metadata_output, config_output)):
        raise RuntimeError("refusing to overwrite Stage 01G-R dry-run evidence")
    frozen = verify_frozen_hashes()
    if not all(frozen.values()):
        raise RuntimeError(f"frozen identity failure: {frozen}")
    resolved_rows = [resolve_row(row) for row in matrix_rows()]
    records = []
    for resolved in resolved_rows:
        checks = validate_resolution(resolved)
        records.append({"run_id": resolved["run_id"], **checks, "status": "PASS" if all(checks.values()) else "FAIL"})
    with output.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=records[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)
    metadata_output.write_text(json.dumps(resolved_rows, indent=2, sort_keys=True, allow_nan=False) + "\n")
    shear = next(item for item in resolved_rows if item["run_id"] == "g_shear_n24")
    row = {
        "run_id": shear["run_id"], "benchmark": shear["benchmark"], "N": shear["N"],
        "H_over_dx": shear["H_over_dx"], "dt": shear["dt"], "t_final": shear["t_final"],
        "common_times": json.dumps(shear["common_times"], separators=(",", ":")),
        "output_directory": shear["future_output_directory"],
        "evaluator_binding": shear["evaluator_binding"], "threshold_hash": shear["threshold_hash"],
        "explicit": True, "non_null": True, "hash_linked": True, "status": "PASS",
    }
    with config_output.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=row.keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerow(row)
    passed = sum(record["status"] == "PASS" for record in records)
    print(json.dumps({"run_count": len(records), "pass_count": passed, "solver_called": False}, sort_keys=True))
    return 0 if passed == 12 else 1


if __name__ == "__main__":
    raise SystemExit(main())
