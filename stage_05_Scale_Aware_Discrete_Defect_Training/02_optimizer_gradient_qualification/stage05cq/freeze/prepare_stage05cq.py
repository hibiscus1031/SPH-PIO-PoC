"""Freeze all prospective Stage 05C-Q identities before any blind target decode."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import torch
import yaml


HERE = Path(__file__).resolve()
STAGE05CQ = HERE.parents[1]
STAGE05 = HERE.parents[3]
ROOT = HERE.parents[4]
STAGE05C = STAGE05 / "02_optimizer_gradient_qualification/stage05c"
STAGE05CR = STAGE05 / "02_optimizer_gradient_qualification/stage05cr"
STAGE03C = ROOT / "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c"
sys.path[:0] = [str(STAGE03C), str(ROOT / "01_solver")]
from arm_d1.model import D1InstantaneousPairMLP
from arm_d2.model import D2CausalRecurrentPairPIO
from arm_d3.model import D3CausalTemporalTransformerPIO


SEEDS = [20500521, 20500522, 20500523]
LINEAGES = ["LCDF_01", "LCDF_04", "LCDF_05", "LCDF_06", "LCDF_07", "LCDF_08"]
VARIANTS = ["VARIANT_LOW", "VARIANT_MAIN"]
ARMS = {"D1": D1InstantaneousPairMLP, "D2": D2CausalRecurrentPairPIO, "D3": D3CausalTemporalTransformerPIO}
RADII = [3e-7, 1e-6, 3e-6, 1e-5, 3e-5, 1e-4, 3e-4, 1e-3]


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def tensor_bytes(value: torch.Tensor) -> bytes:
    array = value.detach().contiguous().cpu().numpy()
    return str(array.dtype).encode() + b"\0" + np.asarray(array.shape, dtype=np.int64).tobytes() + array.tobytes()


def parameter_hash(model: torch.nn.Module) -> str:
    digest = hashlib.sha256()
    for name, parameter in model.named_parameters():
        digest.update(name.encode()); digest.update(tensor_bytes(parameter))
    return "sha256:" + digest.hexdigest()


def group_for(arm: str, name: str) -> tuple[str, dict[str, Any]]:
    entry = {"tensor_path": name, "slice": "all"}
    if arm == "D1":
        return ("D1_TOKEN_ENCODER" if name.startswith("encoder.") else "D1_PAIR_HEAD"), entry
    if arm == "D2":
        if name.startswith("encoder."): group = "D2_TOKEN_ENCODER"
        elif name.startswith("recurrent."): group = "D2_GRU"
        else: group = "D2_PAIR_HEAD"
        return group, entry
    if name == "relative_offset_embedding" or name.startswith("encoder."): return "D3_TOKEN_ENCODER", entry
    if name.startswith("pair_head."): return "D3_PAIR_HEAD", entry
    if ".self_attn.in_proj_" in name: raise RuntimeError("Q/K/V require explicit slices")
    if ".self_attn.out_proj." in name: return "D3_ATTENTION_O", entry
    return "D3_FEED_FORWARD", entry


historical_final = json.loads((STAGE05 / "09_manifests/stage05c_final_manifest.json").read_text())
historical_probe_plan = json.loads((STAGE05C / "parameter_groups/preregistered_probe_plan.json").read_text())
historical_batches = json.loads((STAGE05C / "batch_selection/preregistered_batches.json").read_text())
stage05cr_final = json.loads((STAGE05CR / "manifests/stage05cr_final_manifest.json").read_text())
stage05cr_controls = json.loads((STAGE05CR / "manifests/stage05cr_matched_control_manifest.json").read_text())
assert historical_final["terminal_status"] == "OPTIMIZER_ALIGNED_DEFECT_GRADIENT_AND_LOCAL_DESCENT_NOT_QUALIFIED"
assert stage05cr_final["stage05cr_status"] == "DEFECT_GRADIENT_FD_FAILURE_EVIDENCE_INCOMPLETE"
assert not stage05cr_final["stage05cp_started"]

models = []
group_maps: dict[str, list[dict[str, Any]]] = {}
architecture = {}
for arm, cls in ARMS.items():
    torch.manual_seed(SEEDS[0])
    schema_model = cls().to(dtype=torch.float64, device="cpu")
    grouped: dict[str, list[dict[str, Any]]] = {}
    for name, parameter in schema_model.named_parameters():
        if arm == "D3" and ".self_attn.in_proj_" in name:
            width = parameter.shape[0] // 3
            for label, start in (("Q", 0), ("K", width), ("V", 2 * width)):
                entry = {"tensor_path": name, "slice_dim0": [start, start + width], "slice": f"dim0[{start}:{start + width}]",
                         "shape": [width, *parameter.shape[1:]], "element_count": int(width * np.prod(parameter.shape[1:] or (1,)))}
                grouped.setdefault(f"D3_ATTENTION_{label}", []).append(entry)
        else:
            group, entry = group_for(arm, name)
            entry.update({"shape": list(parameter.shape), "element_count": parameter.numel()})
            grouped.setdefault(group, []).append(entry)
    expected = {
        "D1": ["D1_TOKEN_ENCODER", "D1_PAIR_HEAD"],
        "D2": ["D2_TOKEN_ENCODER", "D2_GRU", "D2_PAIR_HEAD"],
        "D3": ["D3_TOKEN_ENCODER", "D3_ATTENTION_Q", "D3_ATTENTION_K", "D3_ATTENTION_V", "D3_ATTENTION_O", "D3_FEED_FORWARD", "D3_PAIR_HEAD"],
    }[arm]
    assert set(grouped) == set(expected)
    rows = []
    for group in expected:
        entries = grouped[group]
        rows.append({"group": group, "entries": entries, "element_count": sum(entry["element_count"] for entry in entries),
                     "flatten_order": "named_parameters then C-order within frozen slice", "group_schema_sha256": sha_bytes(canonical(entries))})
    assert sum(row["element_count"] for row in rows) == sum(parameter.numel() for parameter in schema_model.parameters())
    group_maps[arm] = rows
    schema = [{"name": name, "shape": list(parameter.shape), "count": parameter.numel()} for name, parameter in schema_model.named_parameters()]
    sources = [STAGE03C / f"arm_{arm.lower()}/model.py", STAGE03C / "pair_force_head/head.py"]
    architecture[arm] = {"parameter_count": sum(parameter.numel() for parameter in schema_model.parameters()), "parameter_schema": schema,
                         "architecture_sha256": sha_bytes(canonical({"schema": schema, "sources": [sha_file(path) for path in sources]}))}
    del schema_model
    for seed in SEEDS:
        torch.manual_seed(seed)
        model = cls().to(dtype=torch.float64, device="cpu")
        module_hashes = {name or "<root>": sha_bytes(b"".join(tensor_bytes(parameter) for parameter in module.parameters(recurse=False)))
                         for name, module in model.named_modules() if any(True for _ in module.parameters(recurse=False))}
        models.append({"arm": arm, "seed": seed, "architecture_sha256": architecture[arm]["architecture_sha256"],
                       "complete_parameter_sha256": parameter_hash(model), "parameter_count": sum(parameter.numel() for parameter in model.parameters()),
                       "module_hashes": module_hashes, "backend": "CPU_FLOAT64_SDPBackend.MATH"})
        del model
model_path = STAGE05CQ / "blind_model_seeds/preregistered_blind_model_identities.json"
group_path = STAGE05CQ / "parameter_groups/preregistered_parameter_groups.json"
write_json(model_path, {"seeds": SEEDS, "prefreeze_introspection_model_instances": 3, "freeze_model_instances": 9,
                        "formal_model_instances_planned": 9, "models": models, "architecture": architecture,
                        "fresh_initialization": True, "historical_weights_read": False})
write_json(group_path, {"groups": group_maps, "coverage_unique": True, "coverage_complete": True})

old_origins = {(row["lineage"], row["variant"]): set(row["origins"]) for row in historical_batches["selection"]}
selection = []
for lineage in LINEAGES:
    for variant in VARIANTS:
        excluded = old_origins[(lineage, variant)]
        ranked = sorted((hashlib.sha256(("stage05cq_blind_origin_v1" + lineage + variant + str(origin)).encode()).hexdigest(), origin)
                        for origin in range(32) if origin not in excluded)
        chosen = ranked[:4]
        selection.append({"lineage": lineage, "variant": variant, "origins": [origin for _, origin in chosen],
                          "keys": ["sha256:" + key for key, _ in chosen], "excluded_stage05c_origins": sorted(excluded), "overlap_count": 0})
diagnostics = []
old_diag = {(row["resolution"], row["lineage"]): row["origin"] for row in historical_batches["resolution_diagnostics"]}
for resolution in (12, 16):
    for lineage in LINEAGES:
        key = hashlib.sha256(("stage05cq_resolution_origin_v1" + str(resolution) + lineage).encode()).hexdigest()
        origin = int(key[:16], 16) % 32
        while origin == old_diag[(resolution, lineage)]: origin = (origin + 1) % 32
        diagnostics.append({"resolution": resolution, "lineage": lineage, "variant": "VARIANT_MAIN", "origin": origin,
                            "key": "sha256:" + key, "stage05c_diagnostic_origin": old_diag[(resolution, lineage)], "overlap": False})
origin_path = STAGE05CQ / "blind_origin_selection/preregistered_blind_origins.json"
write_json(origin_path, {"schema": "sph-pio-poc.stage05cq.blind-origins.v1", "selection": selection, "resolution_diagnostics": diagnostics,
                         "formal_case_count": 48, "global_case_count": 48, "stage05c_origin_overlap_count": 0})

old_coords: dict[tuple[str, str], set[int]] = {}
old_block_keys = set()
for context in historical_probe_plan["contexts"]:
    old_coords.setdefault((context["arm"], context["group"]), set()).update(row["group_flat_index"] for row in context["coordinates"])
    old_block_keys.update(row["key"] for row in context["blocks"])
excluded_keys = set(stage05cr_final["probe_attributions"])
for row in stage05cr_controls["rows"]:
    excluded_keys.update(row["selected_control_keys"])
probe_contexts = []
for arm, rows in group_maps.items():
    for group_row in rows:
        group, count = group_row["group"], group_row["element_count"]
        for lineage in LINEAGES:
            for seed in SEEDS:
                coordinates = []
                used = set()
                for slot in range(4):
                    key = hashlib.sha256(("stage05cq_coordinate_v1" + arm + group + lineage + str(seed) + str(slot)).encode()).hexdigest()
                    index = int(key[:16], 16) % count
                    while index in old_coords[(arm, group)] or index in used: index = (index + 1) % count
                    used.add(index)
                    coordinates.append({"slot": slot, "group_flat_index": index, "key": "sha256:" + key,
                                        "excluded_historical_index_count": len(old_coords[(arm, group)])})
                blocks = []
                starts = set(); size = min(32, count)
                for slot in range(4):
                    key = hashlib.sha256(("stage05cq_block_v1" + arm + group + lineage + str(seed) + str(slot)).encode()).hexdigest()
                    full_key = "sha256:" + key
                    assert full_key not in old_block_keys and full_key not in excluded_keys
                    start = int(key[:16], 16) % count
                    while start in starts: start = (start + 1) % count
                    starts.add(start)
                    indices = [(start + offset) % count for offset in range(size)]
                    direction_key = hashlib.sha256(("stage05cq_block_direction_v1" + arm + group + lineage + str(seed) + str(slot)).encode()).digest()
                    raw = b""; counter = 0
                    while len(raw) * 8 < size:
                        raw += hashlib.sha256(direction_key + counter.to_bytes(8, "big")).digest(); counter += 1
                    bits = np.unpackbits(np.frombuffer(raw, dtype=np.uint8))[:size]
                    signs = (2 * bits.astype(int) - 1).tolist()
                    blocks.append({"slot": slot, "start": start, "indices": indices, "rademacher_signs": signs,
                                   "l2_normalization": f"sqrt({size})", "key": full_key,
                                   "direction_key": "sha256:" + direction_key.hex()})
                probe_contexts.append({"arm": arm, "group": group, "lineage": lineage, "seed": seed,
                                       "group_element_count": count, "coordinates": coordinates, "blocks": blocks})
probe_path = STAGE05CQ / "coordinate_block_sampling/preregistered_blind_probe_plan.json"
write_json(probe_path, {"schema": "sph-pio-poc.stage05cq.blind-probes.v1", "context_count": len(probe_contexts),
                        "probe_count": len(probe_contexts) * 8, "radii": RADII, "coordinates_per_context": 4,
                        "blocks_per_context": 4, "contexts": probe_contexts,
                        "stage05c_coordinate_index_overlap_count": 0, "historical_probe_identity_overlap_count": 0})

contract = {
    "contract_id": "prospective_blind_optimizer_path_confirmation_v0_1", "schema": "sph-pio-poc.stage05cq.contract.v1",
    "branch": {"user_authorized_prospective": True, "not_stage05cp": True, "not_stage05cr_continuation": True,
               "preserves_stage05c_verdict": True, "preserves_four_unresolved_probes": True},
    "backend": {"device": "CPU", "dtype": "float64", "sdpa": "SDPBackend.MATH", "flash": False, "memory_efficient": False, "automatic": False},
    "models": {"seeds": SEEDS, "manifest": str(model_path.relative_to(ROOT)), "manifest_sha256": sha_file(model_path), "checkpoint_reads": False},
    "origins": {"manifest": str(origin_path.relative_to(ROOT)), "manifest_sha256": sha_file(origin_path), "selection_salt": "stage05cq_blind_origin_v1",
                "exclude_stage05c": True, "overlap_required": 0, "lineage_batch": "2 variants x 4 origins", "global_batch": 48},
    "parameter_groups": {"manifest": str(group_path.relative_to(ROOT)), "manifest_sha256": sha_file(group_path), "unique_complete": True},
    "loss": {"s_a": 3.45632855338432798e-1, "s_a_hash": "sha256:78beec16affbae72345d220b7f7c1455f85c212ad006c4d29516946d5c76f296",
             "identity": "balanced mean ||((v_theta_next-v0_next)/dt-a_cons_star)/s_a||^2"},
    "full_gradient": {"repeats": 2, "activity_ratio_min": 100, "noise": "max(RMS(g1-g2),128*eps*max(1,RMS(g1)))", "all_rows_active": True},
    "optimizer_path": {"direction": "g_group/max(||g_group||_2,1e-30)", "theta_ref": "max(||theta_group||_2,sqrt(dim_group)*1e-3)",
                       "radii": RADII, "reverse_jvp_abs_max": 1e-10, "reverse_jvp_rel_max": 1e-7, "required_fraction": 1.0},
    "finite_difference": {"three_point": "(L(+h)-L(-h))/(2h)", "five_point": "(-L(+2h)+8L(+h)-8L(-h)+L(-2h))/(12h)",
                          "richardson": "adjacent five-point extrapolation (r^4*D_small-D_large)/(r^4-1)", "path_repeats": 2,
                          "fd_ad_abs_max": 1e-8, "fd_ad_rel_max": 1e-4, "adjacent_relative_change_max": 1e-3,
                          "richardson_relative_difference_max": 1e-3, "stable_window": "at least one adjacent radius pair (two adjacent radii) satisfying all gates",
                          "fresh_state_history": True, "complete_RK2": True, "parameter_restore": True},
    "blind_probes": {"manifest": str(probe_path.relative_to(ROOT)), "manifest_sha256": sha_file(probe_path), "coordinate_salt": "stage05cq_coordinate_v1",
                     "block_salt": "stage05cq_block_v1", "per_context": "4 coordinates + 4 blocks", "historical_overlap": 0,
                     "context_gate": ">=7/8 PASS or NEAR_ZERO_CONSISTENT and >=1 stable nonzero",
                     "group_lineage": ">=2/3 seeds", "group": "6/6 lineages", "arm": "all groups",
                     "arm_raw_rate_min": .99, "group_raw_rate_min": .98, "group_lineage_across_seeds_min": "23/24",
                     "repeat_failure_max_seeds_same_slice_or_class": 1},
    "local_descent": {"radii": [1e-6, 3e-6, 1e-5, 3e-5, 1e-4, 3e-4], "direction": "-g_all/max(||g_all||,1e-30)",
                      "ratio_range": [.2, 1.8], "lineage": "2/3 seeds for 6/6", "global": "3/3 seeds", "optimizer": False, "writeback": False},
    "structure_safety": {"contexts": "arm x seed x lineage", "force_residual_max": 1e-10,
                         "transforms": ["permutation", "edge_reorder", "translation", "Galilean", "SO2", "reflection", "periodic_shift"],
                         "positive_density": True, "finite_hidden_coefficients": True, "deterministic_graph": True, "midpoint_commit": 0},
    "resolution_diagnostics": {"N12": "6 MAIN x D1/D2/D3 x seed20500521 x one blind origin", "N16": "D3 x 6 MAIN x seed20500521 x one blind origin", "diagnostic_only": True},
    "access": {"TRAIN_only": True, "start_end_denial": True, "validation_and_sealed_decode_counts": 0},
    "resources": {"peak_rss_delta_max_bytes": 1610612736, "no_monotonic_retained_autograd": True, "no_persistent_mutation": True,
                  "no_dense_particle_N_by_N": True, "finite_completion": True, "all_hashes": True},
    "prohibitions": {"optimizer_instances": 0, "optimizer_steps": 0, "persistent_parameter_updates": 0, "training_runs": 0,
                     "neural_rollouts": 0, "performance_evaluations": 0, "checkpoint_selection": 0, "model_ranking": 0},
    "terminal_statuses": {"qualified": "PROSPECTIVE_OPTIMIZER_PATH_GRADIENT_CONFIRMATION_QUALIFIED",
                          "not_qualified": "PROSPECTIVE_OPTIMIZER_PATH_GRADIENT_CONFIRMATION_NOT_QUALIFIED",
                          "incomplete": "PROSPECTIVE_OPTIMIZER_PATH_GRADIENT_CONFIRMATION_EVIDENCE_INCOMPLETE"},
}
contract_path = STAGE05CQ / "contracts/prospective_blind_optimizer_path_confirmation_v0_1.yaml"
contract_path.write_text(yaml.safe_dump(contract, sort_keys=False, allow_unicode=True), encoding="utf-8")
inputs = [
    "stage_05_Scale_Aware_Discrete_Defect_Training/08_reports/stage05a_final_report.md",
    "stage_05_Scale_Aware_Discrete_Defect_Training/09_manifests/stage05b_final_manifest.json",
    "stage_05_Scale_Aware_Discrete_Defect_Training/09_manifests/stage05b_target_manifest.json",
    "stage_05_Scale_Aware_Discrete_Defect_Training/09_manifests/stage05b_scale_manifest.json",
    "stage_05_Scale_Aware_Discrete_Defect_Training/09_manifests/stage05b_uncertainty_manifest.json",
    "stage_05_Scale_Aware_Discrete_Defect_Training/09_manifests/stage05c_final_manifest.json",
    "stage_05_Scale_Aware_Discrete_Defect_Training/09_manifests/stage05c_probe_manifest.json",
    "stage_05_Scale_Aware_Discrete_Defect_Training/08_reports/stage05cr_final_report.md",
    "stage_05_Scale_Aware_Discrete_Defect_Training/02_optimizer_gradient_qualification/stage05cr/manifests/stage05cr_matched_control_manifest.json",
    "stage_05_Scale_Aware_Discrete_Defect_Training/02_optimizer_gradient_qualification/stage05cr/manifests/stage05cr_final_manifest.json",
    "stage_04_Local_Causal_Dynamic_Training/09_manifests/stage04b_role_assignment_manifest.json",
    "stage_04_Local_Causal_Dynamic_Training/09_manifests/stage04b_test_seal_manifest.json",
    "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c/arm_d1/model.py",
    "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c/arm_d2/model.py",
    "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c/arm_d3/model.py",
]
freeze = {"schema": "sph-pio-poc.stage05cq.freeze.v1", "contract_path": str(contract_path.relative_to(ROOT)), "contract_sha256": sha_file(contract_path),
          "frozen_before_first_blind_target_decode": True, "blind_target_decode_count_at_freeze": 0,
          "model_manifest_sha256": sha_file(model_path), "origin_manifest_sha256": sha_file(origin_path), "group_manifest_sha256": sha_file(group_path),
          "probe_manifest_sha256": sha_file(probe_path), "historical_files_modified": 0,
          "inputs": [{"path": item, "sha256": sha_file(ROOT / item), "size_bytes": (ROOT / item).stat().st_size} for item in inputs]}
write_json(STAGE05CQ / "freeze/stage05cq_freeze_record.json", freeze)
print(json.dumps({"contract_sha256": freeze["contract_sha256"], "groups": sum(len(rows) for rows in group_maps.values()),
                  "contexts": len(probe_contexts), "blind_probes": len(probe_contexts) * 8,
                  "origin_overlap": 0, "coordinate_index_overlap": 0, "probe_identity_overlap": 0}))
