"""Pure Stage 01G-R config, metadata, and provenance resolution contract."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[3]
STAGE = ROOT / "06_experiments/stage_01gr_execution_infrastructure_repair"
REPAIR_CONFIG = STAGE / "configs/stage01gr_repair.yml"
COMMON_METADATA = {
    "run_id", "benchmark", "N", "H_over_dx", "dt", "t_final",
    "domain_length", "rho0", "c_s", "config_sha256",
}
SHEAR_METADATA = {"nu", "U_s", "k_s", "claim"}
ACOUSTIC_METADATA = {"nu", "epsilon", "k_a", "claim"}
PROVENANCE_FIELDS = {
    "run_id", "config_sha256", "run_matrix_sha256", "metric_contract_sha256",
    "evaluator_manifest_sha256", "future_output_directory", "device", "dtype",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def repair_config() -> dict[str, Any]:
    return yaml.safe_load(REPAIR_CONFIG.read_text())


def matrix_rows() -> list[dict[str, str]]:
    cfg = repair_config()
    path = ROOT / cfg["frozen_inputs"]["matrix_path"]
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 12 or len({row["run_id"] for row in rows}) != 12:
        raise ValueError("frozen run matrix must contain 12 unique run IDs")
    return rows


def verify_frozen_hashes() -> dict[str, bool]:
    cfg = repair_config()["frozen_inputs"]
    evaluator_manifest = ROOT / cfg["evaluator_manifest_path"]
    return {
        "stage01g_config": sha256(ROOT / cfg["config_path"]) == cfg["config_sha256"],
        "stage01g_matrix": sha256(ROOT / cfg["matrix_path"]) == cfg["matrix_sha256"],
        "stage01g_metric_contract": sha256(ROOT / cfg["metric_contract_path"]) == cfg["metric_contract_sha256"],
        "stage01ge_evaluator_manifest_present": evaluator_manifest.is_file(),
    }


def resolve_row(row: dict[str, str]) -> dict[str, Any]:
    cfg = repair_config()
    frozen = cfg["frozen_inputs"]
    design = yaml.safe_load((ROOT / frozen["config_path"]).read_text())
    benchmark = row["benchmark"]
    if benchmark == "shear":
        problem = design["shear_wave"]
        common_times = list(problem["common_times"])
        metadata = {
            "run_id": row["run_id"], "benchmark": benchmark, "N": int(row["N"]),
            "H_over_dx": float(row["H_over_dx"]), "dt": float(row["dt"]),
            "t_final": float(row["t_final"]), "domain_length": 2.0,
            "rho0": float(problem["parameters"]["rho0"]),
            "c_s": float(problem["parameters"]["c_s"]),
            "config_sha256": frozen["config_sha256"],
            "nu": float(problem["parameters"]["nu"]), "U_s": float(problem["parameters"]["U_s"]),
            "k_s": 2.0 * 3.141592653589793,
            "claim": problem["claim"],
        }
    elif benchmark == "acoustic":
        problem = design["acoustic_wave"]
        common_times = list(problem["common_times"])
        metadata = {
            "run_id": row["run_id"], "benchmark": benchmark, "N": int(row["N"]),
            "H_over_dx": float(row["H_over_dx"]), "dt": float(row["dt"]),
            "t_final": float(row["t_final"]), "domain_length": 2.0,
            "rho0": float(problem["parameters"]["rho0"]),
            "c_s": float(problem["parameters"]["c_s"]),
            "config_sha256": frozen["config_sha256"],
            "nu": float(problem["parameters"]["nu"]), "epsilon": float(row["epsilon"]),
            "k_a": 3.141592653589793,
            "claim": problem["claim"],
        }
    else:
        raise ValueError(f"unknown benchmark {benchmark}")
    evaluator_manifest = ROOT / frozen["evaluator_manifest_path"]
    provenance = {
        "run_id": row["run_id"],
        "config_sha256": frozen["config_sha256"],
        "run_matrix_sha256": frozen["matrix_sha256"],
        "metric_contract_sha256": frozen["metric_contract_sha256"],
        "evaluator_manifest_sha256": sha256(evaluator_manifest),
        "future_output_directory": row["future_output_directory"],
        "device": cfg["explicit_runner_bindings"]["device"],
        "dtype": cfg["explicit_runner_bindings"]["dtype"],
    }
    return {
        "run_id": row["run_id"],
        "benchmark": benchmark,
        "N": int(row["N"]),
        "H_over_dx": float(row["H_over_dx"]),
        "dt": float(row["dt"]),
        "t_final": float(row["t_final"]),
        "common_times": common_times,
        "future_output_directory": row["future_output_directory"],
        "evaluator_binding": "stage01ge-evaluator-v1",
        "threshold_hash": frozen["config_sha256"],
        "metadata": metadata,
        "provenance": provenance,
    }


def validate_resolution(resolved: dict[str, Any]) -> dict[str, bool]:
    metadata = resolved["metadata"]
    benchmark = resolved["benchmark"]
    required_metadata = COMMON_METADATA | (SHEAR_METADATA if benchmark == "shear" else ACOUSTIC_METADATA)
    explicit = all(value is not None and value != "" for key, value in resolved.items() if key not in {"metadata", "provenance"})
    metadata_schema = set(metadata) == required_metadata and all(value is not None and value != "" for value in metadata.values())
    provenance_schema = set(resolved["provenance"]) == PROVENANCE_FIELDS and all(
        value is not None and value != "" for value in resolved["provenance"].values()
    )
    directory = resolved["future_output_directory"] == f"06_experiments/stage_01g_validation_execution/runs/{resolved['run_id']}"
    evaluator_schema = metadata_schema and metadata["config_sha256"] == resolved["threshold_hash"]
    hash_linked = all(len(resolved["provenance"][key]) == 64 for key in (
        "config_sha256", "run_matrix_sha256", "metric_contract_sha256", "evaluator_manifest_sha256"
    ))
    return {
        "config_resolve": explicit,
        "directory_resolve": directory,
        "metadata_schema": metadata_schema,
        "evaluator_schema": evaluator_schema,
        "provenance_schema": provenance_schema,
        "hash_linked": hash_linked,
    }
