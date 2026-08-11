"""Freeze Stage 03D-R inputs and select the prospective audit subset before new results."""

from __future__ import annotations

import collections
import hashlib
import json
import math
from pathlib import Path
import struct
from typing import Any

import torch


HERE = Path(__file__).resolve()
STAGE03DR = HERE.parents[1]
STAGE03 = HERE.parents[3]
ROOT = HERE.parents[4]
STAGE03D = STAGE03 / "05_dynamic_solver_implementation/stage03d"
STAGE03C = STAGE03 / "05_dynamic_solver_implementation/stage03c"
CONTRACT = STAGE03DR / "freeze/stage03dr_attribution_contract_v0_1.yaml"
CONTRACT_HASH = "sha256:63ef93fe7af7c10ffb6a6e1d944003b5e3e85818f98bac6f6b1b9333a479c2d9"
FIXED = STAGE03D / "results/fixed_topology_adfd_results.json"
PREHISTORY = STAGE03D / "history_gradients/reference_prehistory_results.json"
MATRIX_OUTPUT = STAGE03DR / "failure_matrix/stage03d_complete_360_row_matrix.json"
SELECTED_OUTPUT = STAGE03DR / "freeze/selected_row_manifest.json"
INPUT_MANIFEST = STAGE03 / "10_manifests/stage03dr_input_freeze_manifest.json"


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def deterministic_direction(arm: str, case_id: str, seed: int, probe: str, shape: tuple[int, ...]) -> torch.Tensor:
    payload = ("stage03d" + arm + case_id + str(seed) + probe).encode("utf-8")
    values: list[float] = []
    counter = 0
    denominator = float(2**64 - 1)
    while len(values) < math.prod(shape):
        digest = hashlib.sha256(payload + struct.pack("<Q", counter)).digest()
        for offset in range(0, 32, 8):
            integer = int.from_bytes(digest[offset : offset + 8], "little", signed=False)
            values.append(2.0 * (integer / denominator) - 1.0)
        counter += 1
    vector = torch.tensor(values[: math.prod(shape)], dtype=torch.float64).reshape(shape)
    return vector / torch.linalg.vector_norm(vector)


def tensor_hash(value: torch.Tensor) -> str:
    digest = hashlib.sha256()
    digest.update(str(value.dtype).encode("ascii"))
    digest.update(str(tuple(value.shape)).encode("ascii"))
    digest.update(value.contiguous().numpy().tobytes())
    return "sha256:" + digest.hexdigest()


def direction_record(row: dict[str, Any]) -> dict[str, Any]:
    probe = row["probe"]
    shapes = {
        "initial_velocity": (64, 2),
        "initial_density": (64,),
        "initial_hidden_state": (64, 32),
        "historical_token": (64, 4, 10),
    }
    if probe in shapes:
        vector = deterministic_direction(row["arm"], row["case_id"], int(row["seed"]), probe, shapes[probe])
        return {"kind": "sha256_direction", "shape": list(shapes[probe]), "l2_norm": float(torch.linalg.vector_norm(vector)), "tensor_hash": tensor_hash(vector)}
    payload = f"{row['parameter_path']}|{row['tensor_index']}".encode("utf-8")
    return {"kind": "registered_scalar_basis", "basis_hash": "sha256:" + hashlib.sha256(payload).hexdigest()}


def decade(value: float) -> str:
    magnitude = abs(float(value))
    if magnitude == 0.0:
        return "ZERO"
    exponent = math.floor(math.log10(magnitude))
    return f"1e{exponent}"


def historical_failure_reason(row: dict[str, Any]) -> str:
    if row["pass"]:
        return "HISTORICAL_STABLE_WINDOW_PASS"
    topology = any(not repeat["topology_fixed"] for epsilon in row["epsilon_rows"] for repeat in epsilon["repeats"])
    mixed = any(not repeat["mixed_error_pass"] for epsilon in row["epsilon_rows"] for repeat in epsilon["repeats"] if repeat["topology_fixed"])
    if topology:
        return "HISTORICAL_TOPOLOGY_CHANGE_EXCLUDED"
    if mixed and not any(epsilon["pass"] for epsilon in row["epsilon_rows"]):
        return "ALL_EPSILON_MIXED_ERROR_GATE_FAILED"
    if mixed:
        return "MIXED_ERROR_AND_ADJACENT_STABILITY_GATES_FAILED"
    return "ADJACENT_FD_STABILITY_GATE_FAILED"


def matrix_row(source: dict[str, Any]) -> dict[str, Any]:
    row_id = f"{source['arm']}|{source['case_id']}|{int(source['seed'])}|K{int(source['horizon'])}|{source['probe']}"
    fd_values = [float(item["fd"]) for item in source["epsilon_rows"]]
    adjacent = [
        abs(left - right) / max(abs(left), abs(right), 1.0e-12)
        for left, right in zip(fd_values[:-1], fd_values[1:])
    ]
    result = {
        "row_id": row_id,
        "arm": source["arm"],
        "case_id": source["case_id"],
        "case_role": "MMS_WITH_SOURCE" if "DR1" in source["case_id"] else "SOURCE_FREE",
        "seed": int(source["seed"]),
        "horizon": int(source["horizon"]),
        "probe_type": source["probe"],
        "probe_group": "parameter" if source["parameter_path"] is not None else ("history" if source["probe"] in {"initial_hidden_state", "historical_token"} else "initial_state"),
        "parameter_path": source["parameter_path"],
        "tensor_index": source["tensor_index"],
        "direction": direction_record(source),
        "ad": float(source["ad"]),
        "ad_repeats": source["ad_repeats"],
        "fd_epsilons": [float(item["epsilon"]) for item in source["epsilon_rows"]],
        "fd_values": fd_values,
        "absolute_errors": [float(item["repeats"][0]["absolute_error"]) for item in source["epsilon_rows"]],
        "relative_errors": [float(item["repeats"][0]["relative_error"]) for item in source["epsilon_rows"]],
        "adjacent_fd_relative_changes": adjacent,
        "derivative_magnitude_decade": decade(source["ad"]),
        "graph_sequence_identity": all(repeat["topology_fixed"] for item in source["epsilon_rows"] for repeat in item["repeats"]),
        "deterministic_repeat": bool(source["deterministic_ad"] and all(item["deterministic"] for item in source["epsilon_rows"])),
        "structural_zero_status": source["classification"] == "DERIVATIVE_STRUCTURALLY_ZERO",
        "historical_stable_window_verdict": bool(source["pass"]),
        "historical_stable_windows": source["stable_windows"],
        "exact_historical_failure_reason": historical_failure_reason(source),
    }
    return result


def axis_counts(rows: list[dict[str, Any]], key_fields: tuple[str, ...]) -> dict[str, dict[str, int]]:
    counts: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
    for row in rows:
        key = "|".join(str(row[field]) for field in key_fields)
        counts[key]["total"] += 1
        counts[key]["pass" if row["historical_stable_window_verdict"] else "fail"] += 1
    return {key: dict(value) for key, value in sorted(counts.items())}


def selected_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cells: dict[tuple[str, str, int], list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        cells[(row["arm"], row["probe_type"], row["horizon"])].append(row)
    selected = []
    for cell, members in sorted(cells.items()):
        failed = [row for row in members if not row["historical_stable_window_verdict"]]
        pool = failed or members
        chosen = sorted(pool, key=lambda row: (row["case_id"], row["seed"], row["row_id"]))[0]
        selected.append({
            "arm": cell[0],
            "probe_type": cell[1],
            "horizon": cell[2],
            "row_id": chosen["row_id"],
            "case_id": chosen["case_id"],
            "seed": chosen["seed"],
            "selection_role": "historical_failure" if failed else "historical_pass_control",
            "historical_ad": chosen["ad"],
            "historical_verdict": chosen["historical_stable_window_verdict"],
            "parameter_path": chosen["parameter_path"],
            "tensor_index": chosen["tensor_index"],
            "direction": chosen["direction"],
        })
    return selected


def evidence_paths() -> list[Path]:
    paths = [
        STAGE03 / "09_reports/stage03d_final_report.md",
        STAGE03D / "contracts/dynamic_multistep_adfd_topology_contract_v0_1.yaml",
        FIXED,
        PREHISTORY,
        STAGE03D / "conservation_over_time/conservation_results.json",
        STAGE03D / "topology_event_scan/te1_dense_scan_results.json",
        STAGE03D / "topology_stage_replay/replay_results.json",
        STAGE03D / "event_side_gradients/event_side_gradient_results.json",
        STAGE03D / "event_jump_audit/event_force_jump_results.json",
        STAGE03D / "qualification/stage03d_qualification_summary.json",
        STAGE03 / "10_manifests/stage03d_input_freeze_manifest.json",
        STAGE03 / "10_manifests/stage03d_adfd_manifest.json",
        STAGE03 / "10_manifests/stage03d_topology_event_manifest.json",
        STAGE03 / "10_manifests/stage03d_final_manifest.json",
        STAGE03C / "contracts/dynamic_solver_implementation_contract_v0_1.yaml",
    ]
    for folder in ("arm_d1", "arm_d2", "arm_d3", "rk2_core", "temporal_history", "graph_rebuild", "pair_force_head", "tokenization", "reference_loader"):
        paths.extend((STAGE03C / folder).rglob("*.py"))
    paths.extend((STAGE03 / "04_reference_and_trajectory/stage03b/trajectory_records").glob("*.npz"))
    return sorted(set(paths), key=rel)


def main() -> None:
    if sha(CONTRACT) != CONTRACT_HASH:
        raise RuntimeError("Stage 03D-R attribution contract hash changed")
    fixed = json.loads(FIXED.read_text(encoding="utf-8"))
    prehistory = json.loads(PREHISTORY.read_text(encoding="utf-8"))
    rows = [matrix_row(source) for source in fixed["probe_rows"]]
    if len(rows) != 360 or sum(row["historical_stable_window_verdict"] for row in rows) != 216:
        raise RuntimeError("historical 360-row matrix does not match Stage 03D")
    summary = {
        "row_count": len(rows),
        "pass_count": sum(row["historical_stable_window_verdict"] for row in rows),
        "fail_count": sum(not row["historical_stable_window_verdict"] for row in rows),
        "axis_counts": {
            "arm": axis_counts(rows, ("arm",)),
            "horizon": axis_counts(rows, ("horizon",)),
            "probe": axis_counts(rows, ("arm", "probe_type")),
            "probe_group": axis_counts(rows, ("probe_group",)),
            "case_role": axis_counts(rows, ("case_role",)),
            "case": axis_counts(rows, ("case_id",)),
            "seed": axis_counts(rows, ("seed",)),
            "derivative_decade": axis_counts(rows, ("derivative_magnitude_decade",)),
        },
    }
    write_json(MATRIX_OUTPUT, {"schema_version": "sph-pio-poc.stage03dr.failure-matrix.v1", "source": {"path": rel(FIXED), "sha256": sha(FIXED)}, "summary": summary, "rows": rows})

    selected = selected_rows(rows)
    if len(selected) != 60:
        raise RuntimeError(f"selected cell count {len(selected)} != 60")
    selected_manifest = {
        "schema_version": "sph-pio-poc.stage03dr.selected-row-manifest.v1",
        "contract_hash": CONTRACT_HASH,
        "selection_frozen_before_extended_epsilon_decode": True,
        "selection_rule": "for each arm x probe_type x horizon, lexicographically first failed (case_id,seed,row_id), else first PASS control",
        "selected_count": len(selected),
        "historical_failure_selected_count": sum(row["selection_role"] == "historical_failure" for row in selected),
        "historical_control_selected_count": sum(row["selection_role"] == "historical_pass_control" for row in selected),
        "rows": selected,
    }
    write_json(SELECTED_OUTPUT, selected_manifest)

    evidence = [{"path": rel(path), "byte_count": path.stat().st_size, "sha256": sha(path)} for path in evidence_paths()]
    input_manifest = {
        "schema_version": "sph-pio-poc.stage03dr.input-freeze.v1",
        "stage": "Stage 03D-R",
        "authorization": "Stage 03D:DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED",
        "contract": {"path": rel(CONTRACT), "sha256": sha(CONTRACT), "immutable": True},
        "stage03d_failure_matrix": {"path": rel(MATRIX_OUTPUT), "sha256": sha(MATRIX_OUTPUT), "rows": 360, "failures": 144},
        "selected_row_manifest": {"path": rel(SELECTED_OUTPUT), "sha256": sha(SELECTED_OUTPUT), "rows": 60},
        "evidence": evidence,
        "reference_prehistory_historical_pass": sum(row["pass"] for row in prehistory["rows"]),
        "reference_prehistory_historical_total": len(prehistory["rows"]),
        "extended_fd_results_observed_before_selection": False,
        "historical_verdicts": {
            "Stage_01": "V2_QUALIFICATION_FAIL",
            "Stage_02_static_route": "TERMINATED",
            "Stage_03C": "DYNAMIC_RK2_HYBRID_IMPLEMENTATION_VERIFIED",
            "Stage_03D": "DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED",
            "Stage_03E_authorization": False,
        },
        "new_optimizer_steps": 0,
        "new_training_runs": 0,
        "pass": True,
    }
    write_json(INPUT_MANIFEST, input_manifest)
    print(json.dumps({"matrix": summary, "selected_manifest_sha256": sha(SELECTED_OUTPUT), "input_manifest_sha256": sha(INPUT_MANIFEST)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
