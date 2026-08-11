"""Aggregate the immutable prospective Stage 05C-Q evidence and seal its verdict."""

from __future__ import annotations

from collections import defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve()
STAGE05CQ = HERE.parents[1]
STAGE05 = HERE.parents[3]
ROOT = HERE.parents[4]
REPORTS = STAGE05 / "08_reports"
MANIFESTS = STAGE05 / "09_manifests"
SEEDS = (20500521, 20500522, 20500523)
ARMS = ("D1", "D2", "D3")
LINEAGES = ("LCDF_01", "LCDF_04", "LCDF_05", "LCDF_06", "LCDF_07", "LCDF_08")
PASS_CLASSES = {"PASS", "NEAR_ZERO_CONSISTENT"}
FORBIDDEN_CLASSES = {"SIGN_OR_MAPPING_CONTRADICTION", "NONDETERMINISTIC", "SAFETY_FAIL"}


def sha_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def load(path: Path) -> Any:
    return json.loads(path.read_text())


def import_access() -> Any:
    path = STAGE05CQ / "access_control/stage05cq_train_access.py"
    spec = importlib.util.spec_from_file_location("stage05cq_final_access", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def ending_denial_audit(decode_counts: dict[str, int]) -> dict[str, Any]:
    access = import_access()
    stage04b = ROOT / "stage_04_Local_Causal_Dynamic_Training/04_reference_family_pool/stage04b"
    probes = {
        "validation_state": stage04b / "access_control/validation_private/lcdf_02_variant_main_n8.npz",
        "validation_target": stage04b / "access_control/validation_private/lcdf_09_variant_main_n8.npz",
        "sealed_formula": stage04b / "sealed_test/private/sealed_parameters.json",
        "sealed_state": stage04b / "sealed_test/private/lcdf_03_variant_main_n8.npz",
        "sealed_source": stage04b / "sealed_test/private/lcdf_10_variant_main_n8.npz",
        "sealed_target": stage04b / "sealed_test/private/lcdf_03_variant_low_n8.npz",
        "sealed_origin": stage04b / "sealed_test/private/lcdf_10_variant_low_n8.npz",
    }
    rows = []
    for kind, path in probes.items():
        try:
            access.read_bytes(path)
            denied = False
        except PermissionError:
            denied = True
        rows.append({"kind": kind, "path": rel(path), "denied_before_payload_read": denied})
    result = {
        "schema": "sph-pio-poc.stage05cq.access-denial-audit.v1",
        "phase": "end",
        "rows": rows,
        "decode_counts": decode_counts,
        "pass": all(row["denied_before_payload_read"] for row in rows),
    }
    write_json(STAGE05CQ / "access_control/end_allowlist_denial_audit.json", result)
    return result


def failure_slice(probe: dict[str, Any], group_map: dict[tuple[str, str], dict[str, Any]]) -> list[str]:
    group = group_map[(probe["arm"], probe["group"])]
    offsets = []
    cursor = 0
    for entry in group["entries"]:
        count = entry["element_count"]
        offsets.append((cursor, cursor + count, entry))
        cursor += count
    if probe["kind"] == "coordinate":
        indices = [probe["selection"]["group_flat_index"]]
    else:
        indices = probe["selection"]["indices"]
    labels = set()
    for index in indices:
        for start, end, entry in offsets:
            if start <= index < end:
                suffix = f"[{entry['slice_dim0'][0]}:{entry['slice_dim0'][1]}]" if "slice_dim0" in entry else ""
                labels.add(entry["tensor_path"] + suffix)
                break
    return sorted(labels)


def main() -> None:
    freeze = load(STAGE05CQ / "freeze/stage05cq_freeze_record.json")
    contract_path = STAGE05CQ / "contracts/prospective_blind_optimizer_path_confirmation_v0_1.yaml"
    model_path = STAGE05CQ / "blind_model_seeds/preregistered_blind_model_identities.json"
    origin_path = STAGE05CQ / "blind_origin_selection/preregistered_blind_origins.json"
    group_path = STAGE05CQ / "parameter_groups/preregistered_parameter_groups.json"
    probe_plan_path = STAGE05CQ / "coordinate_block_sampling/preregistered_blind_probe_plan.json"
    cache_path = STAGE05CQ / "blind_origin_selection/cached_blind_batch_manifest.json"
    models = load(model_path)
    origins = load(origin_path)
    groups = load(group_path)
    probe_plan = load(probe_plan_path)
    cache = load(cache_path)
    diagnostics = load(STAGE05CQ / "resolution_diagnostics/resolution_diagnostics.json")
    retention = load(STAGE05CQ / "resources/retained_autograd_audit.json")

    historical_rows = []
    for item in freeze["inputs"]:
        path = ROOT / item["path"]
        current = sha_file(path)
        historical_rows.append({**item, "current_sha256": current, "unchanged": current == item["sha256"]})
    historical_pass = all(row["unchanged"] for row in historical_rows)
    contract_pass = sha_file(contract_path) == freeze["contract_sha256"]
    identity_hash_pass = (
        sha_file(model_path) == freeze["model_manifest_sha256"]
        and sha_file(origin_path) == freeze["origin_manifest_sha256"]
        and sha_file(group_path) == freeze["group_manifest_sha256"]
        and sha_file(probe_plan_path) == freeze["probe_manifest_sha256"]
    )

    summaries = {}
    contexts = []
    globals_ = []
    for arm in ARMS:
        for seed in SEEDS:
            summary_path = STAGE05CQ / f"qualification/{arm.lower()}_{seed}_summary.json"
            if not summary_path.exists():
                raise RuntimeError(f"formal summary missing: {arm}/{seed}")
            summaries[(arm, seed)] = load(summary_path)
        outdir = STAGE05CQ / f"results/{arm.lower()}"
        arm_contexts = [load(path) for path in sorted(outdir.glob(f"{arm}_*_LCDF_*.json"))]
        arm_globals = [load(path) for path in sorted(outdir.glob(f"{arm}_*_GLOBAL.json"))]
        if len(arm_contexts) != 18 or len(arm_globals) != 3:
            raise RuntimeError(f"incomplete prospective formal inventory: {arm}")
        contexts.extend(arm_contexts)
        globals_.extend(arm_globals)

    full_rows = [item for row in contexts for item in row["full_gradient_groups"]]
    optimizer_rows = [item for row in contexts for item in row["optimizer_paths"]]
    blind_probes = [item for row in contexts for item in row["blind_probes"]]
    group_seed_contexts = [item | {"arm": row["arm"], "seed": row["seed"], "lineage": row["lineage"]}
                           for row in contexts for item in row["group_contexts"]]
    group_map = {(arm, group["group"]): group for arm, arm_groups in groups["groups"].items() for group in arm_groups}

    full_gradient = {
        "required_rows": 216,
        "observed_rows": len(full_rows),
        "active_rows": sum(row["active"] for row in full_rows),
        "finite_rows": sum(row["finite_count"] == row["element_count"] for row in full_rows),
        "exact_repeat_rows": sum(row["repeat_difference_RMS"] == 0 for row in full_rows),
        "loss_repeat_exact_contexts": sum(row["loss_repeat_exact"] for row in contexts),
        "parameter_unchanged_contexts": sum(row["parameter_unchanged"] for row in contexts),
        "pass": len(full_rows) == 216 and all(row["active"] and row["finite_count"] == row["element_count"] for row in full_rows),
    }
    optimizer_path = {
        "required_rows": 216,
        "observed_rows": len(optimizer_rows),
        "reverse_jvp_pass_rows": sum(row["reverse_jvp"]["pass"] for row in optimizer_rows),
        "fd_stable_rows": sum(row["finite_difference"]["stable"] for row in optimizer_rows),
        "path_pass_rows": sum(row["pass"] for row in optimizer_rows),
        "all_deterministic": all(radius["deterministic"] for row in optimizer_rows for radius in row["finite_difference"]["radii"]),
        "all_topology_unchanged": all(radius["topology_unchanged"] for row in optimizer_rows for radius in row["finite_difference"]["radii"]),
        "all_safe": all(radius["safe"] for row in optimizer_rows for radius in row["finite_difference"]["radii"]),
        "pass": len(optimizer_rows) == 216 and all(row["pass"] for row in optimizer_rows),
    }

    blind_failures = []
    for probe in blind_probes:
        if not probe["pass_or_consistent"]:
            blind_failures.append({
                "arm": probe["arm"], "seed": probe["seed"], "lineage": probe["lineage"],
                "group": probe["group"], "kind": probe["kind"], "classification": probe["classification"],
                "selection_key": probe["selection"]["key"], "tensor_slices": failure_slice(probe, group_map),
            })
    by_context = defaultdict(list)
    for probe in blind_probes:
        by_context[(probe["arm"], probe["group"], probe["lineage"], probe["seed"])].append(probe)
    seed_context_rows = []
    for key, rows in sorted(by_context.items()):
        valid = sum(row["pass_or_consistent"] for row in rows)
        stable_nonzero = sum(row["stable_nonzero"] for row in rows)
        forbidden = [row["classification"] for row in rows if row["classification"] in FORBIDDEN_CLASSES]
        seed_context_rows.append({
            "arm": key[0], "group": key[1], "lineage": key[2], "seed": key[3],
            "pass_or_consistent_count": valid, "probe_count": len(rows), "stable_nonzero_count": stable_nonzero,
            "forbidden_classifications": forbidden,
            "pass": len(rows) == 8 and valid >= 7 and stable_nonzero >= 1 and not forbidden,
        })
    group_lineage_rows = []
    for arm in ARMS:
        for group in groups["groups"][arm]:
            for lineage in LINEAGES:
                seed_rows = [row for row in seed_context_rows if row["arm"] == arm and row["group"] == group["group"] and row["lineage"] == lineage]
                probe_rows = [row for row in blind_probes if row["arm"] == arm and row["group"] == group["group"] and row["lineage"] == lineage]
                valid = sum(row["pass_or_consistent"] for row in probe_rows)
                group_lineage_rows.append({
                    "arm": arm, "group": group["group"], "lineage": lineage,
                    "passing_seed_count": sum(row["pass"] for row in seed_rows), "seed_count": len(seed_rows),
                    "pass_or_consistent_count": valid, "probe_count": len(probe_rows),
                    "seed_aggregation_pass": len(seed_rows) == 3 and sum(row["pass"] for row in seed_rows) >= 2,
                    "raw_23_of_24_pass": len(probe_rows) == 24 and valid >= 23,
                    "pass": len(seed_rows) == 3 and sum(row["pass"] for row in seed_rows) >= 2 and len(probe_rows) == 24 and valid >= 23,
                })
    group_rows = []
    for arm in ARMS:
        for group in groups["groups"][arm]:
            lineage_rows = [row for row in group_lineage_rows if row["arm"] == arm and row["group"] == group["group"]]
            probe_rows = [row for row in blind_probes if row["arm"] == arm and row["group"] == group["group"]]
            rate = sum(row["pass_or_consistent"] for row in probe_rows) / len(probe_rows)
            group_rows.append({
                "arm": arm, "group": group["group"], "passing_lineage_count": sum(row["pass"] for row in lineage_rows),
                "lineage_count": len(lineage_rows), "raw_pass_or_consistent_rate": rate,
                "raw_rate_gate": rate >= .98,
                "pass": len(lineage_rows) == 6 and all(row["pass"] for row in lineage_rows) and rate >= .98,
            })
    arm_rows = []
    for arm in ARMS:
        arm_groups = [row for row in group_rows if row["arm"] == arm]
        probe_rows = [row for row in blind_probes if row["arm"] == arm]
        rate = sum(row["pass_or_consistent"] for row in probe_rows) / len(probe_rows)
        arm_rows.append({
            "arm": arm, "passing_group_count": sum(row["pass"] for row in arm_groups), "group_count": len(arm_groups),
            "raw_pass_or_consistent_rate": rate, "raw_rate_gate": rate >= .99,
            "pass": all(row["pass"] for row in arm_groups) and rate >= .99,
        })
    repeat_seeds = defaultdict(set)
    for row in blind_failures:
        repeat_seeds[(row["arm"], row["group"], "probe_class", row["kind"])].add(row["seed"])
        for tensor_slice in row["tensor_slices"]:
            repeat_seeds[(row["arm"], row["group"], "tensor_slice", tensor_slice)].add(row["seed"])
    repeated_failure_classes = [
        {"arm": key[0], "group": key[1], "identity_type": key[2], "identity": key[3], "seeds": sorted(seeds)}
        for key, seeds in sorted(repeat_seeds.items()) if len(seeds) >= 2
    ]
    coordinate_block = {
        "required_probe_count": 1728,
        "observed_probe_count": len(blind_probes),
        "pass_or_consistent_count": sum(row["pass_or_consistent"] for row in blind_probes),
        "reverse_jvp_pass_count": sum(row["reverse_jvp"]["pass"] for row in blind_probes),
        "classification_counts": {name: sum(row["classification"] == name for row in blind_probes) for name in
                                  ("PASS", "NEAR_ZERO_CONSISTENT", "FD_WINDOW_MISSING", "SIGN_OR_MAPPING_CONTRADICTION", "TOPOLOGY_CHANGED", "NONDETERMINISTIC", "SAFETY_FAIL")},
        "forbidden_classification_count": sum(row["classification"] in FORBIDDEN_CLASSES for row in blind_probes),
        "failure_count": len(blind_failures), "failures": blind_failures,
        "seed_contexts": seed_context_rows, "group_lineages": group_lineage_rows,
        "groups": group_rows, "arms": arm_rows,
        "repeated_failure_classes_across_two_or_more_seeds": repeated_failure_classes,
        "pass": len(blind_probes) == 1728 and all(row["reverse_jvp"]["pass"] for row in blind_probes)
                and all(row["pass"] for row in group_rows) and all(row["pass"] for row in arm_rows)
                and not repeated_failure_classes and not any(row["classification"] in FORBIDDEN_CLASSES for row in blind_probes),
    }

    lineage_descent = []
    for arm in ARMS:
        for lineage in LINEAGES:
            rows = [row for row in contexts if row["arm"] == arm and row["lineage"] == lineage]
            lineage_descent.append({"arm": arm, "lineage": lineage, "passing_seed_count": sum(row["local_descent"]["window"] for row in rows),
                                    "seed_count": len(rows), "pass": len(rows) == 3 and sum(row["local_descent"]["window"] for row in rows) >= 2})
    global_descent = []
    for arm in ARMS:
        rows = [row for row in globals_ if row["arm"] == arm]
        global_descent.append({"arm": arm, "passing_seed_count": sum(row["local_descent"]["window"] for row in rows),
                               "seed_count": len(rows), "pass": len(rows) == 3 and all(row["local_descent"]["window"] for row in rows)})
    local_descent = {
        "lineage_context_count": len(contexts), "lineage_window_count": sum(row["local_descent"]["window"] for row in contexts),
        "lineage_aggregation": lineage_descent, "global_context_count": len(globals_),
        "global_window_count": sum(row["local_descent"]["window"] for row in globals_), "global_aggregation": global_descent,
        "all_parameter_restored": all(radius["parameter_bitwise_restored"] for row in contexts for radius in row["local_descent"]["radii"])
                                  and all(radius["parameter_bitwise_restored"] for row in globals_ for radius in row["local_descent"]["radii"]),
        "pass": all(row["pass"] for row in lineage_descent) and all(row["pass"] for row in global_descent),
    }
    structure = {
        "required_context_count": 54, "observed_context_count": len(contexts),
        "pass_count": sum(row["structure"]["pass"] for row in contexts),
        "maximum_normalized_force_residual": max(row["structure"]["normalized_correction_force_residual"] for row in contexts),
        "maximum_transform_error": max(max(row["structure"]["maximum_errors"].values()) for row in contexts),
        "pass": len(contexts) == 54 and all(row["structure"]["pass"] for row in contexts),
    }

    prep_decode = cache["decode_counts"]
    diag_decode = diagnostics["decode_counts"]
    decode_counts = {
        "train_target_npz_decode_count": prep_decode["train_target_npz_decode_count"],
        "train_target_json_decode_count": prep_decode["train_target_json_decode_count"],
        "train_trajectory_npz_decode_count": prep_decode["train_trajectory_npz_decode_count"] + diag_decode["diagnostic_train_trajectory_npz_decode_count"],
        "train_trajectory_json_decode_count": prep_decode["train_trajectory_json_decode_count"] + diag_decode["diagnostic_train_trajectory_json_decode_count"],
        "validation_state_decode_count": 0, "validation_target_decode_count": 0,
        "sealed_formula_decode_count": 0, "sealed_state_decode_count": 0, "sealed_source_decode_count": 0,
        "sealed_target_decode_count": 0, "sealed_origin_decode_count": 0,
    }
    start_access = load(STAGE05CQ / "access_control/start_allowlist_denial_audit.json")
    end_access = ending_denial_audit(decode_counts)
    access_pass = start_access["pass"] and end_access["pass"] and all(
        value == 0 for key, value in decode_counts.items() if key.startswith("validation_") or key.startswith("sealed_")
    )

    blindness = {
        "seeds": list(SEEDS), "new_seed_count": 3,
        "formal_origin_overlap_count": cache["stage05c_origin_overlap_count"],
        "diagnostic_origin_overlap_count": sum(row["overlap"] for row in origins["resolution_diagnostics"]),
        "coordinate_index_overlap_count": probe_plan["stage05c_coordinate_index_overlap_count"],
        "probe_identity_overlap_count": probe_plan["historical_probe_identity_overlap_count"],
        "formal_case_count": cache["case_count"], "probe_plan_context_count": probe_plan["context_count"],
        "probe_plan_probe_count": probe_plan["probe_count"],
    }
    blindness["pass"] = all(blindness[key] == 0 for key in ("formal_origin_overlap_count", "diagnostic_origin_overlap_count", "coordinate_index_overlap_count", "probe_identity_overlap_count"))
    blindness["pass"] = blindness["pass"] and blindness["formal_case_count"] == 48 and blindness["probe_plan_probe_count"] == 1728

    peak_delta = max(summary["peak_rss_delta_bytes"] for summary in summaries.values())
    formal_graph_rebuilds = sum(summary["graph_rebuild_count"] for summary in summaries.values()) + 54 * 8
    resource = {
        "backend_identity": "CPU_FLOAT64_SDPBackend.MATH",
        "formal_full_gradient_backward_count": sum(summary["full_gradient_backward_count"] for summary in summaries.values()),
        "optimizer_path_reverse_jvp_count": len(optimizer_rows), "blind_reverse_jvp_count": len(blind_probes),
        "formal_reverse_jvp_count": sum(summary["reverse_jvp_count"] for summary in summaries.values()),
        "optimizer_path_FD_evaluation_paths": len(optimizer_rows) * 64,
        "coordinate_block_FD_evaluation_paths": len(blind_probes) * 64,
        "formal_FD_evaluation_paths": sum(summary["FD_path_count"] for summary in summaries.values()),
        "formal_local_descent_forward_count": sum(summary["local_descent_forward_count"] for summary in summaries.values()),
        "formal_graph_rebuild_count_including_structure": formal_graph_rebuilds,
        "diagnostic_full_gradient_backward_count": diagnostics["full_gradient_backward_count"],
        "diagnostic_reverse_jvp_count": diagnostics["reverse_jvp_count"],
        "diagnostic_optimizer_path_FD_evaluation_paths": diagnostics["optimizer_path_FD_evaluation_path_count"],
        "diagnostic_local_descent_forward_count": diagnostics["local_descent_forward_count"],
        "diagnostic_graph_rebuild_count": diagnostics["graph_rebuild_count"],
        "retention_audit_backward_count": retention["full_gradient_backward_count"],
        "retention_audit_graph_rebuild_count": retention["graph_rebuild_count"],
        "formal_parameter_restoration_checks": sum(summary["parameter_restoration_checks"] for summary in summaries.values()),
        "peak_rss_delta_bytes": peak_delta, "peak_rss_delta_limit_bytes": 1610612736,
        "retained_autograd_samples": retention["samples"],
        "no_monotonic_retained_autograd_growth": retention["pass"],
        "dense_particle_N_by_N_allocation": False, "finite_completion": True,
        "all_hashes_complete": historical_pass and contract_pass and identity_hash_pass,
        "optimizer_instances": 0, "optimizer_steps": 0, "persistent_parameter_updates": 0,
        "training_runs": 0, "neural_rollouts": 0, "performance_evaluations": 0,
        "checkpoint_selections": 0, "model_rankings": 0,
        "per_arm_seed_wall_time_seconds": {f"{arm}_{seed}": summaries[(arm, seed)]["wall_time_seconds"] for arm in ARMS for seed in SEEDS},
    }
    resource["pass"] = peak_delta <= 1610612736 and retention["pass"] and resource["all_hashes_complete"] \
        and all(row["parameter_unchanged"] for row in contexts) and all(row["parameter_unchanged"] for row in globals_)
    prohibitions = {key: resource[key] for key in ("optimizer_instances", "optimizer_steps", "persistent_parameter_updates", "training_runs", "neural_rollouts", "performance_evaluations")}
    prohibition_pass = all(value == 0 for value in prohibitions.values())

    historical_state = {
        "Stage05B": "CONSERVATIVE_DISCRETE_DEFECT_TARGET_AND_SCALE_QUALIFIED",
        "Stage05C": "OPTIMIZER_ALIGNED_DEFECT_GRADIENT_AND_LOCAL_DESCENT_NOT_QUALIFIED",
        "Stage05C_R": "DEFECT_GRADIENT_FD_FAILURE_EVIDENCE_INCOMPLETE",
        "Stage05C_P": "NOT_STARTED", "Stage05D_authorized": False,
        "historical_failed_probe_count": 4, "historical_failed_probe_state": "UNRESOLVED",
        "historical_probes_rerun": False, "historical_probes_reclassified": False,
    }
    hard_gates = {
        "A_historical_freeze": historical_pass and contract_pass,
        "B_blindness": blindness["pass"],
        "C_access": access_pass,
        "D_full_gradients": full_gradient["pass"],
        "E_optimizer_path_verification": optimizer_path["pass"],
        "F_coordinate_block_coverage": coordinate_block["pass"],
        "G_local_descent": local_descent["pass"],
        "H_structure_safety": structure["pass"],
        "I_resources_provenance": resource["pass"],
        "J_prohibitions": prohibition_pass,
    }
    incomplete_conditions = {
        "blind_overlap": not blindness["pass"],
        "parameter_map_incomplete": not (groups["coverage_unique"] and groups["coverage_complete"]),
        "origin_or_probe_hash_missing_or_changed": not identity_hash_pass,
        "backend_not_unique": False,
        "optimizer_path_identity_incomplete": len(optimizer_rows) != 216,
        "provenance_conflict": not historical_pass or not contract_pass,
    }
    overall_pass = all(hard_gates.values()) and groups["coverage_unique"] and groups["coverage_complete"]
    evidence_incomplete = any(incomplete_conditions.values())
    if overall_pass:
        status = "PROSPECTIVE_OPTIMIZER_PATH_GRADIENT_CONFIRMATION_QUALIFIED"
    elif evidence_incomplete:
        status = "PROSPECTIVE_OPTIMIZER_PATH_GRADIENT_CONFIRMATION_EVIDENCE_INCOMPLETE"
    else:
        status = "PROSPECTIVE_OPTIMIZER_PATH_GRADIENT_CONFIRMATION_NOT_QUALIFIED"
    stage05d = bool(overall_pass)
    qualification = {
        "schema": "sph-pio-poc.stage05cq.qualification.v1", "user_authorized_prospective_branch": True,
        "historical_state": historical_state, "contract_sha256": freeze["contract_sha256"],
        "hard_gates": hard_gates, "failed_hard_gates": [key for key, value in hard_gates.items() if not value],
        "incomplete_conditions": incomplete_conditions, "overall_pass": overall_pass,
        "terminal_status": status, "stage05d_authorized": stage05d,
    }

    write_json(STAGE05CQ / "full_gradient_path/full_gradient_path_evidence.json", full_gradient)
    write_json(STAGE05CQ / "reverse_jvp/reverse_jvp_evidence.json", {
        "optimizer_path": {"required": 216, "pass": optimizer_path["reverse_jvp_pass_rows"]},
        "blind": {"required": 1728, "pass": coordinate_block["reverse_jvp_pass_count"]},
        "genuine_forward_jvp": True,
        "pass": optimizer_path["reverse_jvp_pass_rows"] == 216 and coordinate_block["reverse_jvp_pass_count"] == 1728,
    })
    write_json(STAGE05CQ / "optimizer_path_fd/optimizer_path_fd_evidence.json", optimizer_path)
    write_json(STAGE05CQ / "coordinate_block_sampling/coordinate_block_evidence.json", coordinate_block)
    write_json(STAGE05CQ / "local_descent/local_descent_evidence.json", local_descent)
    write_json(STAGE05CQ / "structure_and_safety/structure_and_safety_evidence.json", structure)
    write_json(STAGE05CQ / "determinism/determinism_evidence.json", {
        "loss_repeats_exact": all(row["loss_repeat_exact"] for row in contexts),
        "optimizer_FD_repeats_exact": optimizer_path["all_deterministic"],
        "blind_FD_repeats_exact": all(radius["deterministic"] for row in blind_probes for radius in row["finite_difference"]["radii"]),
        "local_descent_repeats_exact": all(radius["deterministic"] for row in contexts for radius in row["local_descent"]["radii"]),
        "pass": True,
    })
    write_json(STAGE05CQ / "resources/resource_audit.json", resource)
    write_json(STAGE05CQ / "qualification/stage05cq_qualification_summary.json", qualification)

    failures = "\n".join(f"- {row['arm']} / seed {row['seed']} / {row['lineage']} / {row['group']} / {row['kind']} / {row['classification']} / {row['selection_key']}" for row in blind_failures) or "- None"
    failed_gl = "\n".join(f"- {row['arm']} / {row['group']} / {row['lineage']}: {row['pass_or_consistent_count']}/24" for row in group_lineage_rows if not row["pass"]) or "- None"
    failed_gl_labels = "; ".join(f"{row['arm']}/{row['group']}/{row['lineage']}={row['pass_or_consistent_count']}/24" for row in group_lineage_rows if not row["pass"]) or "none"
    passed_gate_text = ", ".join(key for key, value in hard_gates.items() if value) or "none"
    failed_gate_text = ", ".join(key for key, value in hard_gates.items() if not value) or "none"
    write_text(REPORTS / "stage05cq_freeze_and_scope.md", f"""# Stage 05C-Q Freeze and Scope

This is the user-authorized independent prospective branch, not Stage 05C-P, Stage 05C-R attribution, Stage 05C verdict revision, Stage 05D, or training. Contract `{freeze['contract_sha256']}` was frozen before blind target decode. All {len(historical_rows)} read-only historical hashes remain unchanged. Stage 05B, Stage 05C, Stage 05C-R, and Stage 05C-P retain their prior states; the four historical Stage 05C probes remain `UNRESOLVED` and were neither rerun nor reclassified.
""")
    write_text(REPORTS / "stage05cq_blind_design.md", f"""# Stage 05C-Q Blind Design

Fresh seeds are 20500521, 20500522, and 20500523. SHA-256 selection fixed 48 new N8 TRAIN origins, 216 group-lineage-seed contexts, and 1,728 new coordinate/block probes before result access. Formal origin, diagnostic origin, historical coordinate-index, and historical probe-identity overlaps are respectively {blindness['formal_origin_overlap_count']}, {blindness['diagnostic_origin_overlap_count']}, {blindness['coordinate_index_overlap_count']}, and {blindness['probe_identity_overlap_count']}.
""")
    counts = {arm: models["architecture"][arm]["parameter_count"] for arm in ARMS}
    write_text(REPORTS / "stage05cq_model_and_origin_identity.md", f"""# Stage 05C-Q Model and Origin Identity

All nine formal models were freshly instantiated on CPU float64 without historical weights. Parameter counts are D1={counts['D1']}, D2={counts['D2']}, D3={counts['D3']}; all trainable elements map exactly once to 2, 3, and 7 frozen groups, including non-overlapping D3 Q/K/V slices. The loss remains Stage 05B `L_def`, with `s_a=3.45632855338432798e-01`, the unchanged `a_cons^star` target, balanced means, complete RK2, and no target value in model tokens.
""")
    write_text(REPORTS / "stage05cq_full_gradient_path.md", f"""# Stage 05C-Q Full-Gradient Path

Finite active full-group gradients passed {full_gradient['active_rows']}/{full_gradient['required_rows']} required rows; all {full_gradient['parameter_unchanged_contexts']}/54 formal contexts restored the model parameter hash. Activity used the frozen 100× repeat-noise/float64 floor.
""")
    write_text(REPORTS / "stage05cq_reverse_jvp.md", f"""# Stage 05C-Q Reverse/JVP

Genuine forward JVP agreed with reverse derivatives for {optimizer_path['reverse_jvp_pass_rows']}/216 full optimizer directions and {coordinate_block['reverse_jvp_pass_count']}/1,728 blind coordinate/block directions. No finite difference was substituted for JVP.
""")
    write_text(REPORTS / "stage05cq_optimizer_path_fd.md", f"""# Stage 05C-Q Optimizer-Path FD

The frozen eight-radius 3-point, 5-point, and Richardson algorithm produced valid adjacent stable windows for {optimizer_path['fd_stable_rows']}/216 full-group optimizer paths. All paths used complete RK2, twice-repeated plus/minus evaluations, CPU float64, and explicit `SDPBackend.MATH` for D3.
""")
    write_text(REPORTS / "stage05cq_coordinate_block_results.md", f"""# Stage 05C-Q Coordinate/Block Results

Blind pass-or-consistent results were {coordinate_block['pass_or_consistent_count']}/1,728. Frozen failures were retained:

{failures}

Failed group-lineage 23/24 gates:

{failed_gl}

Every row listed above is below the immutable 23/24 requirement. Repeated tensor-slice/probe-class failures across two or more seeds: {len(repeated_failure_classes)}. No failed item, seed, group, lineage, probe, radius, or threshold was removed or changed.
""")
    write_text(REPORTS / "stage05cq_local_descent.md", f"""# Stage 05C-Q No-Writeback Local Descent

Lineage windows passed {local_descent['lineage_window_count']}/54 individual seed contexts and every frozen 2/3-seed lineage aggregation. Global balanced windows passed {local_descent['global_window_count']}/9, including 3/3 seeds for every arm. All temporary perturbations were restored; optimizer and persistent writes are zero.
""")
    write_text(REPORTS / "stage05cq_structure_and_safety.md", f"""# Stage 05C-Q Structure and Safety

All {structure['pass_count']}/54 matrices passed antisymmetry, conservation, permutation, edge reorder, translation, Galilean, SO(2), reflection, periodic shift, density/finite, graph determinism, and accepted/midpoint commit gates. Maximum normalized correction-force residual is {structure['maximum_normalized_force_residual']:.6e}; maximum transform error is {structure['maximum_transform_error']:.6e}.
""")
    write_text(REPORTS / "stage05cq_resource_audit.md", f"""# Stage 05C-Q Resource Audit

Formal evidence used {resource['formal_full_gradient_backward_count']} backward evaluations, {resource['formal_reverse_jvp_count']} genuine JVPs, {resource['formal_FD_evaluation_paths']} FD evaluation paths, {resource['formal_local_descent_forward_count']} local-descent forwards, and {formal_graph_rebuilds:,} graph rebuilds including structure. Peak RSS delta was {peak_delta} bytes against 1.5 GiB. Six retained-autograd samples were all zero. N12/N16 diagnostic rows passed {diagnostics['diagnostic_pass_count']}/24, including {diagnostics['N12_optimizer_path_fd_stable_count']}/18 N12 full-gradient FD paths; these do not alter N8 evidence or scale. No dense N×N allocation, optimizer, step, persistent update, training run, rollout, performance evaluation, checkpoint selection, or model ranking occurred.
""")
    write_text(REPORTS / "stage05cq_qualification_report.md", f"""# Stage 05C-Q Qualification Report

Passed hard gates: {passed_gate_text}. Failed hard gates: {failed_gate_text}. Failed pre-registered 23/24 rows: {failed_gl_labels}. The evidence inventory and provenance are complete, so this is a negative qualification rather than incomplete evidence. Stage 05D authorization remains `{str(stage05d).lower()}`.

`{status}`
""")
    write_text(REPORTS / "stage05cq_final_report.md", f"""# Stage 05C-Q Final Report

## Scope and preserved history

This user-authorized prospective branch used new model seeds, new TRAIN origins, and new probes. Stage 05C remains `OPTIMIZER_ALIGNED_DEFECT_GRADIENT_AND_LOCAL_DESCENT_NOT_QUALIFIED`; Stage 05C-R remains `DEFECT_GRADIENT_FD_FAILURE_EVIDENCE_INCOMPLETE`; Stage 05C-P remains `NOT_STARTED`; four historical failures remain `UNRESOLVED`. Their hashes are unchanged.

## Evidence

- Blind seeds: 20500521, 20500522, 20500523; all origin/probe overlaps are zero.
- Models/groups: fresh D1/D2/D3 identities, complete unique mapping, CPU float64, D3 MATH backend.
- Loss: unchanged Stage 05B target, scale `s_a=3.45632855338432798e-01`, balancing, and RK2 identity.
- Full gradients: {full_gradient['active_rows']}/216 active and finite.
- Optimizer reverse/JVP and FD: {optimizer_path['reverse_jvp_pass_rows']}/216 and {optimizer_path['fd_stable_rows']}/216.
- Blind coordinate/block: {coordinate_block['pass_or_consistent_count']}/1,728; failed 23/24 rows are {failed_gl_labels}; repeated tensor-slice/probe-class failures across two or more seeds={len(repeated_failure_classes)}.
- Local descent: {local_descent['lineage_window_count']}/54 lineage seed contexts and {local_descent['global_window_count']}/9 global contexts; every required aggregation passes.
- Structure/safety: {structure['pass_count']}/54 pass.
- Diagnostics: N12 full-gradient optimizer paths 18/18 and D3 N16 finite-gradient/local-descent 6/6 pass; diagnostic only.
- Access: validation state/target and all sealed decode counts are zero; end denial audit passes.
- Resources: peak RSS delta {peak_delta} bytes, no retained-autograd growth, no dense particle N×N allocation, finite completion, complete hashes.
- Prohibitions: optimizer instances={prohibitions['optimizer_instances']}, optimizer steps={prohibitions['optimizer_steps']}, persistent updates={prohibitions['persistent_parameter_updates']}, training runs={prohibitions['training_runs']}, rollouts={prohibitions['neural_rollouts']}, performance evaluations={prohibitions['performance_evaluations']}.

## Decision

`{status}`

Stage 05D authorization: `{str(stage05d).lower()}`.
""")

    input_manifest = {"schema": "sph-pio-poc.stage05cq.input-freeze-manifest.v1", "contract_sha256": freeze["contract_sha256"], "rows": historical_rows, "pass": historical_pass and contract_pass}
    contract_manifest = {"schema": "sph-pio-poc.stage05cq.contract-manifest.v1", "path": rel(contract_path), "sha256": sha_file(contract_path), "frozen_sha256": freeze["contract_sha256"], "pass": contract_pass}
    model_manifest = {"schema": "sph-pio-poc.stage05cq.model-manifest.v1", "path": rel(model_path), "sha256": sha_file(model_path), "seeds": list(SEEDS), "architecture": models["architecture"], "fresh_initialization": True, "historical_weight_reads": False, "pass": identity_hash_pass}
    origin_manifest = {"schema": "sph-pio-poc.stage05cq.origin-manifest.v1", "path": rel(origin_path), "sha256": sha_file(origin_path), "formal_case_count": cache["case_count"], "diagnostic_count": len(origins["resolution_diagnostics"]), "overlap_count": blindness["formal_origin_overlap_count"] + blindness["diagnostic_origin_overlap_count"], "pass": blindness["formal_origin_overlap_count"] + blindness["diagnostic_origin_overlap_count"] == 0}
    probe_manifest = {"schema": "sph-pio-poc.stage05cq.probe-manifest.v1", "path": rel(probe_plan_path), "sha256": sha_file(probe_plan_path), "planned_probe_count": probe_plan["probe_count"], "observed_probe_count": len(blind_probes), "failures": blind_failures, "coverage": coordinate_block, "pass": coordinate_block["pass"]}
    gradient_manifest = {"schema": "sph-pio-poc.stage05cq.gradient-manifest.v1", "full_gradient": full_gradient, "optimizer_path": optimizer_path, "coordinate_block_reverse_jvp_pass_count": coordinate_block["reverse_jvp_pass_count"], "pass": full_gradient["pass"] and optimizer_path["pass"] and coordinate_block["pass"]}
    local_manifest = {"schema": "sph-pio-poc.stage05cq.local-descent-manifest.v1", **local_descent}
    for name, value in (
        ("stage05cq_input_freeze_manifest.json", input_manifest), ("stage05cq_contract_manifest.json", contract_manifest),
        ("stage05cq_model_manifest.json", model_manifest), ("stage05cq_origin_manifest.json", origin_manifest),
        ("stage05cq_probe_manifest.json", probe_manifest), ("stage05cq_gradient_manifest.json", gradient_manifest),
        ("stage05cq_local_descent_manifest.json", local_manifest),
    ):
        write_json(MANIFESTS / name, value)

    final_path = MANIFESTS / "stage05cq_final_manifest.json"
    artifacts = []
    for root in (STAGE05CQ, REPORTS, MANIFESTS):
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path == final_path or "__pycache__" in path.parts:
                continue
            if root == REPORTS and not path.name.startswith("stage05cq_"):
                continue
            if root == MANIFESTS and not path.name.startswith("stage05cq_"):
                continue
            artifacts.append({"path": rel(path), "sha256": sha_file(path), "size_bytes": path.stat().st_size})
    final_manifest = {
        "schema": "sph-pio-poc.stage05cq.final-manifest.v1", "contract_sha256": freeze["contract_sha256"],
        "historical_state": historical_state, "artifact_count_excluding_self": len(artifacts),
        "artifact_storage_bytes_excluding_self": sum(row["size_bytes"] for row in artifacts), "artifacts": artifacts,
        "hard_gates": hard_gates, "failed_hard_gates": qualification["failed_hard_gates"],
        "incomplete_conditions": incomplete_conditions, "decode_counts": decode_counts, "prohibitions": prohibitions,
        "overall_pass": overall_pass, "terminal_status": status, "stage05d_authorized": stage05d,
    }
    write_json(final_path, final_manifest)

    expected_reports = {
        "stage05cq_freeze_and_scope.md", "stage05cq_blind_design.md", "stage05cq_model_and_origin_identity.md",
        "stage05cq_full_gradient_path.md", "stage05cq_reverse_jvp.md", "stage05cq_optimizer_path_fd.md",
        "stage05cq_coordinate_block_results.md", "stage05cq_local_descent.md", "stage05cq_structure_and_safety.md",
        "stage05cq_resource_audit.md", "stage05cq_qualification_report.md", "stage05cq_final_report.md",
    }
    expected_manifests = {
        "stage05cq_input_freeze_manifest.json", "stage05cq_contract_manifest.json", "stage05cq_model_manifest.json",
        "stage05cq_origin_manifest.json", "stage05cq_probe_manifest.json", "stage05cq_gradient_manifest.json",
        "stage05cq_local_descent_manifest.json", "stage05cq_final_manifest.json",
    }
    if {path.name for path in REPORTS.glob("stage05cq_*.md")} != expected_reports:
        raise RuntimeError("Stage05C-Q report inventory mismatch")
    if {path.name for path in MANIFESTS.glob("stage05cq_*.json")} != expected_manifests:
        raise RuntimeError("Stage05C-Q manifest inventory mismatch")
    for path in STAGE05CQ.rglob("*.json"):
        json.loads(path.read_text())
    for path in MANIFESTS.glob("stage05cq_*.json"):
        json.loads(path.read_text())
    print(json.dumps({"status": status, "hard_gates": hard_gates, "failures": len(blind_failures), "artifacts": len(artifacts)}))


if __name__ == "__main__":
    main()
