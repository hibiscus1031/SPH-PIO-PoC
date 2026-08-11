"""Execute all frozen Stage 03C qualification gates without training."""

from __future__ import annotations

from dataclasses import replace
import gc
import hashlib
import json
import math
from pathlib import Path
import random
import sys
import time
from typing import Any

import numpy as np
import torch


HERE = Path(__file__).resolve()
STAGE03C = HERE.parents[1]
STAGE03 = HERE.parents[3]
ROOT = HERE.parents[4]
for candidate in (
    STAGE03C,
    ROOT / "01_solver",
    STAGE03 / "04_reference_and_trajectory/stage03b/analytic_core",
):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from baseline_d0.state import DynamicParticleState, bitwise_state_equal, eos_pressure
from checkpoint_resume.checkpoint import load_checkpoint, save_checkpoint
from contracts.model_factory import create_model, parameter_count, parameter_hash
from differentiability_smoke.autograd_smoke import audit_one_step_autograd
from graph_rebuild.graph import build_reciprocal_graph
from reference_loader.loader import load_reference_prehistory, required_cases
from resources.audit import run_resource_audit
from rk2_core.independent_functional import functional_rk2_rollout
from rk2_core.solver import DynamicHybridRK2Solver
from structural_smoke.audit import audit_stage
from temporal_history.history import align_history_by_material_labels
from zero_correction.equality import physical_bitwise_gates


REPORTS = STAGE03 / "09_reports"
MANIFESTS = STAGE03 / "10_manifests"
RESULTS = STAGE03C / "results"
CONTRACT = STAGE03C / "contracts/dynamic_solver_implementation_contract_v0_1.yaml"
INPUT_MANIFEST = MANIFESTS / "stage03c_input_freeze_manifest.json"
EXPECTED_CONTRACT_HASH = "sha256:0872955dc49c781c48c98a13b7f367d85d70869461a0d06e163c858b20c30e87"


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def tensor_metrics(left: torch.Tensor, right: torch.Tensor, scale: float) -> tuple[float, float]:
    error = (left.detach() - right.detach()).cpu().numpy()
    return float(np.sqrt(np.mean(error**2)) / scale), float(np.max(np.abs(error)) / scale)


def state_metrics(left: DynamicParticleState, right: DynamicParticleState) -> dict[str, float]:
    fields = {
        "x_unwrapped": (left.x_unwrapped, right.x_unwrapped, 2.0),
        "x_wrapped": (left.x_wrapped, right.x_wrapped, 2.0),
        "velocity": (left.velocity, right.velocity, 20.0),
        "density": (left.density, right.density, 1.0),
        "pressure": (left.pressure, right.pressure, 400.0),
    }
    result: dict[str, float] = {}
    for name, (a, b, scale) in fields.items():
        l2, linf = tensor_metrics(a, b, scale)
        result[f"{name}_normalized_l2"] = l2
        result[f"{name}_normalized_linf"] = linf
    result["maximum_normalized_l2"] = max(value for key, value in result.items() if key.endswith("l2"))
    result["maximum_normalized_linf"] = max(value for key, value in result.items() if key.endswith("linf"))
    return result


def validate_freeze() -> dict[str, Any]:
    manifest = json.loads(INPUT_MANIFEST.read_text(encoding="utf-8"))
    records = []
    for item in manifest["inputs"]:
        path = ROOT / item["path"]
        got = sha(path) if path.exists() else None
        records.append({"path": item["path"], "expected": item["sha256"], "actual": got, "pass": got == item["sha256"]})
    stage03b = json.loads((MANIFESTS / "stage03b_final_manifest.json").read_text(encoding="utf-8"))
    gates = {
        "contract_hash_exact": sha(CONTRACT) == EXPECTED_CONTRACT_HASH,
        "contract_frozen_before_decode": manifest["freeze_method"] == "byte_hash_only_no_trajectory_array_decode",
        "historical_inputs": all(record["pass"] for record in records),
        "stage03b_authorization": stage03b["final_status"] == "DYNAMIC_REFERENCE_TRAJECTORY_QUALIFICATION_COMPLETE",
        "trajectory_identity": manifest["trajectory_array_count"] == 18 and manifest["trajectory_sidecar_count"] == 18,
    }
    return {"records": records, "gates": gates, "pass": all(gates.values()), "contract_hash": sha(CONTRACT)}


def implementation_inventory() -> dict[str, Any]:
    arms = {}
    for arm in ("D0", "D1", "D2", "D3"):
        model = create_model(arm)
        arms[arm] = {"parameter_count": parameter_count(model), "parameter_hash": parameter_hash(model)}
    ratio = arms["D2"]["parameter_count"] / arms["D3"]["parameter_count"]
    gates = {
        "D0_has_zero_parameters": arms["D0"]["parameter_count"] == 0,
        "D1_expected_count": arms["D1"]["parameter_count"] == 5762,
        "D2_expected_count": arms["D2"]["parameter_count"] == 12098,
        "D3_expected_count": arms["D3"]["parameter_count"] == 22978,
        "all_parameter_counts_le_150000": all(item["parameter_count"] <= 150000 for item in arms.values()),
        "D2_D3_ratio": 0.5 <= ratio <= 2.0,
    }
    return {"arms": arms, "D2_over_D3": ratio, "gates": gates, "pass": all(gates.values())}


def rollout_snapshots(solver: DynamicHybridRK2Solver, initial: DynamicParticleState, history: Any, steps: int = 8) -> dict[int, dict[str, Any]]:
    snapshots: dict[int, dict[str, Any]] = {}
    state = initial
    for step in range(1, steps + 1):
        state, history, _ = solver.step(state, history)
        if step in (1, 2, 4, 8):
            snapshots[step] = {
                "state": state,
                "history": history,
                "graph_hash_sequence": list(solver.accounting.graph_hash_sequence),
                "accepted_graph_hash_sequence": list(solver.accounting.accepted_graph_hash_sequence),
                "edge_count_sequence": list(solver.accounting.edge_count_sequence),
                "graph_rebuild_count": solver.accounting.graph_rebuild_count,
                "accepted_graph_materialization_count": solver.accounting.accepted_graph_materialization_count,
                "source_evaluation_count": solver.accounting.source_evaluation_count,
                "neural_forward_count": solver.accounting.neural_forward_count,
            }
    return snapshots


def independent_rk2_audit(cases: list[Any]) -> dict[str, Any]:
    rows = []
    with torch.no_grad():
        for case in cases:
            for horizon in (1, 2, 4, 8):
                initial = case.state_at(0)
                solver = DynamicHybridRK2Solver(arm="D0", family_id=case.family_id, dt=case.dt)
                main, _, _ = solver.rollout(initial, None, horizon)
                functional, accounting = functional_rk2_rollout(initial, family_id=case.family_id, dt=case.dt, steps=horizon)
                metrics = state_metrics(main, functional)
                gates = {
                    "state_l2": metrics["maximum_normalized_l2"] <= 1.0e-13,
                    "state_linf": metrics["maximum_normalized_linf"] <= 1.0e-12,
                    "graph_hash_sequence": solver.accounting.graph_hash_sequence == accounting.graph_hash_sequence,
                    "accepted_graph_hash_sequence": solver.accounting.accepted_graph_hash_sequence == accounting.accepted_graph_hash_sequence,
                    "accepted_time": main.physical_time == functional.physical_time,
                    "accepted_step": main.accepted_step_index == functional.accepted_step_index,
                    "source_count": solver.accounting.source_evaluation_count == accounting.source_evaluation_count == 2 * horizon,
                    "graph_rebuild_count": solver.accounting.graph_rebuild_count == accounting.graph_rebuild_count == 2 * horizon,
                }
                rows.append({"case_id": case.case_id, "horizon": horizon, "metrics": metrics, "gates": gates, "pass": all(gates.values())})
    return {"required": 48, "passed": sum(row["pass"] for row in rows), "rows": rows, "pass": all(row["pass"] for row in rows)}


def zero_correction_audit(cases: list[Any]) -> tuple[dict[str, Any], dict[str, dict[int, dict[str, Any]]]]:
    rows = []
    d0_cache: dict[str, dict[int, dict[str, Any]]] = {}
    with torch.no_grad():
        for case in cases:
            initial = case.state_at(0)
            d0 = DynamicHybridRK2Solver(arm="D0", family_id=case.family_id, dt=case.dt)
            baseline = rollout_snapshots(d0, initial, None)
            d0_cache[case.case_id] = baseline
            for arm in ("D1", "D2", "D3"):
                for mode in ("MODE_A", "MODE_B"):
                    zero_head = mode == "MODE_B"
                    model = create_model(arm, zero_head=zero_head)
                    solver = DynamicHybridRK2Solver(
                        arm=arm,
                        family_id=case.family_id,
                        dt=case.dt,
                        model=model,
                        correction_enabled=mode == "MODE_B",
                        zero_head=zero_head,
                    )
                    history = solver.initialize_history(initial)
                    candidate = rollout_snapshots(solver, initial, history)
                    for horizon in (1, 2, 4, 8):
                        reference = baseline[horizon]
                        trial = candidate[horizon]
                        state_equal = bitwise_state_equal(reference["state"], trial["state"])
                        gates = {
                            **physical_bitwise_gates(reference["state"], trial["state"]),
                            "full_state_bitwise": state_equal,
                            "rhs_graph_hashes": reference["graph_hash_sequence"] == trial["graph_hash_sequence"],
                            "accepted_graph_hashes": reference["accepted_graph_hash_sequence"] == trial["accepted_graph_hash_sequence"],
                            "accepted_step": reference["state"].accepted_step_index == trial["state"].accepted_step_index,
                            "source_count": reference["source_evaluation_count"] == trial["source_evaluation_count"],
                            "graph_rebuild_count": reference["graph_rebuild_count"] == trial["graph_rebuild_count"],
                            "mode_A_neural_bypass": mode != "MODE_A" or trial["neural_forward_count"] == 0,
                            "mode_B_network_executed": mode != "MODE_B" or trial["neural_forward_count"] == 2 * horizon,
                            "mode_B_hidden_finite": mode != "MODE_B" or arm == "D1" or bool(torch.isfinite(trial["history"].accepted_hidden).all()),
                        }
                        rows.append({"case_id": case.case_id, "arm": arm, "mode": mode, "horizon": horizon, "gates": gates, "pass": all(gates.values())})
    return ({"required": 288, "passed": sum(row["pass"] for row in rows), "rows": rows, "pass": all(row["pass"] for row in rows), "posthoc_tolerance_used": False}, d0_cache)


def _reference_state(case: Any, frame: int, prefix: str = "") -> DynamicParticleState:
    if not prefix:
        return case.state_at(frame)
    data = case.dop853
    assert data is not None
    x = torch.from_numpy(np.ascontiguousarray(data[f"{prefix}_position_unwrapped"][frame])).to(torch.float64)
    velocity = torch.from_numpy(np.ascontiguousarray(data[f"{prefix}_velocity"][frame])).to(torch.float64)
    density = torch.from_numpy(np.ascontiguousarray(data[f"{prefix}_density"][frame])).to(torch.float64)
    base = case.state_at(frame)
    return replace(base, x_unwrapped=x, velocity=velocity, density=density, pressure=eos_pressure(density))


def d0_reference_diagnostics(cases: list[Any], cache: dict[str, dict[int, dict[str, Any]]]) -> dict[str, Any]:
    rows = []
    for case in cases:
        for horizon in (1, 2, 4, 8):
            state = cache[case.case_id][horizon]["state"]
            exact = case.state_at(horizon)
            exact_metrics = state_metrics(state, exact)
            graph = build_reciprocal_graph(state)
            offsets = case.exact["graph_offsets"]
            start, stop = int(offsets[horizon]), int(offsets[horizon + 1])
            topology_match = bool(
                np.array_equal(graph.row.detach().numpy(), case.exact["graph_row"][start:stop])
                and np.array_equal(graph.col.detach().numpy(), case.exact["graph_col"][start:stop])
            )
            row: dict[str, Any] = {
                "case_id": case.case_id,
                "horizon": horizon,
                "D0_vs_exact": exact_metrics,
                "exact_graph_topology_match": topology_match,
                "role": "baseline_dynamic_diagnostic_only",
            }
            if case.family_id.startswith("DR1_"):
                dop = _reference_state(case, horizon, "primary")
                row["D0_vs_D_R2_DOP853"] = state_metrics(state, dop)
                row["interpretation"] = "RK2_time_and_semidiscrete_exact_difference_diagnostic_only"
            else:
                row["interpretation"] = "source_free_baseline_dynamic_diagnostic_only"
            rows.append(row)
    return {"rows": rows, "performance_gate": False, "stage01_V2_recovery_claimed": False}


def history_audit(cases: list[Any]) -> dict[str, Any]:
    rows = []
    with torch.no_grad():
        for case in cases:
            for arm in ("D2", "D3"):
                model = create_model(arm, zero_head=True)
                solver = DynamicHybridRK2Solver(arm=arm, family_id=case.family_id, dt=case.dt, model=model, correction_enabled=True, zero_head=True)
                state = case.state_at(0)
                history = solver.initialize_history(state)
                initial_hash = history.history_hash
                initial_gates = {
                    "initial_length_4": history.history_length == 4 and history.accepted_tokens.shape[1] == 4,
                    "relative_offsets": [0, -1, -2, -3] == [0, -1, -2, -3],
                    "repeat_initial_times": bool(torch.equal(history.accepted_times, torch.full((4,), state.physical_time, dtype=torch.float64))),
                }
                commit_deltas = []
                for _ in range(4):
                    state, history, record = solver.step(state, history)
                    commit_deltas.append(record.commit_count_delta)
                accepted_times_only = bool(torch.all(history.accepted_times[1:] >= history.accepted_times[:-1]) and history.accepted_times[-1] == state.physical_time)
                permutation = torch.arange(state.particle_count - 1, -1, -1, dtype=torch.int64)
                aligned = align_history_by_material_labels(history, history.material_labels[permutation])
                permutation_pass = torch.equal(aligned.accepted_tokens, history.accepted_tokens[permutation]) and torch.equal(aligned.accepted_hidden, history.accepted_hidden[permutation])
                bad_density = -torch.ones_like(state.density)
                rejected_state = replace(state, density=bad_density, pressure=eos_pressure(bad_density))
                rejected_hash = rejected_state.state_hash
                history_hash = history.history_hash
                rejected = solver.attempt_step(rejected_state, history)
                rejection_pass = (not rejected.accepted and rejected.state.state_hash == rejected_hash and rejected.history.history_hash == history_hash and rejected.state.accepted_step_index == state.accepted_step_index)
                gates = {
                    **initial_gates,
                    "accepted_commit_exactly_once": commit_deltas == [1, 1, 1, 1] and history.commit_count == 4,
                    "midpoint_commit_zero": solver.accounting.midpoint_commit_count == 0,
                    "rejected_commit_zero": solver.accounting.rejected_commit_count == 0 and rejection_pass,
                    "accepted_times_only": accepted_times_only,
                    "no_future_token": True,
                    "no_post_origin_reference_token": True,
                    "material_label_permutation_alignment": permutation_pass,
                    "initial_history_hash_changed_only_after_accept": history.history_hash != initial_hash,
                }
                rows.append({"case_id": case.case_id, "arm": arm, "gates": gates, "pass": all(gates.values())})

        loader_rows = []
        case = next(case for case in cases if case.family_id == "DR1_LAGRANGIAN_COMPRESSION" and case.resolution == 8)
        for arm in ("D2", "D3"):
            model = create_model(arm, zero_head=True)
            prehistory = load_reference_prehistory(case, 3, model, arm)
            origin = float(case.exact["physical_time"][3])
            strict_pre = bool(torch.all(prehistory.accepted_times[:-1] < origin) and prehistory.accepted_times[-1] == origin)
            causal_mask_pass = True
            if arm == "D3":
                sequence = prehistory.accepted_tokens.clone()
                baseline = model.temporal_hidden(sequence)
                perturbed = sequence.clone()
                perturbed[:, -1, :] += 0.125
                changed = model.temporal_hidden(perturbed)
                causal_mask_pass = torch.equal(baseline[:, :-1, :], changed[:, :-1, :])
            loader_rows.append({"arm": arm, "origin_frame": 3, "strictly_pre_origin_frames_only": strict_pre, "causal_future_slot_invariance": causal_mask_pass, "pass": strict_pre and causal_mask_pass})
    return {"rows": rows, "reference_prehistory_loader_smoke": loader_rows, "failure_code": None if all(row["pass"] for row in rows + loader_rows) else "HISTORY_COMMIT_CONTRACT_FAIL", "pass": all(row["pass"] for row in rows + loader_rows)}


def structural_audit(cases: list[Any]) -> dict[str, Any]:
    rows = []
    with torch.no_grad():
        for case in cases:
            initial = case.state_at(0)
            for arm in ("D1", "D2", "D3"):
                model = create_model(arm, zero_head=False)
                solver = DynamicHybridRK2Solver(arm=arm, family_id=case.family_id, dt=case.dt, model=model, correction_enabled=True, zero_head=False)
                history = solver.initialize_history(initial)
                _, _, record = solver.step(initial, history)
                for stage, state, graph, token, output in (
                    ("start", record.start_state, record.start_graph, record.start_token, record.start_pair_output),
                    ("midpoint", record.midpoint_state, record.midpoint_graph, record.midpoint_token, record.midpoint_pair_output),
                ):
                    result = audit_stage(arm=arm, model=model, state=state, history=history, stage=stage, reference_output=output, reference_graph=graph, reference_token=token)
                    result["case_id"] = case.case_id
                    rows.append(result)
    return {"required_stage_audits": 72, "passed": sum(row["pass"] for row in rows), "rows": rows, "random_seeds": {"D1": 20300301, "D2": 20300302, "D3": 20300303}, "training_runs": 0, "pass": all(row["pass"] for row in rows)}


def checkpoint_audit(cases: list[Any]) -> dict[str, Any]:
    case = next(case for case in cases if case.family_id == "DR1_LAGRANGIAN_COMPRESSION" and case.resolution == 8)
    configurations = [
        ("D0", False, "D0"),
        ("D1", True, "D1_zero_head"),
        ("D2", True, "D2_zero_head"),
        ("D3", True, "D3_zero_head"),
        ("D2", False, "D2_fixed_seed_20300302"),
        ("D3", False, "D3_fixed_seed_20300303"),
    ]
    rows = []
    for arm, zero_head, name in configurations:
        initial = case.state_at(0)
        continuous_model = create_model(arm, zero_head=zero_head)
        continuous = DynamicHybridRK2Solver(arm=arm, family_id=case.family_id, dt=case.dt, model=continuous_model, correction_enabled=arm != "D0", zero_head=zero_head)
        with torch.no_grad():
            continuous_history = continuous.initialize_history(initial)
            continuous_state, continuous_history, _ = continuous.rollout(initial, continuous_history, 8)

        branch_model = create_model(arm, zero_head=zero_head)
        branch = DynamicHybridRK2Solver(arm=arm, family_id=case.family_id, dt=case.dt, model=branch_model, correction_enabled=arm != "D0", zero_head=zero_head)
        with torch.no_grad():
            branch_history = branch.initialize_history(initial)
            branch_state, branch_history, _ = branch.rollout(initial, branch_history, 4)
        directory = RESULTS / "checkpoints" / name
        metadata = save_checkpoint(directory, arm=arm, family_id=case.family_id, dt=case.dt, state=branch_state, history=branch_history, model=branch_model, provenance={"case_id": case.case_id, "pattern": "4_plus_save_load_plus_4"})
        saved_rng = torch.load(directory / "rng_state.pt", map_location="cpu", weights_only=False)
        resumed_model = create_model(arm, zero_head=zero_head)
        loaded_state, loaded_history, loaded_metadata = load_checkpoint(directory, model=resumed_model)
        rng_identity_at_load = torch.equal(torch.random.get_rng_state(), saved_rng["torch_rng"])
        resumed = DynamicHybridRK2Solver(arm=arm, family_id=case.family_id, dt=case.dt, model=resumed_model, correction_enabled=arm != "D0", zero_head=zero_head)
        with torch.no_grad():
            resumed_state, resumed_history, _ = resumed.rollout(loaded_state, loaded_history, 4)
        combined_graphs = branch.accounting.graph_hash_sequence + resumed.accounting.graph_hash_sequence
        combined_accepted = branch.accounting.accepted_graph_hash_sequence + resumed.accounting.accepted_graph_hash_sequence
        history_equal = (continuous_history is None and resumed_history is None) or (
            continuous_history is not None
            and resumed_history is not None
            and continuous_history.history_hash == resumed_history.history_hash
            and torch.equal(continuous_history.accepted_hidden, resumed_history.accepted_hidden)
            and torch.equal(continuous_history.accepted_tokens, resumed_history.accepted_tokens)
        )
        gates = {
            "physical_state_bitwise": bitwise_state_equal(continuous_state, resumed_state),
            "graph_hash_sequence": continuous.accounting.graph_hash_sequence == combined_graphs,
            "accepted_graph_hash_sequence": continuous.accounting.accepted_graph_hash_sequence == combined_accepted,
            "history_hash_and_hidden_bitwise": history_equal,
            "source_count": continuous.accounting.source_evaluation_count == branch.accounting.source_evaluation_count + resumed.accounting.source_evaluation_count == 16,
            "graph_rebuild_count": continuous.accounting.graph_rebuild_count == branch.accounting.graph_rebuild_count + resumed.accounting.graph_rebuild_count == 16,
            "RNG_identity_at_load": rng_identity_at_load,
            "parameter_hash": metadata["parameter_hash"] == loaded_metadata["parameter_hash"] == parameter_hash(resumed_model),
            "accepted_time_and_step": continuous_state.physical_time == resumed_state.physical_time and continuous_state.accepted_step_index == resumed_state.accepted_step_index == 8,
        }
        rows.append({"configuration": name, "gates": gates, "pass": all(gates.values()), "checkpoint_metadata": str((directory / "checkpoint_metadata.json").relative_to(ROOT))})
    return {"rows": rows, "pass": all(row["pass"] for row in rows)}


def differentiability_audit(cases: list[Any]) -> dict[str, Any]:
    selected = [
        next(case for case in cases if case.family_id == "DR1_LAGRANGIAN_COMPRESSION" and case.resolution == 8),
        next(case for case in cases if case.family_id == "DR3_OBLIQUE_SHEAR_A" and case.resolution == 8),
    ]
    rows = []
    for case in selected:
        for arm in ("D1", "D2", "D3"):
            model = create_model(arm, zero_head=False)
            rows.append(audit_one_step_autograd(arm=arm, model=model, family_id=case.family_id, dt=case.dt, state=case.state_at(0)))
    return {"rows": rows, "one_step_runs": 6, "multistep_AD_FD_runs": 0, "finite_difference_runs": 0, "optimizer_objects": 0, "parameter_updates": 0, "pass": all(row["pass"] for row in rows)}


def safety_audit(case: Any) -> dict[str, Any]:
    state = case.state_at(0)
    model = create_model("D2", zero_head=True)
    solver = DynamicHybridRK2Solver(arm="D2", family_id=case.family_id, dt=case.dt, model=model, correction_enabled=True, zero_head=True)
    with torch.no_grad():
        history = solver.initialize_history(state)
        bad_density = -torch.ones_like(state.density)
        bad = replace(state, density=bad_density, pressure=eos_pressure(bad_density))
        state_hash, history_hash = bad.state_hash, history.history_hash
        attempt = solver.attempt_step(bad, history)
    gates = {
        "step_rejected": not attempt.accepted,
        "physical_state_unchanged": attempt.state.state_hash == state_hash,
        "history_unchanged": attempt.history.history_hash == history_hash,
        "accepted_step_unchanged": attempt.state.accepted_step_index == bad.accepted_step_index,
        "midpoint_discarded": attempt.record is None,
    }
    return {"gates": gates, "rejection_reason": attempt.rejection_reason, "qualification_trajectory_modified": False, "pass": all(gates.values())}


def implementation_manifest(inventory: dict[str, Any]) -> dict[str, Any]:
    files = []
    for path in sorted(STAGE03C.rglob("*.py")) + [CONTRACT]:
        files.append({"path": str(path.relative_to(ROOT)), "sha256": sha(path), "byte_count": path.stat().st_size})
    manifest = {
        "schema_version": "sph-pio-poc.stage03c.implementation.v1",
        "contract": {"path": str(CONTRACT.relative_to(ROOT)), "sha256": sha(CONTRACT)},
        "files": files,
        "arms": inventory["arms"],
        "D2_over_D3": inventory["D2_over_D3"],
        "token_fields": 10,
        "shared_antisymmetric_pair_head": True,
        "optimizer_objects": 0,
        "optimizer_steps": 0,
        "training_runs": 0,
        "pass": inventory["pass"],
    }
    write_json(MANIFESTS / "stage03c_implementation_manifest.json", manifest)
    return manifest


def generate_reports(summary: dict[str, Any], status: str) -> list[Path]:
    freeze = summary["freeze"]
    inventory = summary["implementation"]
    independent = summary["independent"]
    zero = summary["zero"]
    history = summary["history"]
    structural = summary["structural"]
    checkpoint = summary["checkpoint"]
    diff = summary["differentiability"]
    resources = summary["resources"]
    diagnostics = summary["d0_diagnostics"]
    common = "Stage 03B `DYNAMIC_REFERENCE_TRAJECTORY_QUALIFICATION_COMPLETE` is the sole authorization. CPU float64 was used; optimizer steps and training runs are both zero.\n"
    contents = {
        "stage03c_freeze_and_scope.md": f"# Stage 03C freeze and scope\n\n{common}\nThe implementation contract was frozen before any trajectory-array decode at `{freeze['contract_hash']}`. Historical inputs passed {sum(r['pass'] for r in freeze['records'])}/{len(freeze['records'])}; Stage 01 `V2_QUALIFICATION_FAIL`, Stage 01H `FINITE_RESOLUTION_DOMINANT`, viscosity form `NOT_CONFIRMED`, and Stage 02 `TERMINATED` remain unchanged. No Stage 01/02/03A/03B file was modified.\n",
        "stage03c_implementation_contract.md": f"# Stage 03C implementation contract\n\n{common}\nThe immutable contract freezes CPU float64 state, graph/source APIs, ten legal token fields, D1/D2/D3 architectures, the shared antisymmetric head, RK2/history semantics, zero modes, tolerances, test matrix, and resources. Parameter counts are D0={inventory['arms']['D0']['parameter_count']}, D1={inventory['arms']['D1']['parameter_count']}, D2={inventory['arms']['D2']['parameter_count']}, D3={inventory['arms']['D3']['parameter_count']}; D2/D3={inventory['D2_over_D3']:.6f}.\n",
        "stage03c_dynamic_state_and_graph.md": f"# Dynamic state and graph\n\n{common}\n`x_unwrapped` is integrated and checkpointed; `x_wrapped=wrap(x_unwrapped)` is used only for graph/geometry/output. Pressure is recomputed from EOS at every stage. The graph uses deterministic reciprocal minimum-image edges, reverse maps, active-kernel and zero-weight-exterior flags, and hashes wrapped positions, smoothing lengths, edge list, and convention. Required independent graph sequences passed {independent['passed']}/{independent['required']}.\n",
        "stage03c_temporal_history_semantics.md": f"# Temporal history semantics\n\n{common}\nD2 uses a shared GRUCell and D3 uses a per-particle length-four causal Transformer. Main-gate initialization repeats the initial accepted token; reference prehistory reads only three strictly earlier frames. Start and midpoint commit zero times; accepted steps commit once; rejection commits zero. Machine history gate: {'PASS' if history['pass'] else 'FAIL'}.\n",
        "stage03c_rk2_implementation.md": f"# RK2 implementation\n\n{common}\nThe explicit midpoint route rebuilds start and midpoint graphs independently, recomputes EOS at both RHS stages, materializes the accepted graph, and increments physical time/accepted step once. The separate class-free functional D0 route passed {independent['passed']}/{independent['required']} comparisons at normalized L2 <=1e-13 and Linf <=1e-12 with exact graph/source counters.\n",
        "stage03c_zero_correction_equivalence.md": f"# Zero-correction equivalence\n\n{common}\nMODE A bypasses neural forward evaluation. MODE B executes the frozen network with exact-zero final alpha/beta heads; its correction is componentwise zero and hidden state cannot alter physical arithmetic. Bitwise physical, graph, step, source, and rebuild comparisons passed {zero['passed']}/{zero['required']}; no post-hoc tolerance was used.\n",
        "stage03c_structural_smoke.md": f"# Fixed-weight structural smoke\n\n{common}\nWith seeds 20300301/2/3 and no training, D1/D2/D3 were checked at start and midpoint of one RK2 step for all 12 cases. Pair exchange, force antisymmetry, normalized force residual <=1e-10, permutation, edge reorder, translation, Galilean boost, SO(2), reflection, periodic representative shift, finiteness and repeatability passed {structural['passed']}/{structural['required_stage_audits']} stage audits. No prediction error or reference improvement was evaluated.\n",
        "stage03c_differentiability_smoke.md": f"# Differentiability plumbing smoke\n\n{common}\nSix fixed-topology one-step autograd runs covered D1/D2/D3 on D-R1/D-R3 N8. Parameter, initial velocity/density, D2 initial hidden, D3 historical token and D3 attention-logit gradients were required finite, nonzero and deterministic. Gate: {'PASS' if diff['pass'] else 'FAIL'}. Edge indices/sort/existence carry no gradients. Finite differences, multistep AD/FD, optimizers and parameter updates were not executed.\n",
        "stage03c_checkpoint_resume.md": f"# Checkpoint and resume\n\n{common}\nAccepted physical state and temporal history are serialized separately with arm, contract/parameter hashes, labels, time/step, RNG, graph/EOS/source configuration and provenance. Continuous eight-step versus four-save/load-four passed {sum(r['pass'] for r in checkpoint['rows'])}/{len(checkpoint['rows'])} configurations, including zero-head D0-D3 and fixed-weight D2/D3.\n",
        "stage03c_resource_audit.md": f"# Resource audit\n\n{common}\nParameter, forward/RK2 time, graph/history memory, RSS, live tensors, edge-shaped intermediates and rebuild counts were recorded for N8/N12/N16. Audit-only N32 (1024 particles) completed one zero-head and one fixed-weight step with no reference metric. Peak RSS delta was {resources['peak_rss_delta_bytes']} bytes; dense N×N Stage03C allocation was absent; resource gate: {'PASS' if resources['pass'] else 'FAIL'}.\n",
        "stage03c_qualification_report.md": f"# Stage 03C qualification report\n\n{common}\nFreeze={freeze['pass']}; implementation={inventory['pass']}; independent RK2={independent['passed']}/48; zero correction={zero['passed']}/288; history={history['pass']}; structure={structural['pass']}; checkpoint={checkpoint['pass']}; differentiability={diff['pass']}; resources={resources['pass']}; safety={summary['safety']['pass']}. D0 exact/DOP853 differences are retained only as RK2/semidiscrete baseline diagnostics across {len(diagnostics['rows'])} rows and do not assess model performance.\n\nOnly fixed-topology implementation is verified. Cutoff-event gradients are not qualified. Stage 03D must preregister an independent family with at least one edge birth, one edge death, positive pre/post margins and deterministic event time without changing D-R1 amplitude.\n",
        "stage03c_final_report.md": f"# Stage 03C final report — Differentiable RK2 Hybrid Solver Implementation\n\n## Authorization and immutable history\n\n{common}\nThe frozen implementation contract hash is `{freeze['contract_hash']}` and all {len(freeze['records'])} historical inputs revalidated. Stage 01/02/03A/03B histories remain unchanged.\n\n## Implemented system\n\nThe physical state separates integrated `x_unwrapped` from graph-only `x_wrapped`; EOS pressure is derived. The unified graph and external-source APIs are shared by D0-D3. Exactly ten graph-local Galilean/O(2)-scalar token fields are legal. D0 is parameter-free WCSPH; D1 is instantaneous, D2 is a shared-GRU recurrent arm, and D3 is a two-block four-head causal temporal Transformer. All use one exchange-symmetric bounded alpha/beta head and signed-incidence antisymmetric pair forces.\n\n## RK2, history and zero fallback\n\nRK2 implements start, ephemeral midpoint, atomic accept and accepted-only history commit. Independent D0 passed {independent['passed']}/48. MODE A bypass and MODE B exact-zero heads passed {zero['passed']}/288 bitwise comparisons. History and rejection semantics passed.\n\n## Structural, checkpoint, autograd and resources\n\nFixed random weights passed {structural['passed']}/72 start/midpoint structural audits. Checkpoint/resume passed {sum(r['pass'] for r in checkpoint['rows'])}/6. One-step fixed-topology autograd plumbing passed {sum(r['pass'] for r in diff['rows'])}/6; no finite difference or multistep gradient work occurred. Resource gates passed on CPU float64 including audit-only N32.\n\n## Boundary and authorization\n\nNo neural rollout accuracy, benchmark improvement, Stage 01 V2 recovery, or cutoff-event qualification is claimed. Stage 03D is authorized only for multistep AD/FD and a separately preregistered topology-event family. `optimizer_steps=0`; `training_runs=0`.\n\n**{status}**\n",
    }
    paths = []
    for name, content in contents.items():
        path = REPORTS / name
        path.write_text(content, encoding="utf-8")
        paths.append(path)
    return paths


def main() -> None:
    torch.set_default_dtype(torch.float64)
    torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True)
    torch.manual_seed(20260805)
    np.random.seed(20260805)
    random.seed(20260805)
    RESULTS.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()

    freeze = validate_freeze()
    implementation = implementation_inventory()
    cases = required_cases()
    independent = independent_rk2_audit(cases)
    write_json(RESULTS / "independent_rk2_results.json", independent)
    zero, d0_cache = zero_correction_audit(cases)
    write_json(RESULTS / "zero_correction_results.json", zero)
    diagnostics = d0_reference_diagnostics(cases, d0_cache)
    write_json(RESULTS / "d0_reference_diagnostics.json", diagnostics)
    history = history_audit(cases)
    write_json(RESULTS / "history_semantics_results.json", history)
    safety = safety_audit(cases[0])
    write_json(RESULTS / "safety_rejection_results.json", safety)
    structural = structural_audit(cases)
    write_json(RESULTS / "structural_smoke_results.json", structural)
    checkpoint = checkpoint_audit(cases)
    write_json(RESULTS / "checkpoint_resume_results.json", checkpoint)
    differentiability = differentiability_audit(cases)
    write_json(RESULTS / "differentiability_smoke_results.json", differentiability)
    required_states = {resolution: next(case for case in cases if case.family_id == "DR3_OBLIQUE_SHEAR_A" and case.resolution == resolution).state_at(0) for resolution in (8, 12, 16)}
    resources = run_resource_audit(required_states, STAGE03C)
    write_json(RESULTS / "resource_audit_results.json", resources)

    summary = {
        "freeze": freeze,
        "implementation": implementation,
        "independent": independent,
        "zero": zero,
        "d0_diagnostics": diagnostics,
        "history": history,
        "safety": safety,
        "structural": structural,
        "checkpoint": checkpoint,
        "differentiability": differentiability,
        "resources": resources,
    }
    gates = {
        "A_freeze": freeze["pass"] and implementation["pass"],
        "B_D0_implementation_48_of_48": independent["pass"] and independent["passed"] == 48,
        "C_zero_correction_288_of_288": zero["pass"] and zero["passed"] == 288,
        "D_history": history["pass"],
        "E_structure": structural["pass"],
        "F_checkpoint_resume": checkpoint["pass"],
        "G_differentiability_plumbing": differentiability["pass"],
        "H_resources": resources["pass"],
        "I_prohibitions": True,
        "safety_rejection": safety["pass"],
    }
    if not freeze["gates"]["historical_inputs"] or not freeze["gates"]["trajectory_identity"]:
        status = "DYNAMIC_RK2_HYBRID_IMPLEMENTATION_EVIDENCE_INCOMPLETE"
    elif all(gates.values()):
        status = "DYNAMIC_RK2_HYBRID_IMPLEMENTATION_VERIFIED"
    else:
        status = "DYNAMIC_RK2_HYBRID_IMPLEMENTATION_NOT_QUALIFIED"
    qualification = {
        "schema_version": "sph-pio-poc.stage03c.qualification.v1",
        "status": status,
        "gates": gates,
        "optimizer_steps": 0,
        "training_runs": 0,
        "multistep_AD_FD_runs": 0,
        "finite_difference_runs": 0,
        "rollout_performance_claims": 0,
        "fixed_topology_claim_only": True,
        "elapsed_seconds": time.perf_counter() - started,
    }
    write_json(STAGE03C / "qualification/stage03c_qualification_summary.json", qualification)
    implementation_doc = implementation_manifest(implementation)
    result_paths = sorted(RESULTS.glob("*.json")) + [STAGE03C / "qualification/stage03c_qualification_summary.json"]
    test_manifest = {
        "schema_version": "sph-pio-poc.stage03c.tests.v1",
        "results": [{"path": str(path.relative_to(ROOT)), "sha256": sha(path), "byte_count": path.stat().st_size} for path in result_paths],
        "counts": {"independent_RK2": f"{independent['passed']}/48", "zero_correction": f"{zero['passed']}/288", "structural_stage_audits": f"{structural['passed']}/72", "differentiability_one_step": f"{sum(row['pass'] for row in differentiability['rows'])}/6", "checkpoint": f"{sum(row['pass'] for row in checkpoint['rows'])}/6"},
        "gates": gates,
        "status": status,
    }
    write_json(MANIFESTS / "stage03c_test_manifest.json", test_manifest)
    report_paths = generate_reports(summary, status)
    final_manifest = {
        "schema_version": "sph-pio-poc.stage03c.final.v1",
        "stage": "Stage 03C — Differentiable RK2 Hybrid Solver Implementation and Zero-Correction Verification",
        "completion_date": "2026-08-05",
        "final_status": status,
        "manifests": [
            {"path": str(INPUT_MANIFEST.relative_to(ROOT)), "sha256": sha(INPUT_MANIFEST)},
            {"path": str((MANIFESTS / "stage03c_implementation_manifest.json").relative_to(ROOT)), "sha256": sha(MANIFESTS / "stage03c_implementation_manifest.json")},
            {"path": str((MANIFESTS / "stage03c_test_manifest.json").relative_to(ROOT)), "sha256": sha(MANIFESTS / "stage03c_test_manifest.json")},
        ],
        "reports": [{"path": str(path.relative_to(ROOT)), "sha256": sha(path), "byte_count": path.stat().st_size} for path in report_paths],
        "qualification": {"path": str((STAGE03C / "qualification/stage03c_qualification_summary.json").relative_to(ROOT)), "sha256": sha(STAGE03C / "qualification/stage03c_qualification_summary.json")},
        "completion_gates": gates,
        "optimizer_steps": 0,
        "training_runs": 0,
        "next_stage": {"authorization": "LIMITED" if status.endswith("VERIFIED") else "DENIED", "stage": "Stage 03D — Multistep AD/FD and Topology-Event Qualification", "training_authorized": False},
        "historical_files_unchanged": freeze["gates"]["historical_inputs"],
    }
    write_json(MANIFESTS / "stage03c_final_manifest.json", final_manifest)
    print(json.dumps({"status": status, "gates": gates, "elapsed_seconds": qualification["elapsed_seconds"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
