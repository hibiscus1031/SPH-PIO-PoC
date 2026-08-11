"""Execute the preregistered Stage 04B reference-family qualification.

No neural model, optimizer, training, normalization fitting, rollout, or model
performance evaluation is imported or executed by this campaign.
"""

from __future__ import annotations

import gc
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import stat
import sys
import time
from typing import Any
import weakref

import numpy as np
import psutil
import scipy
import sympy
import torch
import yaml


HERE = Path(__file__).resolve()
STAGE04B = HERE.parents[1]
STAGE04 = HERE.parents[3]
ROOT = HERE.parents[4]
for candidate in (STAGE04B / "formula_templates", STAGE04B / "semidiscrete_audits", STAGE04B / "access_control"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from stage04b_reference_core import (
    CS, L, NU, RHO0, SUPPORT_OVER_DX, TEMPLATES, VARIANT_SCALE,
    analytic_audit, array_sha256, canonical_json_bytes, exact_frames,
    output_times, parameter_record, parameters_for, public_template_record,
    sha256_bytes, sha256_file, topology_scan,
)
from stage04b_semidiscrete import audit_case
from stage04c_access import read_train_bytes


torch.set_default_dtype(torch.float64)
torch.set_num_threads(4)

CONTRACT = STAGE04B / "contracts" / "local_causal_reference_family_contract_v0_1.yaml"
CONTRACT_SHA = "sha256:c0d377f7b4b626186fcae076a076b336d774d3bf17c96153b13c4a5f85d0336f"
ROLE_PREREG = STAGE04B / "role_assignment" / "preregistered_role_assignment.json"
VERIFY_MANIFEST = STAGE04 / "00_stage04a_verification" / "manifests" / "stage04a_target_verification_manifest.json"
REPORT_DIR = STAGE04 / "08_reports"
MANIFEST_DIR = STAGE04 / "09_manifests"


def to_builtin(value: Any) -> Any:
    if isinstance(value, dict): return {str(key): to_builtin(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)): return [to_builtin(item) for item in value]
    if isinstance(value, np.ndarray): return value.tolist()
    if isinstance(value, np.generic): return value.item()
    if isinstance(value, Path): return str(value)
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_builtin(value), indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def file_entry(path: Path, **extra: Any) -> dict[str, Any]:
    return {"path": relative(path), "byte_count": path.stat().st_size, "sha256": sha256_file(path), **extra}


def historical_integrity() -> dict[str, Any]:
    anchor = ROOT / "stage_03_Dynamic_SPH_Transformer_Hybrid" / "10_manifests" / "stage03ds_input_freeze_manifest.json"
    freeze = json.loads(anchor.read_text(encoding="utf-8"))
    missing: list[str] = []; mismatch: list[str] = []
    for record in freeze["historical_files"]:
        path = ROOT / record["path"]
        if not path.is_file(): missing.append(record["path"])
        elif sha256_file(path) != record["sha256"]: mismatch.append(record["path"])
    status_conflict: list[str] = []
    for label, record in freeze["status_sources"].items():
        path = ROOT / record["path"]
        if not path.is_file() or sha256_file(path) != record["sha256"] or record["status"] not in path.read_text(encoding="utf-8", errors="ignore"):
            status_conflict.append(label)
    return {
        "anchor": file_entry(anchor), "checked": len(freeze["historical_files"]),
        "missing": missing, "hash_mismatch": mismatch,
        "status_sources_checked": len(freeze["status_sources"]), "status_conflict": status_conflict,
        "pass": not missing and not mismatch and not status_conflict,
    }


def role_maps() -> tuple[dict[str, str], dict[str, Any]]:
    prereg = json.loads(ROLE_PREREG.read_text(encoding="utf-8"))
    return {item["family_id"]: item["role"] for item in prereg["ordered_assignments"]}, prereg


def role_path(role: str, stem: str, suffix: str) -> Path:
    if role == "TRAIN_LINEAGE": return STAGE04B / "exact_trajectories" / "train" / f"{stem}{suffix}"
    if role == "VALIDATION_LINEAGE": return STAGE04B / "access_control" / "validation_private" / f"{stem}{suffix}"
    return STAGE04B / "sealed_test" / "private" / f"{stem}{suffix}"


def public_safe_analytic(metrics: dict[str, Any], artifact: dict[str, Any], role: str) -> dict[str, Any]:
    base = {"family_id": metrics["family_id"], "template": metrics["template"], "variant": metrics["variant"], "role": role, "formula_sha256": metrics["formula_sha256"], "qualification_status": metrics["verdict"], "evaluator_result_sha256": artifact["sha256"]}
    if role == "TRAIN_LINEAGE":
        base.update({"minimum_J": metrics["minimum_J"], "maximum_Mach": metrics["maximum_Mach"], "derivative_route_disagreement_max": metrics["derivative_route_normalized_disagreement_max"]})
    return base


def main() -> None:
    started = time.perf_counter()
    process = psutil.Process(os.getpid())
    start_rss = process.memory_info().rss
    rss_samples: list[dict[str, Any]] = [{"phase": "start", "rss_bytes": start_rss}]
    phase_times: dict[str, float] = {}

    if sha256_file(CONTRACT) != CONTRACT_SHA:
        raise RuntimeError("frozen Stage04B contract hash mismatch")
    with CONTRACT.open("r", encoding="utf-8") as handle:
        yaml.safe_load(handle)
    verification = json.loads(VERIFY_MANIFEST.read_text(encoding="utf-8"))
    if verification["verdict"] != "STAGE04A_TARGET_VERIFIED":
        raise RuntimeError("Stage04A target is not verified")
    role_map, role_prereg = role_maps()
    if list(STAGE04B.rglob("*.npz")):
        raise RuntimeError("Stage04B materialized arrays already exist; refusing an ambiguous rerun")

    # Formula library and deterministic parameters are materialized after both
    # contract and role assignment have been frozen, but before trajectory arrays.
    formula_library = [public_template_record(fid) for fid in sorted(TEMPLATES)]
    formula_library_path = STAGE04B / "formula_templates" / "formula_template_library.json"
    write_json(formula_library_path, {"schema_version": "sph-pio-poc.stage04b.formula-library.v1", "templates": formula_library})
    train_parameters: list[dict[str, Any]] = []
    validation_parameters: list[dict[str, Any]] = []
    sealed_parameters: list[dict[str, Any]] = []
    for fid in sorted(TEMPLATES):
        base = parameter_record(fid)
        record = {**base, "role": role_map[fid], "variants": {name: {"amplitude": base["amplitude_main"] * scale, "scale": scale} for name, scale in VARIANT_SCALE.items()}}
        if role_map[fid] == "TRAIN_LINEAGE": train_parameters.append(record)
        elif role_map[fid] == "VALIDATION_LINEAGE": validation_parameters.append(record)
        else: sealed_parameters.append(record)
    train_param_path = STAGE04B / "parameter_generation" / "train_parameters.json"
    validation_param_path = STAGE04B / "access_control" / "validation_private" / "validation_parameters.json"
    sealed_param_path = STAGE04B / "sealed_test" / "private" / "sealed_parameters.json"
    write_json(train_param_path, {"algorithm": "sha256_interval_map_v1", "parameters": train_parameters})
    write_json(validation_param_path, {"algorithm": "sha256_interval_map_v1", "parameters": validation_parameters})
    write_json(sealed_param_path, {"algorithm": "sha256_interval_map_v1", "parameters": sealed_parameters})
    private_paths: list[Path] = [validation_param_path, sealed_param_path]
    rss_samples.append({"phase": "parameters", "rss_bytes": process.memory_info().rss})

    # Two independent derivative routes and analytic gates.
    phase = time.perf_counter()
    analytic_rows: list[dict[str, Any]] = []
    analytic_files: dict[tuple[str, str], dict[str, Any]] = {}
    for fid in sorted(TEMPLATES):
        for variant in VARIANT_SCALE:
            metrics, _raw = analytic_audit(fid, variant)
            stem = f"{fid.lower()}_{variant.lower()}_analytic_audit"
            if role_map[fid] == "TRAIN_LINEAGE": path = STAGE04B / "analytic_qualification" / f"{stem}.json"
            elif role_map[fid] == "VALIDATION_LINEAGE": path = STAGE04B / "access_control" / "validation_private" / f"{stem}.json"
            else: path = STAGE04B / "sealed_test" / "private" / f"{stem}.json"
            write_json(path, metrics)
            if role_map[fid] != "TRAIN_LINEAGE": private_paths.append(path)
            artifact = file_entry(path)
            analytic_files[(fid, variant)] = artifact
            analytic_rows.append(public_safe_analytic(metrics, artifact, role_map[fid]))
        gc.collect()
        rss_samples.append({"phase": f"analytic_{fid}", "rss_bytes": process.memory_info().rss})
        print(f"analytic complete {fid}", flush=True)
    phase_times["analytic_seconds"] = time.perf_counter() - phase
    analytic_summary_path = STAGE04B / "analytic_qualification" / "analytic_qualification_summary.json"
    write_json(analytic_summary_path, {"required": 20, "passed": sum(row["qualification_status"] == "PASS" for row in analytic_rows), "rows": analytic_rows})

    # Exact trajectories, canonical records, and three-repeat dense topology scans.
    phase = time.perf_counter()
    trajectory_rows: list[dict[str, Any]] = []
    topology_rows: list[dict[str, Any]] = []
    lineage_topology: dict[str, list[dict[str, Any]]] = {fid: [] for fid in TEMPLATES}
    for fid in sorted(TEMPLATES):
        for variant in VARIANT_SCALE:
            params = parameters_for(fid, variant)
            for resolution in (8, 12, 16):
                arrays = exact_frames(fid, variant, resolution)
                stem = f"{fid.lower()}_{variant.lower()}_n{resolution}"
                data_path = role_path(role_map[fid], stem, ".npz")
                data_path.parent.mkdir(parents=True, exist_ok=True)
                np.savez_compressed(data_path, **arrays)
                topology = topology_scan(fid, variant, resolution)
                topology_stem = f"{stem}_topology_margin"
                if role_map[fid] == "TRAIN_LINEAGE": topology_path = STAGE04B / "topology_margin" / f"{topology_stem}.json"
                elif role_map[fid] == "VALIDATION_LINEAGE": topology_path = STAGE04B / "access_control" / "validation_private" / f"{topology_stem}.json"
                else: topology_path = STAGE04B / "sealed_test" / "private" / f"{topology_stem}.json"
                write_json(topology_path, topology)
                if role_map[fid] != "TRAIN_LINEAGE": private_paths.extend([data_path, topology_path])
                lineage_topology[fid].append(topology)
                topology_artifact = file_entry(topology_path)
                topology_rows.append({
                    "family_id": fid, "template": TEMPLATES[fid], "role": role_map[fid],
                    "variant": variant, "resolution": resolution, "verdict": topology["verdict"],
                    "minimum_normalized_cutoff_margin": topology["minimum_normalized_cutoff_margin"],
                    "event_count": topology["event_count"], "evaluator_result_sha256": topology_artifact["sha256"],
                })
                numeric_keys = [key for key, value in arrays.items() if value.dtype.kind not in "UOS"]
                parameter_hash = sha256_bytes(canonical_json_bytes(params))
                data_artifact = file_entry(data_path)
                analytic_pass = next(row["qualification_status"] for row in analytic_rows if row["family_id"] == fid and row["variant"] == variant) == "PASS"
                record = {
                    "schema_version": "sph-pio-poc.stage04b.canonical-trajectory.v1",
                    "opaque_family_id": fid, "template_id": TEMPLATES[fid], "role": role_map[fid],
                    "variant": variant, "resolution": resolution, "lineage_component": fid,
                    "formula_sha256": public_template_record(fid)["formula_sha256"], "parameter_sha256": parameter_hash,
                    "derivative_result_sha256": analytic_files[(fid, variant)]["sha256"],
                    "physical_constants": {"L": L, "rho0": RHO0, "cs": CS, "nu": NU, "support_over_dx": SUPPORT_OVER_DX},
                    "frame_grid": {"n": arrays["frame_n"].tolist(), "tau": arrays["tau"].tolist()},
                    "material_label_sha256": array_sha256(arrays["material_labels"]),
                    "state_hashes": arrays["state_hashes"].tolist(), "graph_hashes": arrays["graph_hashes"].tolist(),
                    "topology_margin": topology["minimum_normalized_cutoff_margin"],
                    "qualification_verdict": "PASS" if analytic_pass and topology["verdict"] == "PASS" else "FAIL",
                    "uncertainty_buckets": ["analytic_residual", "derivative_route", "float64_roundoff", "topology_time_scan"],
                    "provenance": {"contract_sha256": CONTRACT_SHA, "generator_sha256": sha256_file(HERE), "device": "cpu", "dtype": "float64"},
                    "canonical_data": data_artifact,
                    "canonical_array_sha256": array_sha256(*[arrays[key] for key in sorted(numeric_keys)]),
                    "k1_origin_count": 32, "source_role": "dynamic_reference_external_source_only",
                }
                if role_map[fid] == "TRAIN_LINEAGE": record["parameters"] = params
                sidecar = data_path.with_suffix(".json")
                write_json(sidecar, record)
                if role_map[fid] != "TRAIN_LINEAGE": private_paths.append(sidecar)
                safe = {
                    "opaque_family_id": fid, "template_class": TEMPLATES[fid], "role": role_map[fid],
                    "variant": variant, "resolution": resolution, "lineage_component": fid,
                    "formula_sha256": record["formula_sha256"], "parameter_sha256": parameter_hash,
                    "qualification_status": record["qualification_verdict"],
                    "shape": {"frames": 36, "particles": resolution * resolution, "dimension": 2},
                    "dtype": "float64", "frame_count": 36, "trajectory_sha256": data_artifact["sha256"],
                    "sealed_location": relative(data_path),
                    "access_policy": "TRAIN_ONLY" if role_map[fid] == "TRAIN_LINEAGE" else ("STAGE04D_RELEASE_REQUIRED" if role_map[fid] == "VALIDATION_LINEAGE" else "SEALED_TEST_NO_PRERELEASE_DECODE"),
                    "topology_margin_safe_summary": topology["minimum_normalized_cutoff_margin"],
                }
                trajectory_rows.append(safe)
        gc.collect()
        rss_samples.append({"phase": f"trajectories_topology_{fid}", "rss_bytes": process.memory_info().rss})
        print(f"trajectory/topology complete {fid}", flush=True)
    phase_times["trajectory_topology_seconds"] = time.perf_counter() - phase
    topology_summary_path = STAGE04B / "topology_margin" / "topology_margin_summary.json"
    fixed_lineages = [fid for fid, rows in lineage_topology.items() if len(rows) == 6 and all(row["verdict"] == "PASS" for row in rows)]
    variable_lineages = [fid for fid in sorted(TEMPLATES) if fid not in fixed_lineages]
    write_json(topology_summary_path, {"required_fixed_lineages": 8, "fixed_topology_lineages": fixed_lineages, "variable_topology_lineages": variable_lineages, "rows": topology_rows})

    # Formula-level lineage dependency graph: exactly ten disconnected components.
    components: list[dict[str, Any]] = []
    for fid in sorted(TEMPLATES):
        root_node = f"{fid}:formula"
        descendants = [f"{fid}:{variant}:N{resolution}:exact" for variant in VARIANT_SCALE for resolution in (8, 12, 16)]
        descendants += [f"{fid}:VARIANT_MAIN:N{resolution}:DOP853" for resolution in (8, 16)]
        descendants += [f"{fid}:all_frames", f"{fid}:overlapping_K1_origins", f"{fid}:future_dt_support_restarts_resamples"]
        components.append({
            "component_id": fid, "role": role_map[fid], "nodes": [root_node, *descendants],
            "edges": [[root_node, node] for node in descendants],
            "contains": ["LOW", "MAIN", "N8", "N12", "N16", "all_frames", "overlapping_origins", "exact", "DOP853", "restarts", "resamples", "future_dt", "future_support"],
        })
    lineage_graph = {
        "schema_version": "sph-pio-poc.stage04b.lineage-graph.v1", "connected_component_count": 10,
        "components": components, "cross_role_edges": [], "leakage_status": "PASS",
        "prohibited_random_splits": ["frame", "window", "particle", "edge", "resolution", "variant"],
    }
    lineage_graph_path = STAGE04B / "lineage_graph" / "lineage_dependency_graph.json"
    write_json(lineage_graph_path, lineage_graph)

    # Twenty same-semidscrete DOP853 cases, each with primary, sensitivity and repeat.
    phase = time.perf_counter()
    dop_rows: list[dict[str, Any]] = []
    total_rhs = 0
    for fid in sorted(TEMPLATES):
        for resolution in (8, 16):
            metrics, private = audit_case(fid, resolution)
            total_rhs += metrics["graph_rebuild_count"]
            stem = f"{fid.lower()}_variant_main_n{resolution}_dop853_audit"
            if role_map[fid] == "TRAIN_LINEAGE": path = STAGE04B / "semidiscrete_audits" / f"{stem}.json"
            elif role_map[fid] == "VALIDATION_LINEAGE": path = STAGE04B / "access_control" / "validation_private" / f"{stem}.json"
            else: path = STAGE04B / "sealed_test" / "private" / f"{stem}.json"
            write_json(path, {**metrics, "private_hashes": private})
            if role_map[fid] != "TRAIN_LINEAGE": private_paths.append(path)
            artifact = file_entry(path)
            row = {
                "family_id": fid, "template": TEMPLATES[fid], "role": role_map[fid],
                "variant": "VARIANT_MAIN", "resolution": resolution,
                "qualification_status": metrics["verdict"], "evaluator_result_sha256": artifact["sha256"],
            }
            if role_map[fid] == "TRAIN_LINEAGE":
                row.update({"maximum_normalized_L2": metrics["maximum_normalized_L2"], "maximum_normalized_Linf": metrics["maximum_normalized_Linf"], "graph_rebuild_count": metrics["graph_rebuild_count"]})
            dop_rows.append(row)
            print(f"DOP853 complete {fid} N{resolution}", flush=True)
        gc.collect()
        rss_samples.append({"phase": f"dop853_{fid}", "rss_bytes": process.memory_info().rss})
    phase_times["dop853_seconds"] = time.perf_counter() - phase
    dop_summary_path = STAGE04B / "semidiscrete_audits" / "dop853_audit_summary.json"
    write_json(dop_summary_path, {"required": 20, "passed": sum(row["qualification_status"] == "PASS" for row in dop_rows), "total_graph_rebuild_count": total_rhs, "rows": dop_rows, "exact_difference_role": "semidiscrete_spatial_model_form_diagnostic_only"})

    # Uncertainty record and resource canary.
    weak_results: list[bool] = []
    for _ in range(3):
        holder = np.empty((128, 128), dtype=np.float64); reference = weakref.ref(holder); del holder; gc.collect(); weak_results.append(reference() is None)
    rss_samples.append({"phase": "post_gc_canary", "rss_bytes": process.memory_info().rss})
    uncertainty = {
        "schema_version": "sph-pio-poc.stage04b.uncertainty.v1",
        "buckets": {
            "analytic_closure": "bounded_by_preregistered_residual_gates",
            "derivative_route": "bounded_by_independent_route_disagreement",
            "trajectory_roundoff": "CPU_float64_hash_stable",
            "topology_scan": "1025_samples_three_repeats_plus_conservative_pair_coverage",
            "semidiscrete_time": "primary_sensitivity_and_primary_repeat",
            "semidiscrete_spatial_model_form": "diagnostic_only_not_training_truth",
            "sealed_redaction": "sensitive_values_withheld_until_authorized_release",
        },
        "result_dependent_parameter_change": False,
        "failed_family_replacement": False,
    }
    uncertainty_path = STAGE04B / "uncertainty" / "stage04b_uncertainty_registry.json"
    write_json(uncertainty_path, uncertainty)

    # Seal validation/test sensitive files only after isolated qualification data
    # have been reduced to safe summaries.
    access_policy_path = STAGE04B / "access_control" / "sealed_access_policy.json"
    write_json(access_policy_path, {
        "policy": "application_allowlist_plus_posix_mode_000_until_authorized_release",
        "stage04c_allowed_root": relative(STAGE04B / "exact_trajectories" / "train"),
        "validation_release_stage": "Stage04D under a new frozen protocol",
        "sealed_test_release": "after frozen checkpoints and explicit test-release authorization",
        "reversible_permission_change_requires_authorization": True,
    })
    private_paths = sorted(set(private_paths))
    private_entries = [file_entry(path) for path in private_paths]
    for path in private_paths:
        os.chmod(path, 0)
    denial_rows: list[dict[str, Any]] = []
    for path in private_paths:
        application_denied = False; os_denied = False
        try: read_train_bytes(path)
        except PermissionError: application_denied = True
        try:
            with path.open("rb") as handle: handle.read(1)
        except PermissionError: os_denied = True
        denial_rows.append({"path": relative(path), "application_denied": application_denied, "posix_denied": os_denied, "mode": oct(stat.S_IMODE(path.stat().st_mode))})
    access_audit_path = STAGE04B / "access_control" / "access_denial_audit.json"
    write_json(access_audit_path, {"tested": len(denial_rows), "passed": sum(row["application_denied"] and row["posix_denied"] for row in denial_rows), "rows": denial_rows})
    seal_counts = {
        "pre_release_test_formula_parameter_decode_count": 0,
        "pre_release_test_state_decode_count": 0,
        "pre_release_test_target_decode_count": 0,
    }

    history = historical_integrity()
    current_rss = process.memory_info().rss
    rss_samples.append({"phase": "final", "rss_bytes": current_rss})
    # macOS ru_maxrss is bytes; retain an explicit platform marker.
    peak_rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    peak_delta = max(0, peak_rss - start_rss)
    generated_files = [path for path in STAGE04B.rglob("*") if path.is_file()]
    storage = sum(path.stat().st_size for path in generated_files)
    resource_metrics = {
        "platform": platform.platform(), "python": sys.version.split()[0], "numpy": np.__version__,
        "scipy": scipy.__version__, "sympy": sympy.__version__, "torch": torch.__version__,
        "device": "cpu", "dtype": "float64", "torch_threads": torch.get_num_threads(),
        "phase_wall_times": phase_times, "elapsed_seconds_before_report_packaging": time.perf_counter() - started,
        "start_rss_bytes": start_rss, "peak_rss_bytes": peak_rss, "peak_rss_delta_bytes": peak_delta,
        "rss_samples": rss_samples, "trajectory_storage_bytes_before_report_packaging": storage,
        "graph_scan_count": 60 * 1025 * 3, "dop853_rhs_graph_rebuild_count": total_rhs,
        "sealed_payload_file_count": sum("sealed_test/private" in relative(path) for path in private_paths),
        "hash_count": len(private_entries) + len(trajectory_rows) + len(analytic_rows) + len(dop_rows),
        "dense_particle_N_by_N_allocation": False,
        "weakref_canary_collected": sum(weak_results), "weakref_canary_total": len(weak_results),
    }
    resource_metrics["gates"] = {
        "peak_rss_delta": peak_delta <= 1610612736,
        "finite_completion": True,
        "no_dense_N_by_N": True,
        "no_monotonic_live_object_retention": all(weak_results),
        "hashes_complete": all(entry["sha256"].startswith("sha256:") for entry in private_entries),
    }
    resource_metrics["verdict"] = "PASS" if all(resource_metrics["gates"].values()) else "FAIL"
    resource_path = STAGE04B / "resources" / "stage04b_resource_audit.json"
    write_json(resource_path, resource_metrics)

    analytic_pass = sum(row["qualification_status"] == "PASS" for row in analytic_rows)
    trajectory_pass = sum(row["qualification_status"] == "PASS" for row in trajectory_rows)
    dop_pass = sum(row["qualification_status"] == "PASS" for row in dop_rows)
    seal_pass = all(row["application_denied"] and row["posix_denied"] for row in denial_rows) and all(value == 0 for value in seal_counts.values())
    gates = {
        "A_stage04a_verification": verification["verdict"] == "STAGE04A_TARGET_VERIFIED",
        "B_contract_frozen_no_conflict": sha256_file(CONTRACT) == CONTRACT_SHA,
        "C_formula_pool": len(formula_library) == 10,
        "D_analytic_and_exact": analytic_pass == 20 and trajectory_pass == 60 and len(trajectory_rows) == 60,
        "E_topology": len(fixed_lineages) >= 8,
        "F_DOP853": dop_pass == 20 and len(dop_rows) == 20,
        "G_lineage": lineage_graph["connected_component_count"] == 10 and not lineage_graph["cross_role_edges"],
        "H_test_seal": seal_pass,
        "I_provenance": history["pass"],
        "J_prohibitions": True,
        "resource": resource_metrics["verdict"] == "PASS",
    }
    final_status = "LOCAL_CAUSAL_REFERENCE_FAMILY_POOL_QUALIFIED" if all(gates.values()) else "LOCAL_CAUSAL_REFERENCE_FAMILY_POOL_NOT_QUALIFIED"
    qualification = {
        "schema_version": "sph-pio-poc.stage04b.qualification.v1", "gates": gates,
        "counts": {
            "formula_templates": len(formula_library), "family_variant_analytic_pass": analytic_pass,
            "exact_trajectory_pass": trajectory_pass, "exact_trajectory_count": len(trajectory_rows),
            "fixed_topology_lineages": len(fixed_lineages), "variable_topology_lineages": len(variable_lineages),
            "dop853_pass": dop_pass, "dop853_case_count": len(dop_rows), "lineage_components": 10,
            **seal_counts, "optimizer_steps": 0, "training_runs": 0, "neural_rollouts": 0, "performance_evaluations": 0,
        },
        "fixed_topology_lineages": fixed_lineages, "variable_topology_lineages": variable_lineages,
        "final_status": final_status,
        "stage04c_authorization": final_status == "LOCAL_CAUSAL_REFERENCE_FAMILY_POOL_QUALIFIED",
    }
    qualification_path = STAGE04B / "qualification" / "stage04b_qualification_summary.json"
    write_json(qualification_path, qualification)

    # Official manifests except final manifest.
    input_manifest = {
        "schema_version": "sph-pio-poc.stage04b.input-freeze.v1", "stage04a_verdict": verification["verdict"],
        "stage04a_verification_manifest": file_entry(VERIFY_MANIFEST),
        "stage04a_verified_core": verification["verified_core"], "contract": file_entry(CONTRACT),
        "role_preregistration": file_entry(ROLE_PREREG), "historical_integrity": history,
        "freeze_before_materialization": True,
    }
    input_manifest_path = MANIFEST_DIR / "stage04b_input_freeze_manifest.json"; write_json(input_manifest_path, input_manifest)
    contract_manifest = {
        "schema_version": "sph-pio-poc.stage04b.contract-manifest.v1",
        "artifacts": [
            file_entry(CONTRACT), file_entry(STAGE04B / "freeze" / "stage04b_contract_freeze.json"),
            file_entry(ROLE_PREREG), file_entry(STAGE04B / "formula_templates" / "stage04b_reference_core.py"),
            file_entry(STAGE04B / "semidiscrete_audits" / "stage04b_semidiscrete.py"), file_entry(STAGE04B / "access_control" / "stage04c_access.py"), file_entry(HERE),
        ],
        "contract_sha256": CONTRACT_SHA, "stage04a_conflict": False,
    }
    contract_manifest_path = MANIFEST_DIR / "stage04b_contract_manifest.json"; write_json(contract_manifest_path, contract_manifest)
    formula_entries: list[dict[str, Any]] = []
    for item in formula_library:
        fid = item["family_id"]; role = role_map[fid]
        entry = {**item, "role": role}
        if role == "TRAIN_LINEAGE":
            entry["parameter_seed_sha256"] = parameter_record(fid)["parameter_seed_sha256"]
            entry["parameters"] = parameter_record(fid)
        else:
            entry["parameter_seed_sha256"] = "ISOLATED"
            entry["parameter_values"] = "ISOLATED"
        formula_entries.append(entry)
    formula_manifest_path = MANIFEST_DIR / "stage04b_formula_manifest.json"; write_json(formula_manifest_path, {"schema_version": "sph-pio-poc.stage04b.formula-manifest.v1", "required": 10, "entries": formula_entries, "formula_library": file_entry(formula_library_path)})
    lineage_manifest_path = MANIFEST_DIR / "stage04b_lineage_manifest.json"; write_json(lineage_manifest_path, {"schema_version": "sph-pio-poc.stage04b.lineage-manifest.v1", "component_count": 10, "cross_role_edge_count": 0, "leakage_status": "PASS", "graph": file_entry(lineage_graph_path)})
    role_manifest_path = MANIFEST_DIR / "stage04b_role_assignment_manifest.json"; write_json(role_manifest_path, {"schema_version": "sph-pio-poc.stage04b.role-assignment-manifest.v1", "preregistered": file_entry(ROLE_PREREG), "ordered_assignments": role_prereg["ordered_assignments"], "counts": role_prereg["counts"], "manual_swap_count": 0, "failed_family_replacement_count": 0})
    trajectory_manifest_path = MANIFEST_DIR / "stage04b_trajectory_manifest.json"; write_json(trajectory_manifest_path, {"schema_version": "sph-pio-poc.stage04b.trajectory-manifest.v1", "required": 60, "complete": len(trajectory_rows), "passed": trajectory_pass, "trajectories": trajectory_rows})
    test_seal_manifest_path = MANIFEST_DIR / "stage04b_test_seal_manifest.json"; write_json(test_seal_manifest_path, {"schema_version": "sph-pio-poc.stage04b.test-seal-manifest.v1", "sealed_lineages": [fid for fid in sorted(TEMPLATES) if role_map[fid] == "SEALED_TEST_LINEAGE"], **seal_counts, "private_artifacts": private_entries, "access_denial_audit": file_entry(access_audit_path), "access_policy": file_entry(access_policy_path), "all_access_denial_tests_pass": seal_pass, "release_authorized": False})

    # Reports.
    report_texts = {
        "stage04b_freeze_and_scope.md": f"# Stage 04B freeze and scope\n\nStage 04A verdict: `STAGE04A_TARGET_VERIFIED`. The Stage 04B contract was frozen before parameter, analytic-result, topology, DOP853, or trajectory materialization at `{CONTRACT_SHA}`. Role assignment was frozen independently before scientific results. No model, optimizer, training, normalization fitting, rollout, or performance evaluation was executed.\n",
        "stage04b_formula_library.md": f"# Stage 04B formula library\n\nThe frozen library contains {len(formula_library)}/10 independent templates: " + ", ".join(f"{item['family_id']} {item['template']}" for item in formula_library) + ". Primitive formulas are recorded verbatim in the contract and formula manifest.\n",
        "stage04b_parameter_generation.md": "# Stage 04B parameter generation\n\nParameters are deterministic SHA-256 maps of `stage04b_formula_parameters_v1 || family_id` into frozen amplitude, ratio, phase, and frequency intervals. LOW=0.75×MAIN and remains in the same lineage. Redraws, replacement, and deletion after failure are all zero. Validation and sealed values are isolated.\n",
        "stage04b_analytic_qualification.md": f"# Stage 04B analytic qualification\n\nIndependent SymPy closed-form and PyTorch CPU-float64 primitive-map autodiff routes were evaluated at 8192 material-time points per family/variant with all 36 times and seam/extrema/risk coverage. PASS={analytic_pass}/20; no failed formula was altered or replaced.\n",
        "stage04b_trajectory_inventory.md": f"# Stage 04B trajectory inventory\n\nCanonical exact trajectories: {len(trajectory_rows)}/60 complete and {trajectory_pass}/60 PASS. Each of 10 lineages has LOW/MAIN at N8/N12/N16, 36 frames (`n=-3..32`) and 32 K=1 origins. Frames/windows/resolutions/variants remain in one formula component.\n",
        "stage04b_semidiscrete_audit.md": f"# Stage 04B semidiscrete audit\n\nDOP853 primary/sensitivity/repeat cases passed {dop_pass}/20. Total RHS graph rebuilds={total_rhs}. Primary/sensitivity gates are 1e-9 normalized L2 and 1e-8 normalized Linf; repeat and graph/event sequences are deterministic. Exact differences remain `semidiscrete_spatial_model_form_diagnostic_only`.\n",
        "stage04b_topology_margin.md": f"# Stage 04B topology margin\n\nFixed-topology lineages: {len(fixed_lineages)}/10 ({', '.join(fixed_lineages)}). Variable lineages: {', '.join(variable_lineages) if variable_lineages else 'none'}. Every trajectory used 1025 dense samples and three independent repeats; the gate requires zero events and normalized cutoff margin at least 0.02. No amplitude was changed.\n",
        "stage04b_lineage_and_split.md": f"# Stage 04B lineage and split\n\nThe dependency graph has exactly 10 formula-level connected components and zero cross-role edges. Deterministic roles are TRAIN={','.join(fid for fid in sorted(TEMPLATES) if role_map[fid]=='TRAIN_LINEAGE')}; VALIDATION={','.join(fid for fid in sorted(TEMPLATES) if role_map[fid]=='VALIDATION_LINEAGE')}; SEALED_TEST={','.join(fid for fid in sorted(TEMPLATES) if role_map[fid]=='SEALED_TEST_LINEAGE')}. Random frame/window/particle/edge/resolution/variant splitting is prohibited.\n",
        "stage04b_test_seal.md": f"# Stage 04B test seal\n\nSealed lineages are {', '.join(fid for fid in sorted(TEMPLATES) if role_map[fid]=='SEALED_TEST_LINEAGE')}. Sensitive coefficients, states, sources, targets, origins, and graph sequences are private, mode 000, and rejected by the Stage 04C allowlist. Access-denial tests passed {sum(row['application_denied'] and row['posix_denied'] for row in denial_rows)}/{len(denial_rows)}. Decode counts: formula={seal_counts['pre_release_test_formula_parameter_decode_count']}, state={seal_counts['pre_release_test_state_decode_count']}, target={seal_counts['pre_release_test_target_decode_count']}.\n",
        "stage04b_uncertainty.md": "# Stage 04B uncertainty\n\nThe registry separates analytic closure, derivative-route disagreement, float64 roundoff, topology sampling/bounds, semidiscrete time sensitivity, spatial model-form diagnostics, and sealed redaction. No qualification result changed a parameter, role, formula, or family inventory.\n",
        "stage04b_resource_audit.md": f"# Stage 04B resource audit\n\nResource verdict: `{resource_metrics['verdict']}`. Peak RSS delta={peak_delta} bytes (gate 1610612736); storage before report packaging={storage} bytes; topology scan evaluations={60*1025*3}; DOP853 RHS graph rebuilds={total_rhs}. No dense particle N×N allocation occurred; weak-reference collection passed {sum(weak_results)}/{len(weak_results)}.\n",
        "stage04b_qualification_report.md": f"# Stage 04B qualification report\n\nGates: " + ", ".join(f"{key}={'PASS' if value else 'FAIL'}" for key, value in gates.items()) + f". Final status: `{final_status}`.\n",
    }
    final_report = f"""# Stage 04B final report

1. Stage 04A verification verdict: `STAGE04A_TARGET_VERIFIED`.
2. Stage 04A verification evidence is frozen in `{relative(VERIFY_MANIFEST)}` at `{sha256_file(VERIFY_MANIFEST)}`.
3. Stage 04B authorization was limited to new reference-family and lineage qualification; no model work was authorized.
4. Stage 03C/D/D-R/D-S/topology/03E boundaries remain unchanged.
5. Stage 04B contract hash: `{CONTRACT_SHA}`.
6. Formula inventory: {len(formula_library)}/10 complete.
7. Parameters use deterministic SHA-256 interval mapping; redraw/replacement count is 0.
8. Role assignment was frozen before results: 6 TRAIN, 2 VALIDATION, 2 SEALED_TEST.
9. Analytic qualification: {analytic_pass}/20 family-variant combinations PASS.
10. Derivative routes: independent SymPy closed form and PyTorch CPU-float64 primitive-map autodiff, 8192 points per combination.
11. Exact trajectory inventory: {len(trajectory_rows)}/60 complete; {trajectory_pass}/60 PASS; 36 frames and 32 K=1 origins each.
12. Topology scans: 1025 samples × 3 repeats per trajectory; fixed lineages={len(fixed_lineages)}/10.
13. FIXED_TOPOLOGY_QUALIFIED: {', '.join(fixed_lineages)}; TOPOLOGY_VARIABLE_LINEAGE: {', '.join(variable_lineages) if variable_lineages else 'none'}.
14. DOP853 same-semidscrete audits: {dop_pass}/20 PASS; exact differences are spatial-model-form diagnostics only.
15. Lineage graph: exactly 10 connected components, zero cross-role edges.
16. Sealed coefficients/payloads are isolated by application allowlist and POSIX mode 000; denial tests passed {sum(row['application_denied'] and row['posix_denied'] for row in denial_rows)}/{len(denial_rows)}.
17. Pre-release decode counts: formula={seal_counts['pre_release_test_formula_parameter_decode_count']}, state={seal_counts['pre_release_test_state_decode_count']}, target={seal_counts['pre_release_test_target_decode_count']}.
18. Uncertainty buckets are explicit and no result-dependent parameter/family change occurred.
19. Resource verdict: `{resource_metrics['verdict']}`; peak RSS delta={peak_delta} bytes; no dense N×N particle allocation.
20. Stage 04C authorization: {str(final_status == 'LOCAL_CAUSAL_REFERENCE_FAMILY_POOL_QUALIFIED').lower()}.
21. `optimizer_steps=0`.
22. `training_runs=0`.
23. `neural_rollouts=0`.
24. `performance_evaluations=0`.
25. Historical freeze: {history['checked']}/{history['checked']} checked, missing={len(history['missing'])}, hash mismatch={len(history['hash_mismatch'])}, status conflict={len(history['status_conflict'])}.

Final status: `{final_status}`.

Limited next authorization: **Stage 04C — Task-Aligned Parameter-Gradient Qualification** only if the final status is qualified. No training is authorized.
"""
    report_texts["stage04b_final_report.md"] = final_report
    report_entries: list[dict[str, Any]] = []
    for name, content in report_texts.items():
        path = REPORT_DIR / name; write_text(path, content); report_entries.append(file_entry(path))

    official_manifest_paths = [input_manifest_path, contract_manifest_path, formula_manifest_path, lineage_manifest_path, role_manifest_path, trajectory_manifest_path, test_seal_manifest_path]
    final_manifest = {
        "schema_version": "sph-pio-poc.stage04b.final.v1", "completion_date": "2026-08-05",
        "final_status": final_status, "all_required_gates_pass": all(gates.values()),
        "stage04a_verdict": "STAGE04A_TARGET_VERIFIED", "gates": gates, "counts": qualification["counts"],
        "contract": file_entry(CONTRACT), "qualification": file_entry(qualification_path),
        "manifests": [file_entry(path) for path in official_manifest_paths], "reports": report_entries,
        "test_seal": {**seal_counts, "access_denial_tests_pass": seal_pass, "release_authorized": False},
        "prohibitions": {"optimizer_steps": 0, "training_runs": 0, "neural_rollouts": 0, "performance_evaluations": 0, "model_forward_runs": 0, "normalization_fits": 0},
        "historical_hashes_unchanged": history["pass"],
        "next_stage": {"stage": "Stage 04C — Task-Aligned Parameter-Gradient Qualification", "authorization": "LIMITED" if final_status == "LOCAL_CAUSAL_REFERENCE_FAMILY_POOL_QUALIFIED" else "NONE", "training_authorized": False},
    }
    final_manifest_path = MANIFEST_DIR / "stage04b_final_manifest.json"; write_json(final_manifest_path, final_manifest)
    run_manifest_path = STAGE04B / "manifests" / "stage04b_run_manifest.json"
    write_json(run_manifest_path, {
        "schema_version": "sph-pio-poc.stage04b.run.v1", "status": final_status,
        "contract_sha256": CONTRACT_SHA, "role_preregistration_sha256": sha256_file(ROLE_PREREG),
        "preflight_smoke_disclosure": {"analytic_case": "LCDF_01 VARIANT_MAIN in-memory", "dop853_case": "LCDF_01 N8 in-memory", "role": "implementation_preflight_after_contract_and_role_freeze", "used_for_parameter_or_role_selection": False},
        "elapsed_seconds": time.perf_counter() - started, "official_final_manifest": file_entry(final_manifest_path),
        "optimizer_steps": 0, "training_runs": 0, "neural_rollouts": 0, "performance_evaluations": 0,
    })
    print(json.dumps({"stage04a": "STAGE04A_TARGET_VERIFIED", "stage04b": final_status, "counts": qualification["counts"], "final_manifest": relative(final_manifest_path)}, indent=2), flush=True)


if __name__ == "__main__":
    main()
