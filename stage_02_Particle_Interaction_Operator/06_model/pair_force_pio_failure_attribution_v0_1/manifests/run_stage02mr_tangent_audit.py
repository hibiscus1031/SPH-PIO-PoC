#!/usr/bin/env python3
"""Matrix-free whole-network and small dense final-head tangent audits; no writeback."""

from __future__ import annotations

import json
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any

import numpy as np
import torch
from scipy.sparse.linalg import LinearOperator, lsqr

from audit_common import (
    ARCHITECTURES, A0, ROOT, SEEDS, STAGE, aggregate, load_items, make_model,
    metric_row, tensor_hash, terminal, write_json,
)

CONTRACT = json.loads((ROOT / "freeze/diagnostic_contract_v0_1.json").read_text())
TC = CONTRACT["tangent_space"]


class TangentOperator:
    def __init__(self, model: torch.nn.Module, items: list[Any]) -> None:
        self.model = model
        self.items = items
        self.names = [name for name, _ in model.named_parameters()]
        self.shapes = [parameter.shape for parameter in model.parameters()]
        self.sizes = [parameter.numel() for parameter in model.parameters()]
        self.offsets = np.cumsum([0] + self.sizes)
        self.theta = torch.cat([parameter.detach().reshape(-1) for parameter in model.parameters()])
        self.graph_slices: list[tuple[int, int, float, Any]] = []
        start = 0
        for item in items:
            n = item.graph.position.shape[0]
            length = int(2 * n)
            scale = A0 * np.sqrt(len(items) * n)
            self.graph_slices.append((start, start + length, scale, item))
            start += length
        self.output_size = start
        self.parameter_size = int(self.theta.numel())
        self.matvec_calls = 0
        self.rmatvec_calls = 0

    def params(self, vector: torch.Tensor) -> OrderedDict[str, torch.Tensor]:
        return OrderedDict((name, vector[int(self.offsets[i]):int(self.offsets[i + 1])].view(shape)) for i, (name, shape) in enumerate(zip(self.names, self.shapes)))

    def function(self, vector: torch.Tensor) -> torch.Tensor:
        params = self.params(vector)
        outputs = []
        for start, end, scale, item in self.graph_slices:
            del start, end
            prediction = torch.func.functional_call(self.model, params, (item.graph,))
            outputs.append(prediction.reshape(-1) / scale)
        return torch.cat(outputs)

    def base_and_target(self) -> tuple[np.ndarray, np.ndarray]:
        with torch.no_grad():
            base = self.function(self.theta).detach().numpy()
        targets = []
        for _, _, scale, item in self.graph_slices:
            targets.append(item.target.detach().numpy().reshape(-1) / scale)
        return base, np.concatenate(targets)

    def matvec(self, vector: np.ndarray) -> np.ndarray:
        self.matvec_calls += 1
        tangent = torch.as_tensor(np.asarray(vector, dtype=np.float64))
        _, output = torch.func.jvp(self.function, (self.theta,), (tangent,))
        return output.detach().numpy()

    def rmatvec(self, vector: np.ndarray) -> np.ndarray:
        self.rmatvec_calls += 1
        theta = self.theta.detach().clone().requires_grad_(True)
        output = self.function(theta)
        cotangent = torch.as_tensor(np.asarray(vector, dtype=np.float64))
        gradient = torch.autograd.grad(output, theta, grad_outputs=cotangent, retain_graph=False, create_graph=False)[0]
        return gradient.detach().numpy()

    def scipy_operator(self) -> LinearOperator:
        return LinearOperator((self.output_size, self.parameter_size), matvec=self.matvec, rmatvec=self.rmatvec, dtype=np.float64)

    def metrics_from_weighted(self, weighted: np.ndarray) -> dict[str, Any]:
        rows = []
        for start, end, scale, item in self.graph_slices:
            prediction = torch.as_tensor(weighted[start:end].reshape(-1, 2) * scale)
            values = metric_row(prediction, item.target)
            rows.append({"case_id": item.case_id, "family_id": item.family_id, "resolution_id": item.resolution_id, "support_id": item.support_id, **values})
        return aggregate(rows)


def audit_point(architecture: str, seed: int, point: str, checkpoint: Path | None, train_items: list[Any]) -> dict[str, Any]:
    started = time.perf_counter()
    model, _ = make_model(architecture, seed, checkpoint)
    before = tensor_hash(model)
    operator = TangentOperator(model, train_items)
    base, target = operator.base_and_target()
    residual = target - base
    linear = operator.scipy_operator()
    solution = lsqr(linear, residual, atol=TC["atol"], btol=TC["btol"], conlim=TC["conlim"], iter_lim=TC["iteration_limit"], show=False)
    delta = solution[0]
    projected = base + operator.matvec(delta)
    whole_metrics = operator.metrics_from_weighted(projected)

    rng = np.random.default_rng(TC["rank_probe_seed"] + seed + {"K0": 0, "K1": 100, "K2": 200}[architecture] + (0 if point == "initialization" else 1000))
    probe_outputs = []
    for _ in range(TC["rank_probe_count"]):
        probe = rng.standard_normal(operator.parameter_size)
        probe /= max(np.linalg.norm(probe), 1e-300)
        probe_outputs.append(operator.matvec(probe))
    sketch = np.stack(probe_outputs, axis=1)
    sketch_sv = np.linalg.svd(sketch, compute_uv=False)
    effective_rank = int(np.sum(sketch_sv >= sketch_sv[0] * TC["effective_rank_relative_threshold"])) if sketch_sv[0] > 0 else 0

    head_indices = []
    for index, name in enumerate(operator.names):
        if name.startswith("coefficient_head"):
            head_indices.extend(range(int(operator.offsets[index]), int(operator.offsets[index + 1])))
    head_jacobian = np.empty((operator.output_size, len(head_indices)), dtype=np.float64)
    for column, parameter_index in enumerate(head_indices):
        direction = np.zeros(operator.parameter_size, dtype=np.float64)
        direction[parameter_index] = 1.0
        head_jacobian[:, column] = operator.matvec(direction)
    head_delta, head_residuals, head_rank, head_singular = np.linalg.lstsq(head_jacobian, residual, rcond=CONTRACT["final_head_tangent"]["rcond"])
    head_projected = base + head_jacobian @ head_delta
    head_metrics = operator.metrics_from_weighted(head_projected)
    after = tensor_hash(model)
    result = {
        "architecture": architecture,
        "seed": seed,
        "point": point,
        "checkpoint": None if checkpoint is None else str(checkpoint.relative_to(STAGE.parent)),
        "parameter_count": operator.parameter_size,
        "output_scalar_count": operator.output_size,
        "parameter_hash_before": before,
        "parameter_hash_after": after,
        "parameter_hash_unchanged": before == after,
        "whole_network": {
            "linearized_metrics": whole_metrics,
            "attainable_train_family_balanced_Q_L2": whole_metrics["family_balanced_mean"]["Q_L2"],
            "weighted_initial_residual_L2": float(np.linalg.norm(residual)),
            "weighted_projected_residual_L2": float(np.linalg.norm(target - projected)),
            "LSQR_istop": int(solution[1]),
            "LSQR_iterations": int(solution[2]),
            "LSQR_r1norm": float(solution[3]),
            "LSQR_arnorm": float(solution[7]),
            "LSQR_operator_norm_estimate": float(solution[5]),
            "LSQR_condition_estimate": float(solution[6]),
            "delta_parameter_norm": float(np.linalg.norm(delta)),
            "rank_probe_effective_rank": effective_rank,
            "rank_probe_count": TC["rank_probe_count"],
            "rank_probe_singular_value_max": float(sketch_sv[0]),
            "rank_probe_singular_value_min": float(sketch_sv[-1]),
            "rank_probe_singular_values": sketch_sv.tolist(),
        },
        "final_head": {
            "head_parameter_count": len(head_indices),
            "dense_small_head_jacobian_only": True,
            "linearized_metrics": head_metrics,
            "attainable_train_family_balanced_Q_L2": head_metrics["family_balanced_mean"]["Q_L2"],
            "weighted_projected_residual_L2": float(np.linalg.norm(target - head_projected)),
            "matrix_rank": int(head_rank),
            "singular_value_max": float(head_singular[0]) if len(head_singular) else 0.0,
            "singular_value_min": float(head_singular[-1]) if len(head_singular) else 0.0,
            "least_squares_reported_residual": head_residuals.tolist(),
        },
        "matrix_free_calls": {"JVP": operator.matvec_calls, "VJP": operator.rmatvec_calls},
        "wall_seconds": time.perf_counter() - started,
        "no_writeback": True,
        "new_checkpoint": False,
        "validation_target_used": False,
        "test_target_used": False,
    }
    print(json.dumps({"architecture": architecture, "seed": seed, "point": point, "whole_Q": result["whole_network"]["attainable_train_family_balanced_Q_L2"], "head_Q": result["final_head"]["attainable_train_family_balanced_Q_L2"], "iterations": result["whole_network"]["LSQR_iterations"], "seconds": result["wall_seconds"]}), flush=True)
    return result


def main() -> None:
    freeze = json.loads((ROOT / "freeze/stage02mr_historical_freeze_manifest.json").read_text())
    if freeze["status"] != "PASS":
        raise RuntimeError("historical freeze failed")
    _loader, items = load_items(include_test_inputs=False)
    results = []
    for architecture in ARCHITECTURES:
        for seed in SEEDS:
            term = terminal(architecture, seed)
            selected = STAGE.parent / term["selected_checkpoint"]
            results.append(audit_point(architecture, seed, "initialization", None, items["future_train"]))
            results.append(audit_point(architecture, seed, "selected", selected, items["future_train"]))
            write_json(ROOT / "tangent_space/tangent_space_partial.json", {"audits": results, "complete": False})
    for row in results:
        head_q = row["final_head"]["attainable_train_family_balanced_Q_L2"]
        whole_q = row["whole_network"]["attainable_train_family_balanced_Q_L2"]
        if head_q <= 0.25:
            row["final_head_classification"] = "HEAD_OPTIMIZATION_GAP"
        elif whole_q <= 0.25:
            row["final_head_classification"] = "ENCODER_REPRESENTATION_LIMIT"
        else:
            row["final_head_classification"] = "WHOLE_NETWORK_NONLINEAR_OR_UNRESOLVED"
    output = {
        "contract": TC,
        "audits": results,
        "all_parameter_hashes_unchanged": all(row["parameter_hash_unchanged"] for row in results),
        "complete": len(results) == 18,
        "new_optimizer_steps": 0,
        "new_checkpoints": 0,
        "validation_target_used": False,
        "test_target_used": False,
    }
    write_json(ROOT / "tangent_space/tangent_space_audit.json", output)
    print(json.dumps({"complete": output["complete"], "all_parameter_hashes_unchanged": output["all_parameter_hashes_unchanged"], "audit_count": len(results)}))


if __name__ == "__main__":
    main()
