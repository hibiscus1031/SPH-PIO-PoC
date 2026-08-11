"""Freeze Stage 04C before any TRAIN trajectory state-array decode.

This module intentionally does not import numpy and never opens a trajectory
NPZ.  It resolves the verified Stage 03C parameter tensors, preregisters every
formal case/direction identity, hashes the historical authorization inputs, and
then seals the Stage 04C contract.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import torch
import yaml


HERE = Path(__file__).resolve()
STAGE04C = HERE.parents[1]
STAGE04 = HERE.parents[3]
ROOT = HERE.parents[4]
STAGE03C = ROOT / "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c"
for candidate in (STAGE03C, ROOT / "01_solver"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from arm_d1.model import D1InstantaneousPairMLP
from arm_d2.model import D2CausalRecurrentPairPIO
from arm_d3.model import D3CausalTemporalTransformerPIO


SEEDS = [20400401, 20400402, 20400403]
LINEAGES = ["LCDF_01", "LCDF_04", "LCDF_05", "LCDF_06", "LCDF_07", "LCDF_08"]
VARIANTS = ["VARIANT_LOW", "VARIANT_MAIN"]
ARMS = {
    "D1": D1InstantaneousPairMLP,
    "D2": D2CausalRecurrentPairPIO,
    "D3": D3CausalTemporalTransformerPIO,
}
BACKEND_IDENTITY = "CPU_FLOAT64_TORCH_SDPA_EXPLICIT_MATH_NO_AUTO"


def sha_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def origin_digest(lineage: str, variant: str, origin: int) -> str:
    raw = "stage04c_origin_selection_v1" + lineage + variant + str(origin)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def selected_origins(lineage: str, variant: str, count: int = 2) -> list[int]:
    ranked = sorted(range(32), key=lambda n: origin_digest(lineage, variant, n))
    return ranked[:count]


def group_definitions(arm: str, model: torch.nn.Module) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    if arm == "D1":
        prefix_map = {"D1_TOKEN_ENCODER": ("encoder.",), "D1_PAIR_HEAD": ("pair_head.",)}
    elif arm == "D2":
        prefix_map = {
            "D2_TOKEN_ENCODER": ("encoder.",),
            "D2_GRU": ("recurrent.",),
            "D2_PAIR_HEAD": ("pair_head.",),
        }
    else:
        prefix_map = {
            "D3_TOKEN_ENCODER": ("encoder.",),
            "D3_ATTENTION_O": ("temporal.layers.0.self_attn.out_proj.", "temporal.layers.1.self_attn.out_proj."),
            "D3_FEED_FORWARD": (
                "relative_offset_embedding",
                "temporal.layers.0.linear1.", "temporal.layers.0.linear2.",
                "temporal.layers.0.norm1.", "temporal.layers.0.norm2.",
                "temporal.layers.1.linear1.", "temporal.layers.1.linear2.",
                "temporal.layers.1.norm1.", "temporal.layers.1.norm2.",
            ),
            "D3_PAIR_HEAD": ("pair_head.",),
        }
    assigned: set[tuple[str, str]] = set()
    named = dict(model.named_parameters())
    for group, prefixes in prefix_map.items():
        rows = []
        for name, tensor in named.items():
            if any(name == p or name.startswith(p) for p in prefixes):
                rows.append({"tensor_path": name, "slice": "all", "shape": list(tensor.shape), "parameter_count": tensor.numel()})
                assigned.add((name, "all"))
        groups[group] = rows
    if arm == "D3":
        for qkv_index, label in enumerate(("Q", "K", "V")):
            group = f"D3_ATTENTION_{label}"
            rows = []
            start, stop = 32 * qkv_index, 32 * (qkv_index + 1)
            for layer in (0, 1):
                for suffix in ("weight", "bias"):
                    name = f"temporal.layers.{layer}.self_attn.in_proj_{suffix}"
                    tensor = named[name]
                    rows.append({
                        "tensor_path": name,
                        "slice": f"[{start}:{stop}]" if suffix == "bias" else f"[{start}:{stop},:]",
                        "shape": list(tensor[start:stop].shape),
                        "parameter_count": tensor[start:stop].numel(),
                    })
                    assigned.add((name, f"[{start}:{stop}]"))
            groups[group] = rows
    # Exact coverage is checked elementwise, including combined QKV slices.
    coverage: dict[str, torch.Tensor] = {name: torch.zeros_like(tensor, dtype=torch.int8) for name, tensor in named.items()}
    for rows in groups.values():
        for row in rows:
            mask = coverage[row["tensor_path"]]
            spec = row["slice"]
            if spec == "all":
                mask.add_(1)
            else:
                row_slice = spec.split(",")[0].lstrip("[").rstrip("]")
                start, stop = (int(x) for x in row_slice.split(":")[:2])
                mask[start:stop].add_(1)
    if not all(bool((mask == 1).all()) for mask in coverage.values()):
        raise RuntimeError(f"non-unique parameter coverage for {arm}")
    return groups


def tensor_hash(model: torch.nn.Module, *, prefix: str | None = None) -> str:
    digest = hashlib.sha256(BACKEND_IDENTITY.encode("ascii"))
    for name, tensor in model.named_parameters():
        if prefix is None or name == prefix or name.startswith(prefix):
            digest.update(name.encode("utf-8")); digest.update(str(tuple(tensor.shape)).encode("ascii"))
            digest.update(tensor.detach().contiguous().numpy().tobytes())
    return "sha256:" + digest.hexdigest()


def main() -> None:
    subdirs = [
        "freeze", "contracts", "access_control", "train_case_selection", "model_instantiation",
        "parameter_group_map", "direction_generation", "loss_components", "reverse_vjp", "forward_jvp",
        "finite_difference", "stable_windows", "diagnostic_input_gradients", "structure_and_safety",
        "determinism", "resources", "qualification", "manifests", "results",
    ]
    for name in subdirs:
        (STAGE04C / name).mkdir(parents=True, exist_ok=True)

    history_paths = [
        "stage_04_Local_Causal_Dynamic_Training/08_reports/stage04a_final_report.md",
        "stage_04_Local_Causal_Dynamic_Training/08_reports/stage04a_gradient_strategy.md",
        "stage_04_Local_Causal_Dynamic_Training/08_reports/stage04a_training_hypothesis.md",
        "stage_04_Local_Causal_Dynamic_Training/08_reports/stage04a_dataset_strategy.md",
        "stage_04_Local_Causal_Dynamic_Training/00_stage04a_verification/reports/stage04a_target_verification_report.md",
        "stage_04_Local_Causal_Dynamic_Training/00_stage04a_verification/manifests/stage04a_target_verification_manifest.json",
        "stage_04_Local_Causal_Dynamic_Training/08_reports/stage04b_final_report.md",
        "stage_04_Local_Causal_Dynamic_Training/04_reference_family_pool/stage04b/contracts/local_causal_reference_family_contract_v0_1.yaml",
        "stage_04_Local_Causal_Dynamic_Training/09_manifests/stage04b_formula_manifest.json",
        "stage_04_Local_Causal_Dynamic_Training/09_manifests/stage04b_lineage_manifest.json",
        "stage_04_Local_Causal_Dynamic_Training/09_manifests/stage04b_role_assignment_manifest.json",
        "stage_04_Local_Causal_Dynamic_Training/09_manifests/stage04b_trajectory_manifest.json",
        "stage_04_Local_Causal_Dynamic_Training/09_manifests/stage04b_test_seal_manifest.json",
        "stage_04_Local_Causal_Dynamic_Training/04_reference_family_pool/stage04b/topology_margin/topology_margin_summary.json",
        "stage_04_Local_Causal_Dynamic_Training/04_reference_family_pool/stage04b/analytic_qualification/analytic_qualification_summary.json",
        "stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03c_final_manifest.json",
        "stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03d_final_manifest.json",
        "stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03dr_final_manifest.json",
    ]
    source_paths = sorted(
        str(path.relative_to(ROOT)) for path in STAGE03C.rglob("*.py")
        if any(part in {"arm_d1", "arm_d2", "arm_d3", "baseline_d0", "graph_rebuild", "pair_force_head", "rk2_core", "source_interface", "temporal_history", "tokenization"} for part in path.parts)
    )
    input_rows = [{"path": p, "sha256": sha_file(ROOT / p)} for p in history_paths + source_paths]
    auth = json.loads((STAGE04 / "09_manifests/stage04b_final_manifest.json").read_text(encoding="utf-8"))
    if auth.get("final_status") != "LOCAL_CAUSAL_REFERENCE_FAMILY_POOL_QUALIFIED":
        raise RuntimeError("Stage04B authorization absent")

    origin_rows = []
    formal_cases = []
    for lineage in LINEAGES:
        for variant in VARIANTS:
            chosen = selected_origins(lineage, variant)
            origin_rows.append({"lineage": lineage, "variant": variant, "selected_origins": chosen,
                                "digests": [origin_digest(lineage, variant, n) for n in chosen]})
            for origin in chosen:
                for seed in SEEDS:
                    formal_cases.append({"lineage": lineage, "variant": variant, "origin": origin, "model_seed": seed, "resolution": 8})

    model_rows: list[dict[str, Any]] = []
    group_map: dict[str, Any] = {}
    for arm, cls in ARMS.items():
        for seed in SEEDS:
            torch.manual_seed(seed)
            model = cls().to(dtype=torch.float64, device="cpu")
            groups = group_definitions(arm, model)
            if seed == SEEDS[0]:
                group_map[arm] = groups
            model_rows.append({
                "arm": arm, "model_seed": seed, "architecture": model.arm_id,
                "parameter_count": sum(p.numel() for p in model.parameters()),
                "complete_parameter_hash": tensor_hash(model),
                "per_module_hashes": {name: tensor_hash(model, prefix=name) for name, _ in model.named_children()},
                "backend_identity": BACKEND_IDENTITY,
            })
    group_rows = []
    for arm, groups in group_map.items():
        for group, tensors in groups.items():
            body = {"arm": arm, "group": group, "flatten_ordering": "named_parameters order, C-contiguous, listed slice order", "tensors": tensors}
            group_rows.append({**body, "parameter_count": sum(r["parameter_count"] for r in tensors), "group_hash": sha_bytes(canonical(body))})

    direction_rows = []
    for arm in ARMS:
        for group in [row["group"] for row in group_rows if row["arm"] == arm]:
            for case in formal_cases:
                raw = "stage04c_parameter_direction_v1" + arm + group + case["lineage"] + case["variant"] + str(case["origin"]) + str(case["model_seed"])
                direction_rows.append({"arm": arm, "group": group, **case,
                                       "direction_seed_sha256": sha_bytes(raw.encode("utf-8")),
                                       "rule": "SHA256 counter stream -> deterministic Rademacher {-1,+1}; group L2 normalize"})

    contract: dict[str, Any] = {
        "stage": "Stage 04C — Task-Aligned Parameter-Gradient Qualification",
        "version": "v0.1", "authorization": auth["final_status"],
        "historical_statuses": {"stage04a": "STAGE04A_TARGET_VERIFIED", "stage03d": "DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED", "stage03dr": "DYNAMIC_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED", "stage03e_authorization": False, "stage04_training": "NOT_AUTHORIZED"},
        "formal_environment": {"device": "CPU", "dtype": "float64", "attention_backend": "SDPBackend.MATH", "backend_identity": BACKEND_IDENTITY, "flash_sdpa": False, "memory_efficient_sdpa": False, "automatic_selection": False},
        "source_hashes": [{"path": p, "sha256": sha_file(ROOT / p)} for p in source_paths],
        "model_seeds": SEEDS, "train_lineages": LINEAGES, "variants": VARIANTS, "resolution": 8,
        "origin_selection": {"namespace": "stage04c_origin_selection_v1", "legal_origins": list(range(32)), "count": 2, "ranking": "ascending SHA256 hex"},
        "parameter_groups": group_rows,
        "direction_generation": {"namespace": "stage04c_parameter_direction_v1", "distribution": "Rademacher", "normalization": "L2=1", "mutation": False},
        "loss_components": {
            "vector": ["L_x", "L_v", "L_rho"], "transition": "complete K=1 explicit-midpoint RK2 start/midpoint/accept",
            "L_x": "mean(||minimum_image(x_pred-x_ref)||^2/L^2)", "L_v": "mean(||v_pred-v_ref||^2/cs^2)", "L_rho": "mean((rho_pred-rho_ref)^2/rho0^2)",
            "constants": {"L": 2.0, "cs": 20.0, "rho0": 1.0}, "L_sum_training_weight_authority": False,
        },
        "reverse_jvp_gate": {"absolute": 1e-10, "relative": 1e-7, "near_zero_both": 1e-12, "near_zero_abs_difference": 1e-12, "required_pass_rate": 1.0},
        "finite_difference": {"scheme": "central", "epsilon_ladder": [1e-2, 3e-3, 1e-3, 3e-4, 1e-4], "epsilon_actual": "epsilon*max(1,group_RMS)", "repeats": 2, "minimum_topology_preserving_epsilons": 3},
        "stable_window": {"fd_ad_absolute": 1e-8, "fd_ad_relative": 1e-4, "adjacent_fd_relative": 1e-3, "minimum_adjacent_epsilons": 2},
        "near_zero": {"reverse_and_jvp_absolute_below": 1e-10, "stable_fd_absolute": 1e-8, "at_least_one_nonzero_component_per_probe": True},
        "aggregation": {"seed_lineage_group": "at least 3/4 probes", "lineage_group": "at least 2/3 seeds", "parameter_group": "all 6 lineages", "arm": "all groups", "minimum_arm_probe_pass_rate": 0.85},
        "input_gradient_diagnostics": {"hard_gate": False, "lineages": LINEAGES[:2], "variant": "VARIANT_MAIN", "origins_per_lineage": 1, "seeds": SEEDS},
        "structure_safety": {"correction_force_residual_max": 1e-10, "audit_granularity": "arm*seed*lineage", "accepted_history_commits": 1, "midpoint_commits": 0},
        "resource_gates": {"peak_rss_delta_gib_max": 1.5, "retained_autograd_growth": False, "parameter_mutation": False, "dense_particle_nxn": False, "finite_completion": True},
        "access_policy": {"allowed": "TRAIN exact trajectories/source/formula parameters/graph/origin metadata", "validation_lineages": ["LCDF_02", "LCDF_09"], "sealed_lineages": ["LCDF_03", "LCDF_10"], "all_prohibited_decode_counts": 0},
        "prohibited_counts": {"optimizer_instances": 0, "optimizer_steps": 0, "training_runs": 0, "parameter_updates": 0, "neural_rollouts": 0, "performance_evaluations": 0},
        "formal_counts": {"contexts_per_arm": 72, "D1_probes": 144, "D2_probes": 216, "D3_probes": 504, "total_probes": 864},
    }
    contract_path = STAGE04C / "contracts/task_aligned_parameter_gradient_contract_v0_1.yaml"
    contract_path.write_text(yaml.safe_dump(contract, sort_keys=False, allow_unicode=True), encoding="utf-8")
    contract_hash = sha_file(contract_path)
    freeze_record = {
        "freeze_completed_before_train_state_array_decode": True,
        "train_state_array_decode_count_at_freeze": 0,
        "contract_path": str(contract_path.relative_to(ROOT)), "contract_sha256": contract_hash,
        "historical_input_count": len(input_rows), "historical_inputs": input_rows,
        "stage04b_authorization": auth["final_status"], "pass": True,
    }
    write_json(STAGE04C / "freeze/stage04c_freeze_record.json", freeze_record)
    write_json(STAGE04 / "09_manifests/stage04c_input_freeze_manifest.json", freeze_record)
    write_json(STAGE04 / "09_manifests/stage04c_contract_manifest.json", {"contract": str(contract_path.relative_to(ROOT)), "sha256": contract_hash, "immutable_after_train_decode": True, "backend_identity": BACKEND_IDENTITY})
    write_json(STAGE04 / "09_manifests/stage04c_case_manifest.json", {"selection_before_state_decode": True, "origin_rows": origin_rows, "formal_contexts_per_arm": 72, "cases": formal_cases})
    write_json(STAGE04 / "09_manifests/stage04c_parameter_manifest.json", {"unique_complete_assignment": True, "unassigned_parameter_elements": 0, "multiply_assigned_parameter_elements": 0, "models": model_rows, "groups": group_rows})
    write_json(STAGE04 / "09_manifests/stage04c_direction_manifest.json", {"generation_before_state_decode": True, "expected_direction_count": 864, "direction_count": len(direction_rows), "directions": direction_rows})
    write_json(STAGE04C / "train_case_selection/formal_case_selection.json", {"origin_rows": origin_rows, "cases": formal_cases})
    write_json(STAGE04C / "model_instantiation/fresh_model_instances.json", {"models": model_rows, "checkpoint_reads": 0, "weight_reads": 0})
    write_json(STAGE04C / "parameter_group_map/exact_parameter_groups.json", {"groups": group_rows, "pass": True})
    write_json(STAGE04C / "direction_generation/preregistered_directions.json", {"directions": direction_rows, "count": len(direction_rows)})
    print(json.dumps({"contract_sha256": contract_hash, "formal_cases_per_arm": len(formal_cases), "directions": len(direction_rows)}))


if __name__ == "__main__":
    main()
