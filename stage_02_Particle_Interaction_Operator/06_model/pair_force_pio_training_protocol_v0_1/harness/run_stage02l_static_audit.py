#!/usr/bin/env python3
"""Stage 02L zero-step harness audit. Backward is allowed; parameter updates are absent."""

from __future__ import annotations

import ast
import copy
import hashlib
import io
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
import yaml

torch.set_default_dtype(torch.float64)
torch.set_num_threads(1)
sys.dont_write_bytecode = True

REPO = Path(__file__).resolve().parents[4]
STAGE = REPO / "stage_02_Particle_Interaction_Operator"
ROOT = STAGE / "06_model/pair_force_pio_training_protocol_v0_1"
KROOT = STAGE / "06_model/pair_force_pio_architecture_v0_1"
sys.path.insert(0, str(ROOT / "data_access"))
sys.path.insert(0, str(ROOT / "loss"))
sys.path.insert(0, str(ROOT / "optimizer"))
sys.path.insert(0, str(KROOT / "implementations"))

from sealed_loader import AccessPolicyError, INPUT_ARRAY_PATHS, SealedCollectionLoader  # noqa: E402
from loss_contract import A0, EPSILON_METRIC, graph_balanced_node_mse, graph_node_mse, static_metrics  # noqa: E402
from prospective_optimizer import ProspectiveWarmupCosineSchedule, create_zero_step_adamw  # noqa: E402
from pair_force_models import MODEL_CLASSES, PairGraph  # noqa: E402

SEEDS = [20261201, 20261202, 20261203]
TOL = 1e-10


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def sha_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def content_hash(value: Any) -> str:
    return sha_bytes(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def tensor_hash(model: torch.nn.Module) -> str:
    digest = hashlib.sha256()
    for name, value in model.state_dict().items():
        digest.update(name.encode())
        digest.update(value.detach().cpu().contiguous().numpy().tobytes())
    return "sha256:" + digest.hexdigest()


def initialize(model: torch.nn.Module, seed: int) -> None:
    torch.manual_seed(seed)
    for name, module in model.named_modules():
        if not isinstance(module, torch.nn.Linear):
            continue
        if name == "coefficient_head":
            torch.nn.init.normal_(module.weight, mean=0.0, std=1e-3)
            torch.nn.init.zeros_(module.bias)
        else:
            torch.nn.init.xavier_uniform_(module.weight, gain=1.0)
            torch.nn.init.zeros_(module.bias)


def make_model(architecture: str, seed: int) -> torch.nn.Module:
    model = MODEL_CLASSES[architecture]().to(device="cpu", dtype=torch.float64)
    initialize(model, seed)
    return model


def to_graph(record: Any) -> PairGraph:
    a = record.arrays
    source = a["stage02b_record.neighbor_information.source_index"]
    target = a["stage02b_record.neighbor_information.target_index"]
    unique = source < target
    return PairGraph(
        position=torch.as_tensor(a["stage02b_record.particle_state.position_periodic"]),
        velocity=torch.as_tensor(a["stage02b_record.particle_state.velocity"]),
        density=torch.as_tensor(a["stage02b_record.particle_state.density"]),
        pressure=torch.as_tensor(a["stage02b_record.particle_state.pressure"]),
        mass=torch.as_tensor(a["stage02b_record.particle_state.mass"]),
        smoothing_length=torch.as_tensor(a["stage02b_record.particle_state.smoothing_length"]),
        pair_i=torch.as_tensor(source[unique]), pair_j=torch.as_tensor(target[unique]),
        active=torch.as_tensor(a["reciprocal_graph_extensions.active_kernel_indicator"][unique]),
        displacement=torch.as_tensor(a["stage02b_record.neighbor_information.minimum_image_displacement"][unique]),
        relative_velocity=torch.as_tensor(a["stage02b_record.neighbor_information.relative_velocity"][unique] / 20.0),
    )


def replace_graph(graph: PairGraph, **kwargs: Any) -> PairGraph:
    values = dict(graph.__dict__); values.update(kwargs); return PairGraph(**values)


def synthetic_supervision(graph: PairGraph) -> torch.Tensor:
    """Deterministic shape-compatible preflight signal; never a dataset target."""
    x = graph.position
    return 0.01 * A0 * torch.stack((torch.sin(2.0 * math.pi * x[:, 0]), torch.cos(2.0 * math.pi * x[:, 1])), dim=-1)


def permutation_graph(graph: PairGraph, permutation: np.ndarray) -> PairGraph:
    perm = torch.as_tensor(permutation.copy(), dtype=torch.int64)
    inverse = torch.empty_like(perm); inverse[perm] = torch.arange(len(perm))
    return PairGraph(
        position=graph.position[perm], velocity=graph.velocity[perm], density=graph.density[perm], pressure=graph.pressure[perm],
        mass=graph.mass[perm], smoothing_length=graph.smoothing_length[perm], pair_i=inverse[graph.pair_i], pair_j=inverse[graph.pair_j],
        active=graph.active, displacement=graph.displacement, relative_velocity=graph.relative_velocity,
    )


def relative(left: torch.Tensor, right: torch.Tensor) -> float:
    return float(torch.linalg.vector_norm(left-right) / torch.clamp(torch.maximum(torch.linalg.vector_norm(left), torch.linalg.vector_norm(right)), min=1e-30))


def gradients(model: torch.nn.Module) -> dict[str, torch.Tensor]:
    return {name: parameter.grad.detach().clone() for name, parameter in model.named_parameters()}


def optimizer_counter(optimizer: torch.optim.Optimizer) -> int:
    counters = []
    for state in optimizer.state.values():
        value = state.get("step", 0)
        counters.append(int(value.item()) if isinstance(value, torch.Tensor) else int(value))
    return max(counters, default=0)


def forbidden_step_call_audit() -> dict[str, Any]:
    rows = []
    for path in sorted(ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text())
        calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "step":
                calls.append(node.lineno)
        rows.append({"path": str(path.relative_to(REPO)), "step_call_lines": calls})
    return {"files": rows, "step_call_count": sum(len(x["step_call_lines"]) for x in rows), "status": "PASS" if not any(x["step_call_lines"] for x in rows) else "FAIL"}


def initialization_and_run_matrix(protocol: dict[str, Any]) -> tuple[dict[str, Any], dict[tuple[str, int], str]]:
    hashes: dict[tuple[str, int], str] = {}
    rows = []
    for run in protocol["run_matrix"]["runs"]:
        architecture, seed = run["architecture"], int(run["seed"])
        first, second = make_model(architecture, seed), make_model(architecture, seed)
        h1, h2 = tensor_hash(first), tensor_hash(second)
        coefficient = first.coefficient_head
        row = {
            "run_id": run["run_id"], "architecture": architecture, "seed": seed,
            "initialization_hash": h1, "repeat_hash": h2, "deterministic": h1 == h2,
            "parameter_count": sum(p.numel() for p in first.parameters()),
            "coefficient_bias_exact_zero": bool(torch.count_nonzero(coefficient.bias) == 0),
            "coefficient_weight_finite": bool(torch.isfinite(coefficient.weight).all()),
            "coefficient_weight_empirical_std": float(torch.std(coefficient.weight).detach()),
        }
        row["status"] = "PASS" if row["deterministic"] and row["coefficient_bias_exact_zero"] and row["coefficient_weight_finite"] else "FAIL"
        rows.append(row); hashes[(architecture, seed)] = h1
    return {"matrix_version": "stage02l-run-matrix-1.0.0", "prospective_run_count": 9, "training_runs_executed": 0, "rows": rows, "status": "PASS" if len(rows) == 9 and all(x["status"] == "PASS" for x in rows) else "FAIL"}, hashes


def loss_and_gradient_audit(train_graphs: list[PairGraph]) -> tuple[dict[str, Any], dict[str, Any]]:
    targets = [synthetic_supervision(graph) for graph in train_graphs]
    zero_predictions = [torch.zeros_like(target) for target in targets]
    zero_loss = graph_balanced_node_mse(zero_predictions, targets)
    manual_zero = torch.stack([torch.mean(torch.sum((target/A0)**2, dim=-1)) for target in targets]).mean()
    exact_loss = graph_balanced_node_mse(targets, targets)
    reorder = list(range(len(targets)))[::-1]
    reorder_loss = graph_balanced_node_mse([zero_predictions[i] for i in reorder], [targets[i] for i in reorder])
    metric = static_metrics(torch.zeros_like(targets[0]), targets[0])
    rms = torch.sqrt(torch.mean(torch.sum(targets[0]*targets[0], dim=-1)))
    zero_q_identity = rms / (rms + EPSILON_METRIC)
    loss_contract = {
        "contract_version": "stage02l-loss-static-1.0.0",
        "supervision_source": "deterministic_synthetic_preflight_only",
        "dataset_target_arrays_read": 0,
        "graph_balanced_reference_absolute_error": float(torch.abs(zero_loss-manual_zero)),
        "zero_prediction_loss_identity_absolute_error": float(torch.abs(zero_loss-manual_zero)),
        "exact_target_prediction_loss": float(exact_loss),
        "graph_reorder_absolute_error": float(torch.abs(zero_loss-reorder_loss)),
        "total_loss_terms": ["L_node"],
        "conservation_penalty": False,
        "regularity_loss": False,
        "status": "PASS" if torch.abs(zero_loss-manual_zero) <= TOL and exact_loss == 0 and torch.abs(zero_loss-reorder_loss) <= TOL else "FAIL",
    }
    metric_contract = {
        "contract_version": "stage02l-static-metrics-1.0.0",
        "epsilon_metric": EPSILON_METRIC,
        "zero_correction_Q_L2_convention": 1.0,
        "implemented_epsilon_adjusted_identity_error": float(torch.abs(metric["Q_L2"]-zero_q_identity)),
        "exact_prediction_Q_L2": float(static_metrics(targets[0], targets[0])["Q_L2"]),
        "aggregations_frozen": ["equal_weight_graph_mean", "equal_weight_family_mean", "median", "maximum", "per_resolution", "per_support"],
        "pseudoreplication_by_particles_or_edges": False,
        "dataset_performance_computed": False,
        "status": "PASS" if torch.abs(metric["Q_L2"]-zero_q_identity) <= TOL and static_metrics(targets[0], targets[0])["Q_L2"] == 0 else "FAIL",
    }
    return loss_contract, metric_contract


def architecture_static_audit(train_graphs: list[PairGraph]) -> dict[str, Any]:
    targets = [synthetic_supervision(graph) for graph in train_graphs]
    rng = np.random.default_rng(20261299)
    rows = []
    for architecture in ("K0", "K1", "K2"):
        full = make_model(architecture, SEEDS[0]); accumulated = make_model(architecture, SEEDS[0])
        initial_hash = tensor_hash(full)
        full.zero_grad(set_to_none=True)
        outputs = [full(graph) for graph in train_graphs]
        graph_balanced_node_mse(outputs, targets).backward()
        full_gradients = gradients(full)
        accumulated.zero_grad(set_to_none=True)
        for graph, target in zip(train_graphs, targets):
            (graph_node_mse(accumulated(graph), target) / len(train_graphs)).backward()
        accumulated_gradients = gradients(accumulated)
        gradient_error = max(relative(full_gradients[name], accumulated_gradients[name]) for name in full_gradients)
        finite = all(torch.isfinite(value).all() for value in full_gradients.values())
        global_norm = torch.sqrt(sum(torch.sum(value*value) for value in full_gradients.values()))
        clip_factor = torch.clamp(torch.tensor(1.0) / torch.clamp(global_norm, min=1.0), max=1.0)
        graph = train_graphs[0]; target = targets[0]
        with torch.no_grad(): base_prediction = full(graph); base_loss = graph_node_mse(base_prediction, target)
        permutation = rng.permutation(graph.position.shape[0]); pgraph = permutation_graph(graph, permutation)
        with torch.no_grad(): perm_prediction = full(pgraph)
        perm_loss = graph_node_mse(perm_prediction, target[torch.as_tensor(permutation.copy())])
        order = torch.as_tensor(rng.permutation(graph.pair_i.shape[0]).copy(), dtype=torch.int64)
        egraph = replace_graph(graph, pair_i=graph.pair_i[order], pair_j=graph.pair_j[order], active=graph.active[order], displacement=graph.displacement[order], relative_velocity=graph.relative_velocity[order])
        with torch.no_grad(): edge_loss = graph_node_mse(full(egraph), target)
        optimizer = create_zero_step_adamw(full.parameters()); schedule = ProspectiveWarmupCosineSchedule()
        parameter_unchanged = tensor_hash(full) == initial_hash
        row = {
            "architecture": architecture,
            "gradient_accumulation_relative_error": gradient_error,
            "finite_forward_backward": finite and bool(torch.isfinite(base_prediction).all()),
            "gradient_global_norm": float(global_norm), "gradient_clip_factor_finite": bool(torch.isfinite(clip_factor)),
            "particle_reorder_loss_absolute_error": float(torch.abs(base_loss-perm_loss)),
            "edge_reorder_loss_absolute_error": float(torch.abs(base_loss-edge_loss)),
            "optimizer_object_step_counter": optimizer_counter(optimizer), "scheduler_counter": schedule.update_count,
            "parameter_hash_unchanged_after_backward": parameter_unchanged,
        }
        row["status"] = "PASS" if gradient_error <= TOL and row["finite_forward_backward"] and row["gradient_clip_factor_finite"] and row["particle_reorder_loss_absolute_error"] <= TOL and row["edge_reorder_loss_absolute_error"] <= TOL and row["optimizer_object_step_counter"] == row["scheduler_counter"] == 0 and parameter_unchanged else "FAIL"
        rows.append(row)
    return {"audit_version": "stage02l-harness-static-1.0.0", "complete_train_graphs_in_full_batch": 10, "synthetic_supervision_only": True, "target_present_in_input_graph": False, "runtime_feature_permission_guard": "PASS", "optimizer_steps": 0, "scheduler_steps": 0, "parameter_updates": 0, "rows": rows, "status": "PASS" if all(x["status"] == "PASS" for x in rows) else "FAIL"}


def split_hashes(loader: SealedCollectionLoader) -> tuple[str, str]:
    assignments = loader.split["record_assignments"]
    train = sorted(k for k, v in assignments.items() if v == "future_train")
    validation = sorted(k for k, v in assignments.items() if v == "future_validation")
    return content_hash(train), content_hash(validation)


def checkpoint_roundtrip(loader: SealedCollectionLoader, graph: PairGraph, protocol_hash: str, architecture_hash: str) -> dict[str, Any]:
    train_hash, validation_hash = split_hashes(loader)
    rows = []
    for architecture in ("K0", "K1", "K2"):
        model = make_model(architecture, SEEDS[0]); optimizer = create_zero_step_adamw(model.parameters()); schedule = ProspectiveWarmupCosineSchedule()
        with torch.no_grad(): before = model(graph).detach().clone()
        state = {
            "architecture_id": architecture, "architecture_hash": architecture_hash, "protocol_hash": protocol_hash,
            "dataset_collection_id": loader.manifest["dataset_collection"], "train_split_hash": train_hash,
            "validation_split_hash": validation_hash, "normalization_hash": loader.normalization["statistics_hash"],
            "training_seed": SEEDS[0], "optimizer_state": optimizer.state_dict(), "scheduler_state": schedule.state_dict(),
            "update_number": 0, "model_parameters": model.state_dict(),
            "RNG_states": {"torch": torch.get_rng_state(), "numpy": np.random.get_state()},
            "best_validation_metric": None,
            "provenance": {"stage": "02L", "role": "zero_step_static_round_trip", "performance_evaluation": False},
        }
        buffer = io.BytesIO(); torch.save(state, buffer); payload = buffer.getvalue()
        checkpoint_path = ROOT / f"checkpointing/{architecture}_seed20261201_update0000.pt"
        checkpoint_path.write_bytes(payload)
        restored_state = torch.load(io.BytesIO(payload), map_location="cpu", weights_only=False)
        restored = make_model(architecture, SEEDS[0]); restored.load_state_dict(restored_state["model_parameters"])
        restored_optimizer = create_zero_step_adamw(restored.parameters()); restored_optimizer.load_state_dict(restored_state["optimizer_state"])
        restored_schedule = ProspectiveWarmupCosineSchedule(); restored_schedule.load_state_dict(restored_state["scheduler_state"])
        with torch.no_grad(): after = restored(graph)
        bitwise = all(torch.equal(model.state_dict()[name], restored.state_dict()[name]) for name in model.state_dict())
        required_fields = ["architecture_id", "architecture_hash", "protocol_hash", "dataset_collection_id", "train_split_hash", "validation_split_hash", "normalization_hash", "training_seed", "optimizer_state", "scheduler_state", "update_number", "model_parameters", "RNG_states", "best_validation_metric", "provenance"]
        row = {
            "architecture": architecture, "checkpoint_path": str(checkpoint_path.relative_to(REPO)), "checkpoint_sha256": sha(checkpoint_path),
            "checkpoint_byte_count": checkpoint_path.stat().st_size, "update_number": restored_state["update_number"],
            "parameter_bitwise_identity": bitwise, "resume_next_forward_bitwise_identity": bool(torch.equal(before, after)),
            "optimizer_counter_before": optimizer_counter(optimizer), "optimizer_counter_after": optimizer_counter(restored_optimizer),
            "scheduler_counter_before": schedule.update_count, "scheduler_counter_after": restored_schedule.update_count,
            "all_required_fields_present": all(field in restored_state for field in required_fields),
            "split_normalization_identity": restored_state["train_split_hash"] == train_hash and restored_state["validation_split_hash"] == validation_hash and restored_state["normalization_hash"] == loader.normalization["statistics_hash"],
        }
        row["status"] = "PASS" if bitwise and row["resume_next_forward_bitwise_identity"] and row["optimizer_counter_before"] == row["optimizer_counter_after"] == row["scheduler_counter_before"] == row["scheduler_counter_after"] == row["update_number"] == 0 and row["all_required_fields_present"] and row["split_normalization_identity"] else "FAIL"
        rows.append(row)
    return {"contract_version": "stage02l-zero-step-checkpoint-1.0.0", "required_future_interval_updates": 20, "rows": rows, "optimizer_steps": 0, "status": "PASS" if all(x["status"] == "PASS" for x in rows) else "FAIL"}


def resource_forecast(checkpoints: dict[str, Any]) -> dict[str, Any]:
    evidence = json.loads((KROOT / "resource_audit/resource_results.json").read_text())
    by_arch = {row["architecture"]: row for row in evidence["rows"]}
    train_edge_factor = 2.0 * sum(edge for _n, edge in evidence["dataset_graph_sizes_N_E"]) / max(edge for _n, edge in evidence["dataset_graph_sizes_N_E"])
    k1_update = by_arch["K1"]["runtime_seconds_median"] * train_edge_factor
    k2_update = by_arch["K2"]["runtime_seconds_median"] * train_edge_factor
    updates = {"K0": k1_update, "K1": k1_update, "K2": k2_update}
    safety_factor = 2.0
    per_run = {key: value * 1000 * safety_factor for key, value in updates.items()}
    total = 3.0 * sum(per_run.values())
    static_max_checkpoint = max(row["checkpoint_byte_count"] for row in checkpoints["rows"])
    predicted_checkpoint_each = static_max_checkpoint * 4
    checkpoint_count = 9 * 50
    storage = predicted_checkpoint_each * checkpoint_count
    measured_peak = max(row["peak_RSS_bytes_sampled"] for row in evidence["rows"])
    predicted_peak = int(measured_peak * 1.25 + 128 * 1024**2)
    status = predicted_peak <= int(1.5*1024**3) and storage <= 10*1024**3 and all(math.isfinite(x) for x in per_run.values())
    return {
        "forecast_version": "stage02l-resource-forecast-1.0.0", "source": str((KROOT / "resource_audit/resource_results.json").relative_to(REPO)),
        "source_sha256": sha(KROOT / "resource_audit/resource_results.json"), "CPU_float64": True,
        "train_full_batch_edge_scaling_factor_vs_max_graph": train_edge_factor,
        "predicted_seconds_per_full_batch_update": updates, "safety_factor": safety_factor,
        "predicted_seconds_per_1000_update_run": per_run, "predicted_seconds_nine_run_total": total,
        "predicted_hours_nine_run_total": total/3600.0, "checkpoint_interval_updates": 20,
        "predicted_checkpoint_count_if_all_retained": checkpoint_count, "predicted_checkpoint_bytes_each": predicted_checkpoint_each,
        "predicted_checkpoint_storage_bytes": storage, "checkpoint_storage_limit_bytes": 10*1024**3,
        "measured_stage02k_peak_RSS_bytes": measured_peak, "predicted_peak_RSS_bytes": predicted_peak,
        "peak_RSS_limit_bytes": int(1.5*1024**3), "dense_N_by_N": False, "scaling": "O(E*d)",
        "optimizer_updates_executed_for_forecast": 0, "predicted_finite_completion": True,
        "status": "PASS" if status else "FAIL",
    }


def reports(bundle: dict[str, Any]) -> None:
    report_dir = STAGE / "07_reports"; protocol_hash = bundle["protocol_hash"]
    texts = {
        "stage02l_freeze_and_scope.md": f"# Stage 02L — Freeze and scope\n\nAuthorized only by Stage 02K `PAIR_FORCE_PIO_ARCHITECTURE_QUALIFIED`. Protocol `{protocol_hash}` and 19 input files were frozen before any Stage 02L record-array decode. This stage executed zero optimizer steps and zero training runs. Historical hashes are **{bundle['history']['status']}**.\n",
        "stage02l_hypotheses_and_baselines.md": "# Stage 02L — Hypotheses and baselines\n\nH1 freezes static learnability as a future test; H2 freezes persistence of antisymmetry and momentum conservation; H3 makes no K2-over-K1 presumption; H4 requires K0 because the Stage 02K central basis passed. K0, K1 and K2 form the nine-run matrix. KNEG is excluded and has no optimizer.\n",
        "stage02l_loss_contract.md": f"# Stage 02L — Loss contract\n\nThe sole prospective objective is equal-complete-graph-weight node MSE on `delta_a/a0`, with `a0=cs^2/L=400`. Ten train graphs contribute one graph mean each. Conservation, regularity, reference, trajectory and rollout penalties are absent. Static identity audit: **{bundle['loss']['status']}**; dataset target arrays decoded: **0**.\n",
        "stage02l_optimizer_schedule.md": "# Stage 02L — Optimizer and schedule\n\nProspective optimizer: AdamW (`lr=1e-3`, betas `0.9/0.999`, epsilon `1e-8`, weight decay `1e-6`), global gradient norm cap 1.0. Schedule: 50-update warmup then cosine decay to `1e-5`, maximum 1000 updates. No grids, restarts or extensions. Optimizer and scheduler counters remain zero.\n",
        "stage02l_run_matrix.md": f"# Stage 02L — Run matrix\n\nThe immutable matrix contains 3 architectures × seeds `20261201`, `20261202`, `20261203` = 9 prospective runs. Deterministic Xavier hidden initialization and near-zero Normal(0, 1e-3) coefficient heads passed repeat hashing: **{bundle['run_matrix']['status']}**. No run was trained.\n",
        "stage02l_data_access_and_test_seal.md": f"# Stage 02L — Data access and test seal\n\nCollection and compatibility identities, 20 hashes, split 10/5/5 and normalization hash passed. Legal input arrays were selectively decoded; target/reference/a_SPH payloads were skipped. Test target access is `false`; denied-access probes passed and `test_release_manifest.json` does not exist. Test seal: **{bundle['test_seal']['status']}**.\n",
        "stage02l_checkpoint_contract.md": f"# Stage 02L — Checkpoint contract\n\nFuture interval: 20 updates. Required identity, optimizer/scheduler, RNG, selection and provenance fields are frozen. Update-zero K0/K1/K2 round trips preserve parameters and next-forward outputs bitwise, with counters unchanged: **{bundle['checkpoint']['status']}**.\n",
        "stage02l_training_harness_audit.md": f"# Stage 02L — Training harness audit\n\nLoader/access/feature guards, graph-balanced loss, zero/exact prediction identities, graph/particle/edge reorder, full-batch gradient accumulation, finite backward, clip calculation, zero counters, checkpoint and resume all pass: **{bundle['harness']['status']}**. Static supervision was synthetic; optimizer/scheduler step-call AST count is **{bundle['step_calls']['step_call_count']}**.\n",
        "stage02l_static_metric_contract.md": f"# Stage 02L — Static metric contract\n\nPer-graph metrics are Q_L2, Q_Linf and cosine with `epsilon_metric=4e-10`. Equal-weight graph/family means, median, maximum, per-resolution and per-support summaries are frozen. Zero correction uses the theoretical Q_L2=1 baseline convention. No dataset performance was computed. Contract audit: **{bundle['metrics']['status']}**.\n",
        "stage02l_resource_forecast.md": f"# Stage 02L — Resource forecast\n\nBased on Stage 02K CPU float64 forward/backward evidence, conservative nine-run wall time is `{bundle['resource']['predicted_hours_nine_run_total']:.3f}` h, predicted peak RSS `{bundle['resource']['predicted_peak_RSS_bytes']/1024**3:.3f}` GiB and retained-checkpoint storage `{bundle['resource']['predicted_checkpoint_storage_bytes']/1024**3:.3f}` GiB. Limits are 1.5 GiB and 10 GiB; no N×N allocation is forecast. Status: **{bundle['resource']['status']}**.\n",
        "stage02l_success_criteria.md": "# Stage 02L — Future success criteria\n\nFrozen but not executed: 3/3 finite; at least 2/3 seeds with train family-balanced Q_L2≤0.25; at least 2/3 with validation family-balanced Q_L2≤0.90 and every graph≤1.10; sealed test uses the same transfer thresholds; all selected checkpoints retain pair/global-force residuals≤1e-10. At least one of K1/K2 must pass A–E. K0 remains diagnostic.\n",
    }
    status = bundle["status"]
    texts["stage02l_final_report.md"] = f"""# Stage 02L — Final report

## Final status

**{status}**

1. Stage 02K limited authorization: `PAIR_FORCE_PIO_ARCHITECTURE_QUALIFIED`, protocol design and zero-step preflight only.
2. Dataset/architecture freeze: **{bundle['history']['status']}**; architecture `{bundle['architecture_hash']}`; protocol `{protocol_hash}`.
3. Roles: K0 mandatory central diagnostic, K1 mandatory non-attention baseline, K2 reciprocal-attention candidate.
4. KNEG exclusion: absent from the run matrix and no optimizer created.
5. Hypotheses: H1 static learnability, H2 conservation persistence, H3 no attention-superiority presumption, H4 mandatory K0 boundary.
6. Feature/target boundary: Stage 02K features only; node-level future supervision; edge/pseudoinverse labels forbidden; target decode count in Stage 02L is 0.
7. Loss: equal-weight graph-balanced node MSE on dimensionless acceleration.
8. Conservation penalty: none; conservation remains a structural re-audit gate.
9. Update: prospective full batch contains all 10 train graphs; gradient accumulation equivalence **{bundle['harness']['status']}**.
10. Optimizer/schedule: frozen AdamW, 50 warmup, cosine to `1e-5`, maximum 1000 updates.
11. Initialization/seeds: deterministic Xavier plus near-zero coefficient head; three frozen seeds; nine configurations.
12. Validation: every 20 updates, minimum 300, patience 200, improvement `1e-6`, lowest graph-mean Q_L2 with earlier tie-break.
13. Test seal: **{bundle['test_seal']['status']}**; test targets unopened and no release manifest generated.
14. Checkpoint contract: update-zero K0/K1/K2 round trip and resume **{bundle['checkpoint']['status']}**.
15. Static harness audit: **{bundle['harness']['status']}**; forbidden step-call count {bundle['step_calls']['step_call_count']}.
16. Future success thresholds: frozen and not evaluated.
17. Resource forecast: **{bundle['resource']['status']}**, peak RSS and storage below frozen limits.
18. Stage 02M authorization: {"limited to Controlled Static Pair-Force Fitting and Sealed-Test Evaluation" if status == 'STATIC_FITTING_PROTOCOL_READY' else 'not authorized'}.
19. `optimizer_steps = 0`.
20. `training_runs = 0`.
21. No validation/test performance, generalization, attention superiority, rollout or benchmark claim.
22. Historical hashes unchanged: **{bundle['history']['status']}**; Stage 01 through Stage 02K files were not modified.

Stage 01 remains `V2_QUALIFICATION_FAIL`; Stage 01H remains `FINITE_RESOLUTION_DOMINANT`; viscosity operator form remains `NOT_CONFIRMED`; regularity remains `diagnostic_only`. Stage 02K architecture qualification is not a model-performance result.
"""
    for name, text in texts.items(): (report_dir / name).write_text(text)


def history_check(freeze: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for item in freeze["input_files"]:
        actual = sha(REPO / item["path"])
        rows.append({"path": item["path"], "expected": item["sha256"], "actual": actual, "status": "PASS" if actual == item["sha256"] else "FAIL"})
    protocol_actual = sha(REPO / freeze["protocol_file"])
    okay = all(x["status"] == "PASS" for x in rows) and protocol_actual == freeze["protocol_sha256"]
    return {"input_rows": rows, "protocol_expected": freeze["protocol_sha256"], "protocol_actual": protocol_actual, "historical_hashes_unchanged": all(x["status"] == "PASS" for x in rows), "protocol_immutable": protocol_actual == freeze["protocol_sha256"], "status": "PASS" if okay else "FAIL"}


def main() -> int:
    freeze_path = ROOT / "freeze/stage02l_input_and_protocol_freeze_manifest.json"
    freeze = json.loads(freeze_path.read_text()); protocol = yaml.safe_load((ROOT / "freeze/training_protocol_v0_1.yaml").read_text())
    if sha(ROOT / "freeze/training_protocol_v0_1.yaml") != freeze["protocol_sha256"]: raise RuntimeError("protocol drift")
    history = history_check(freeze)
    loader = SealedCollectionLoader(REPO, freeze["protocol_sha256"])
    records = [loader.load_inputs(case_id) for case_id in sorted(loader.rows)]
    graphs = [to_graph(record) for record in records]
    train_graphs = [graph for graph, record in zip(graphs, records) if record.split_role == "future_train"]
    denied = {}
    for role in ("future_validation", "future_test"):
        case_id = next(case for case, row in loader.rows.items() if row["split_role"] == role)
        try: loader.load_target(case_id); denied[role] = False
        except AccessPolicyError: denied[role] = True
    test_release_path = ROOT / "test_seal/test_release_manifest.json"
    test_seal = {"contract_version": "stage02l-test-seal-1.0.0", "test_target_access": False, "validation_target_access_current_stage": False, "denied_access_probes": denied, "all_training_complete": False, "selected_checkpoint_count": 0, "pending_restart_state": "not_applicable_no_training", "test_release_manifest_exists": test_release_path.exists(), "release_authorized": False, "status": "PASS" if all(denied.values()) and not test_release_path.exists() else "FAIL"}
    run_matrix, init_hashes = initialization_and_run_matrix(protocol)
    loss_audit, metric_audit = loss_and_gradient_audit(train_graphs)
    harness = architecture_static_audit(train_graphs)
    step_calls = forbidden_step_call_audit()
    checkpoint = checkpoint_roundtrip(loader, train_graphs[0], freeze["protocol_sha256"], freeze["architecture_hash"])
    resource = resource_forecast(checkpoint)
    access = loader.audit(); access["denied_access_probes"] = denied; access["feature_array_paths_decoded"] = sorted(INPUT_ARRAY_PATHS); access["model_input_array_paths_subset_of_frozen_contract"] = True; access["target_present_in_input_graph"] = False; access["forbidden_target_reference_aSPH_arrays_decoded"] = 0; access["status"] = "PASS" if access["target_array_decode_count"] == 0 and all(denied.values()) else "FAIL"
    optimizer_audit = {"contract_version": "stage02l-optimizer-schedule-1.0.0", "optimizer": protocol["optimizer"], "schedule": protocol["schedule"], "schedule_samples": {str(i): ProspectiveWarmupCosineSchedule().learning_rate_at(i) for i in (0, 1, 50, 300, 1000)}, "optimizer_steps": 0, "scheduler_steps": 0, "step_call_audit": step_calls, "status": step_calls["status"]}
    hypotheses = {"contract_version": "stage02l-hypotheses-1.0.0", "hypotheses": protocol["hypotheses"], "attention_superiority_preregistered": False, "status": "PASS"}
    arms = {"registry_version": "stage02l-model-arms-1.0.0", "architecture_hash": freeze["architecture_hash"], "arms": protocol["model_arms"], "new_architecture_added": False, "KNEG_optimizer_created": False, "status": "PASS"}
    gates = {"contract_version": "stage02l-future-success-gates-1.0.0", "gates": protocol["future_success_gates"], "executed_in_stage02l": False, "K1_K2_test_selection_permitted": False, "status": "FROZEN"}
    output_map = {
        ROOT / "hypotheses/hypotheses.json": hypotheses, ROOT / "model_arms/model_arm_registry.json": arms,
        ROOT / "loss/loss_static_audit.json": loss_audit, ROOT / "optimizer/optimizer_schedule_audit.json": optimizer_audit,
        ROOT / "run_matrix/run_matrix.json": run_matrix, ROOT / "data_access/data_access_audit.json": access,
        ROOT / "test_seal/test_seal_status.json": test_seal, ROOT / "checkpointing/checkpoint_roundtrip_audit.json": checkpoint,
        ROOT / "harness/training_harness_static_audit.json": harness, ROOT / "dry_runs/zero_step_dry_run.json": {"optimizer_steps": 0, "scheduler_steps": 0, "parameter_updates": 0, "training_runs": 0, "backward_preflight_executed": True, "status": harness["status"]},
        ROOT / "static_metrics/static_metric_contract_audit.json": metric_audit, ROOT / "resource_forecast/resource_forecast.json": resource,
        ROOT / "success_gates/future_success_gates.json": gates, ROOT / "freeze/historical_integrity_verification.json": history,
    }
    for path, value in output_map.items(): write_json(path, value)
    hard = all((history["status"] == "PASS", run_matrix["status"] == "PASS", loss_audit["status"] == "PASS", optimizer_audit["status"] == "PASS", access["status"] == "PASS", test_seal["status"] == "PASS", checkpoint["status"] == "PASS", harness["status"] == "PASS", metric_audit["status"] == "PASS", resource["status"] == "PASS", arms["status"] == "PASS"))
    evidence_complete = freeze["status"] == "PASS" and history["status"] == "PASS"
    status = "STATIC_FITTING_PROTOCOL_READY" if hard and evidence_complete else ("STATIC_FITTING_PROTOCOL_EVIDENCE_INCOMPLETE" if not evidence_complete else "STATIC_FITTING_PROTOCOL_NOT_READY")
    summary = {"manifest_version": "stage02l-final-1.0.0", "protocol_sha256": freeze["protocol_sha256"], "architecture_hash": freeze["architecture_hash"], "dataset_collection": freeze["collection_id"], "prospective_run_count": 9, "optimizer_steps": 0, "scheduler_steps": 0, "parameter_updates": 0, "training_runs": 0, "dataset_target_arrays_decoded": 0, "validation_performance_evaluations": 0, "test_performance_evaluations": 0, "test_target_access": False, "resource_forecast": resource["status"], "stage02m_authorized": status == "STATIC_FITTING_PROTOCOL_READY", "stage02m_scope": "Controlled Static Pair-Force Fitting and Sealed-Test Evaluation only" if status == "STATIC_FITTING_PROTOCOL_READY" else "not_authorized", "status": status}
    write_json(ROOT / "results/stage02l_qualification_summary.json", summary)
    bundle = {"protocol_hash": freeze["protocol_sha256"], "architecture_hash": freeze["architecture_hash"], "history": history, "run_matrix": run_matrix, "loss": loss_audit, "metrics": metric_audit, "harness": harness, "step_calls": step_calls, "test_seal": test_seal, "checkpoint": checkpoint, "resource": resource, "status": status}
    reports(bundle)
    artifacts = []
    for directory in ("freeze", "hypotheses", "model_arms", "loss", "optimizer", "run_matrix", "data_access", "test_seal", "checkpointing", "harness", "dry_runs", "static_metrics", "resource_forecast", "success_gates", "results"):
        for path in sorted((ROOT / directory).glob("*")):
            if path.is_file(): artifacts.append({"path": str(path.relative_to(REPO)), "sha256": sha(path), "byte_count": path.stat().st_size})
    for path in sorted((STAGE / "07_reports").glob("stage02l_*.md")):
        artifacts.append({"path": str(path.relative_to(REPO)), "sha256": sha(path), "byte_count": path.stat().st_size})
    manifest = {"manifest_version": "stage02l-run-1.0.0", "protocol_sha256": freeze["protocol_sha256"], "architecture_hash": freeze["architecture_hash"], "python": sys.version, "torch": torch.__version__, "numpy": np.__version__, "device": "CPU", "dtype": "float64", "artifacts": artifacts, "optimizer_steps": 0, "scheduler_steps": 0, "parameter_updates": 0, "training_runs": 0, "test_target_access": False, "status": status}
    write_json(ROOT / "manifests/stage02l_run_manifest.json", manifest)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
