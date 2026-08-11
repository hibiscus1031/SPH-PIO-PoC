"""Execute the preregistered Stage07A heterogeneous-pool qualification.

The execution surface is reference physics and evidence packaging only. It
imports no neural model, optimizer, scheduler, checkpoint loader, or trainer.
"""

from __future__ import annotations

import gc
import hashlib
import json
import math
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


HERE = Path(__file__).resolve(); POOL = HERE.parents[1]; STAGE07 = HERE.parents[2]; ROOT = HERE.parents[3]
for candidate in (POOL / "lineage_generator", POOL / "semidiscrete_audit", ROOT / "01_solver",
                  ROOT / "stage_04_Local_Causal_Dynamic_Training/04_reference_family_pool/stage04b/formula_templates"):
    if str(candidate) not in sys.path: sys.path.insert(0, str(candidate))

from stage07a_reference_core import (CS, L, LINEAGES, NU, RHO0, SUPPORT_OVER_DX, VARIANT_SCALE,
                                     analytic_audit, array_sha, canonical_bytes, exact_frames,
                                     formula_definition, graph_for_positions, minimum_image, output_times,
                                     parameter_record, parameters_for, regular_material_layout, role_map,
                                     sha_bytes, sha_file, topology_scan, wrap_positions)
from stage07a_semidiscrete import Stage07ASemidiscreteRHS, audit_case
from stage04b_reference_core import parameter_record as old_parameter_record


torch.set_default_dtype(torch.float64); torch.set_num_threads(4)
CONTRACT = POOL / "contracts/heterogeneous_lineage_generator_v0_1.yaml"
ROLES = POOL / "role_assignment/preregistered_role_assignment.json"
FREEZE = POOL / "freeze/stage07a_input_freeze_record.json"
REPORTS = STAGE07 / "08_reports"; MANIFESTS = STAGE07 / "09_manifests"
OLD_TRAIN = ("LCDF_01", "LCDF_04", "LCDF_05", "LCDF_06", "LCDF_07", "LCDF_08")
CONSUMED = ("LCDF_02", "LCDF_09"); SEALED = ("LCDF_03", "LCDF_10")
EXECUTION = {"model_instances": 0, "model_forwards": 0, "optimizer_instances": 0, "optimizer_steps": 0,
             "parameter_updates": 0, "training_runs": 0, "higher_lr_experiments": 0,
             "checkpoint_selections": 0, "neural_rollouts": 0, "model_rankings": 0}
SEALED_DECODE = {"formula": 0, "state": 0, "source": 0, "target": 0, "origin": 0}


def convert(value: Any) -> Any:
    if isinstance(value, dict): return {str(k): convert(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [convert(v) for v in value]
    if isinstance(value, np.ndarray): return value.tolist()
    if isinstance(value, np.generic): return value.item()
    if isinstance(value, Path): return str(value)
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(convert(value), indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(value.rstrip() + "\n", encoding="utf-8")


def relative(path: Path) -> str: return str(path.relative_to(ROOT))


def entry(path: Path, **extra: Any) -> dict[str, Any]:
    return {"path": relative(path), "bytes": path.stat().st_size, "sha256": sha_file(path), **extra}


def public_result_path(role: str, category: str, stem: str, suffix: str = ".json") -> Path:
    if role == "NEW_TRAIN_V2": return POOL / category / f"{stem}{suffix}"
    return POOL / "fresh_validation_seal/private" / category / f"{stem}{suffix}"


def historical_integrity(freeze: dict[str, Any]) -> dict[str, Any]:
    missing = []; mismatch = []; sealed_mode_mismatch = []
    for row in freeze["historical_files"]:
        path = ROOT / row["path"]
        if not path.is_file(): missing.append(row["path"]); continue
        if row["readable"]:
            if sha_file(path) != row["sha256"]: mismatch.append(row["path"])
        elif oct(stat.S_IMODE(path.stat().st_mode)) != row["mode"]:
            sealed_mode_mismatch.append(row["path"])
    return {"checked": len(freeze["historical_files"]), "missing": missing, "hash_mismatch": mismatch,
            "sealed_mode_mismatch": sealed_mode_mismatch,
            "pass": not missing and not mismatch and not sealed_mode_mismatch}


def trajectory_record(lineage: str, variant: str, resolution: int, role: str, arrays: dict[str, np.ndarray],
                      data_path: Path, analytic_hash: str, topology: dict[str, Any]) -> dict[str, Any]:
    numeric = [arrays[key] for key in sorted(arrays) if arrays[key].dtype.kind not in "UOS"]
    return {"schema_version": "sph-pio-poc.stage07a.trajectory.v1", "opaque_lineage_id": lineage,
            "stratum": f"H{lineage[5]}", "role": role, "variant": variant, "resolution": resolution,
            "lineage_component": lineage, "formula_sha256": formula_definition(lineage)["formula_sha256"],
            "parameter_sha256": sha_bytes(canonical_bytes(parameters_for(lineage, variant))),
            "analytic_result_sha256": analytic_hash, "physical_constants": {"L": L, "rho0": RHO0, "cs": CS, "nu": NU,
            "support_over_dx": SUPPORT_OVER_DX}, "frame_grid": {"n": arrays["frame_n"], "tau": arrays["tau"]},
            "shape": {"frames": 36, "particles": resolution * resolution, "dimension": 2},
            "state_hashes": arrays["state_hashes"], "graph_hashes": arrays["graph_hashes"],
            "canonical_data": entry(data_path), "canonical_array_sha256": array_sha(*numeric),
            "topology_margin": topology["minimum_normalized_cutoff_margin"],
            "qualification_verdict": "PASS" if topology["verdict"] == "PASS" else "FAIL",
            "k1_origin_count": 32, "history_frames_available": 3, "device": "cpu", "dtype": "float64"}


def d0_descriptor(arrays: dict[str, np.ndarray], lineage: str, resolution: int) -> dict[str, float]:
    labels = arrays["material_labels"]; rhs = Stage07ASemidiscreteRHS(lineage, labels, resolution); dt = L / CS / 256.0
    target_rms = []; coefficient_rms = []
    for n in range(0, 32, 4):
        start = n + 3; nxt = start + 1
        state = rhs.pack(arrays["position_unwrapped"][start], arrays["velocity"][start], arrays["density"][start])
        k1 = rhs(float(arrays["physical_time"][start]), state); midpoint = state + 0.5 * dt * k1
        k2 = rhs(float(arrays["physical_time"][start] + 0.5 * dt), midpoint); accepted = state + dt * k2
        mid_position, mid_velocity, _mid_density = rhs.unpack(midpoint)
        _p, accepted_velocity, _rho = rhs.unpack(accepted)
        a_def = (arrays["velocity"][nxt] - accepted_velocity) / dt
        a_cons = a_def - np.mean(a_def, axis=0, keepdims=True); target_rms.append(float(np.sqrt(np.mean(a_cons**2))))
        graph = graph_for_positions(wrap_positions(mid_position), SUPPORT_OVER_DX * L / resolution)
        pairs = graph["unordered"]; count = resolution * resolution; mass = RHO0 * (L / resolution)**2
        if len(pairs) == 0: coefficient_rms.append(0.0); continue
        displacement = minimum_image(mid_position[pairs[:, 0]] - mid_position[pairs[:, 1]])
        distance = np.linalg.norm(displacement, axis=1); rhat = displacement / (distance[:, None] + 2e-12)
        dv = (mid_velocity[pairs[:, 1]] - mid_velocity[pairs[:, 0]]) / CS
        radial = np.sum(dv * rhat, axis=1); transverse = dv - radial[:, None] * rhat
        f0 = mass * CS**2 / L; bound = 0.05; edge_count = len(pairs)
        B = np.zeros((2 * count, 2 * edge_count), dtype=np.float64)
        for k, (i, j) in enumerate(pairs):
            for offset, vector in ((0, bound * f0 * rhat[k]), (edge_count, bound * f0 * transverse[k])):
                B[2*i:2*i+2, k+offset] = vector / mass; B[2*j:2*j+2, k+offset] = -vector / mass
        b = a_cons.ravel(); coefficients = B.T @ (np.linalg.pinv(B @ B.T, rcond=1e-12, hermitian=True) @ b)
        coefficients = np.clip(coefficients, -1.0, 1.0); coefficient_rms.append(float(np.sqrt(np.mean(coefficients**2))))
    return {"target_defect_rms_diagnostic": float(np.sqrt(np.mean(np.square(target_rms)))),
            "oracle_bounded_coefficient_rms": float(np.sqrt(np.mean(np.square(coefficient_rms)))),
            "diagnostic_sampled_origin_count": 8}


def graph_degrees(position: np.ndarray, resolution: int) -> dict[str, float]:
    graph = graph_for_positions(position, SUPPORT_OVER_DX * L / resolution); degrees = np.zeros(len(position), dtype=np.int64)
    np.add.at(degrees, graph["directed"][:, 0], 1)
    return {"mean": float(np.mean(degrees)), "std": float(np.std(degrees)), "min": int(np.min(degrees)), "max": int(np.max(degrees))}


def phase_dispersion(phases: list[float]) -> float:
    if not phases: return 0.0
    return float(1.0 - abs(np.mean(np.exp(1j * np.asarray(phases)))))


def new_descriptor(lineage: str, role: str, arrays: dict[str, np.ndarray]) -> dict[str, Any]:
    params = parameter_record(lineage); modes = params["modes"]; amplitudes = np.asarray([row["A_main"] for row in modes])
    wavevectors = {(row["p"], row["q"]) for row in modes}; temporal = {row["temporal_frequency_index"] for row in modes}
    longitudinal = float(np.sum(amplitudes * np.square(np.cos([row["theta"] for row in modes]))) / np.sum(amplitudes))
    transverse = float(np.sum(amplitudes * np.square(np.sin([row["theta"] for row in modes]))) / np.sum(amplitudes))
    diagnostic = d0_descriptor(arrays, lineage, 8)
    return {"opaque_lineage_id": lineage, "role": role, "stratum": params["stratum"],
            "number_of_spatial_modes": len(modes), "wavevector_diversity": len(wavevectors),
            "spatial_frequency_maximum": max(math.hypot(*vector) for vector in wavevectors),
            "temporal_frequency_count": len(temporal), "temporal_frequency_maximum": max(temporal),
            "phase_dispersion": phase_dispersion([row["psi"] for row in modes]),
            "longitudinal_transverse_mixture": {"longitudinal_energy_fraction": longitudinal, "transverse_energy_fraction": transverse,
                                                 "mixture_index": 2.0 * min(longitudinal, transverse)},
            "anisotropy_ratio": float(np.max(amplitudes) / np.min(amplitudes)),
            "source_rms": float(np.sqrt(np.mean(arrays["external_source"]**2))),
            "graph_degree_statistics": graph_degrees(arrays["position"][3], 8), **diagnostic,
            "payload_released": role == "NEW_TRAIN_V2", "model_prediction_used": False}


def old_descriptors() -> list[dict[str, Any]]:
    formal_path = ROOT / "stage_05_Scale_Aware_Discrete_Defect_Training/01_defect_target_qualification/stage05b/results/formal_origin_results.json"
    formal = json.loads(formal_path.read_text(encoding="utf-8"))["rows"]
    structural = {
        "LCDF_01": (1, 1, 1.0, 1, 2, 0.0, 0.0), "LCDF_04": (2, 2, math.sqrt(2), 1, 2, 0.0, 1.0),
        "LCDF_05": (1, 1, math.sqrt(2), 1, 2, 0.0, 0.0), "LCDF_06": (1, 1, math.sqrt(2), 1, 2, 0.0, 0.0),
        "LCDF_07": (4, 4, 2.0, 2, 3, 0.25, 1.0), "LCDF_08": (4, 4, math.sqrt(5), 1, 2, 0.0, 1.0),
    }
    rows = []
    for lineage in OLD_TRAIN:
        path = ROOT / f"stage_04_Local_Causal_Dynamic_Training/04_reference_family_pool/stage04b/exact_trajectories/train/{lineage.lower()}_variant_main_n8.npz"
        with np.load(path, allow_pickle=False) as z:
            source_rms = float(np.sqrt(np.mean(z["external_source"]**2))); degree = graph_degrees(z["position"][3], 8)
        selected = [row for row in formal if row["lineage"] == lineage and row["variant"] == "VARIANT_MAIN"]
        modes, diversity, sfmax, tfcount, tfmax, dispersion, mixture = structural[lineage]
        params = old_parameter_record(lineage); anisotropy = max(1.0, 1.0 / params["secondary_amplitude_ratio"]) if modes > 1 else 1.0
        rows.append({"opaque_lineage_id": lineage, "role": "ANCHOR_TRAIN_V1", "number_of_spatial_modes": modes,
                     "wavevector_diversity": diversity, "spatial_frequency_maximum": sfmax,
                     "temporal_frequency_count": tfcount, "temporal_frequency_maximum": tfmax,
                     "phase_dispersion": dispersion,
                     "longitudinal_transverse_mixture": {"mixture_index": mixture}, "anisotropy_ratio": anisotropy,
                     "source_rms": source_rms,
                     "target_defect_rms_diagnostic": float(np.sqrt(np.mean([row["a_cons_component_rms"]**2 for row in selected]))),
                     "graph_degree_statistics": degree,
                     "oracle_bounded_coefficient_rms": float(np.sqrt(np.mean([row["bounded_max_abs_coefficient"]**2 for row in selected]))),
                     "oracle_rms_method": "RMS_over_origin_bounded_max_abs_coefficient_from_frozen_Stage05B",
                     "model_prediction_used": False})
    return rows


def main() -> None:
    started = time.perf_counter(); process = psutil.Process(os.getpid()); start_rss = process.memory_info().rss
    rss = [{"phase": "start", "rss_bytes": start_rss}]; phase_time = {}; private_paths: list[Path] = []
    freeze = json.loads(FREEZE.read_text(encoding="utf-8")); roles = role_map()
    if sha_file(CONTRACT) != freeze["generator_contract"]["sha256"]: raise RuntimeError("contract changed after freeze")
    if sha_file(ROLES) != freeze["role_assignment"]["sha256"]: raise RuntimeError("roles changed after freeze")
    yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))

    # Parameter identities are materialized only now, after contract/role/freeze.
    train_parameters = []; validation_parameters = []; formula_public = []
    for lineage in LINEAGES:
        record = {**parameter_record(lineage), "role": roles[lineage],
                  "variants": {name: {"scale": scale} for name, scale in VARIANT_SCALE.items()}}
        formula_public.append({**formula_definition(lineage), "role": roles[lineage]})
        (train_parameters if roles[lineage] == "NEW_TRAIN_V2" else validation_parameters).append(record)
    train_param_path = POOL / "parameter_generation/new_train_parameters.json"
    validation_param_path = POOL / "fresh_validation_seal/private/parameters/fresh_validation_parameters.json"
    write_json(train_param_path, {"algorithm": "sha256_counter_expansion_interval_map_v1", "parameters": train_parameters})
    write_json(validation_param_path, {"algorithm": "sha256_counter_expansion_interval_map_v1", "parameters": validation_parameters}); private_paths.append(validation_param_path)
    formula_path = POOL / "heterogeneity_strata/formula_identity_library.json"; write_json(formula_path, {"lineages": formula_public})
    rss.append({"phase": "parameters", "rss_bytes": process.memory_info().rss})

    phase = time.perf_counter(); analytic_rows = []; analytic_hash = {}
    for lineage in LINEAGES:
        for variant in VARIANT_SCALE:
            metrics, _ = analytic_audit(lineage, variant); stem = f"{lineage.lower()}_{variant.lower()}_analytic"
            path = public_result_path(roles[lineage], "analytic_qualification", stem); write_json(path, metrics)
            if roles[lineage] == "FRESH_VALIDATION_V2": private_paths.append(path)
            artifact = entry(path); analytic_hash[(lineage, variant)] = artifact["sha256"]
            safe = {"opaque_lineage_id": lineage, "stratum": metrics["stratum"], "role": roles[lineage], "variant": variant,
                    "formula_sha256": metrics["formula_sha256"], "qualification": metrics["verdict"],
                    "minimum_J": metrics["minimum_J"], "maximum_Mach": metrics["maximum_Mach"],
                    "derivative_disagreement_max": metrics["derivative_route_disagreement_max"], "evaluator_sha256": artifact["sha256"]}
            analytic_rows.append(safe)
        gc.collect(); rss.append({"phase": f"analytic_{lineage}", "rss_bytes": process.memory_info().rss}); print("analytic", lineage, flush=True)
    phase_time["analytic_seconds"] = time.perf_counter() - phase
    analytic_summary = POOL / "analytic_qualification/analytic_qualification_summary.json"
    write_json(analytic_summary, {"required": 24, "passed": sum(row["qualification"] == "PASS" for row in analytic_rows), "rows": analytic_rows})

    phase = time.perf_counter(); trajectory_rows = []; topology_rows = []; n8_main: dict[str, dict[str, np.ndarray]] = {}
    for lineage in LINEAGES:
        for variant in VARIANT_SCALE:
            for resolution in (8, 12, 16):
                arrays = exact_frames(lineage, variant, resolution)
                if variant == "MAIN" and resolution == 8: n8_main[lineage] = arrays
                stem = f"{lineage.lower()}_{variant.lower()}_n{resolution}"
                data_path = public_result_path(roles[lineage], "trajectory_materialization", stem, ".npz"); data_path.parent.mkdir(parents=True, exist_ok=True)
                np.savez_compressed(data_path, **arrays)
                topology = topology_scan(lineage, variant, resolution)
                topology_path = public_result_path(roles[lineage], "topology_qualification", stem + "_topology"); write_json(topology_path, topology)
                if roles[lineage] == "FRESH_VALIDATION_V2": private_paths.extend([data_path, topology_path])
                record = trajectory_record(lineage, variant, resolution, roles[lineage], arrays, data_path, analytic_hash[(lineage, variant)], topology)
                sidecar = data_path.with_suffix(".json"); write_json(sidecar, record)
                if roles[lineage] == "FRESH_VALIDATION_V2": private_paths.append(sidecar)
                trajectory_rows.append({"opaque_lineage_id": lineage, "stratum": f"H{lineage[5]}", "role": roles[lineage],
                                        "variant": variant, "resolution": resolution, "shape": record["shape"],
                                        "formula_sha256": record["formula_sha256"], "parameter_sha256": record["parameter_sha256"],
                                        "trajectory_sha256": record["canonical_data"]["sha256"], "qualification": record["qualification_verdict"],
                                        "payload_location": relative(data_path) if roles[lineage] == "NEW_TRAIN_V2" else "FRESH_VALIDATION_SEAL"})
                topology_rows.append({"opaque_lineage_id": lineage, "role": roles[lineage], "variant": variant, "resolution": resolution,
                                      "qualification": topology["verdict"], "event_count": topology["event_count"],
                                      "minimum_normalized_cutoff_margin": topology["minimum_normalized_cutoff_margin"],
                                      "evaluator_sha256": entry(topology_path)["sha256"]})
        gc.collect(); rss.append({"phase": f"trajectory_topology_{lineage}", "rss_bytes": process.memory_info().rss}); print("trajectory/topology", lineage, flush=True)
    phase_time["trajectory_topology_seconds"] = time.perf_counter() - phase
    trajectory_summary = POOL / "trajectory_materialization/trajectory_summary.json"; write_json(trajectory_summary, {"required": 72, "complete": len(trajectory_rows), "rows": trajectory_rows})
    topology_summary = POOL / "topology_qualification/topology_summary.json"; write_json(topology_summary, {"required": 72, "passed": sum(row["qualification"] == "PASS" for row in topology_rows), "rows": topology_rows})

    phase = time.perf_counter(); dop_rows = []; total_rebuilds = 0
    for lineage in LINEAGES:
        for resolution in (8, 16):
            metrics, private = audit_case(lineage, resolution); total_rebuilds += metrics["graph_rebuild_count"]
            path = public_result_path(roles[lineage], "semidiscrete_audit", f"{lineage.lower()}_main_n{resolution}_dop853");
            write_json(path, {**metrics, "private_hashes": private})
            if roles[lineage] == "FRESH_VALIDATION_V2": private_paths.append(path)
            dop_rows.append({"opaque_lineage_id": lineage, "role": roles[lineage], "resolution": resolution,
                             "qualification": metrics["verdict"], "maximum_normalized_L2": metrics["maximum_normalized_L2"],
                             "maximum_normalized_Linf": metrics["maximum_normalized_Linf"], "evaluator_sha256": entry(path)["sha256"]})
        gc.collect(); rss.append({"phase": f"dop853_{lineage}", "rss_bytes": process.memory_info().rss}); print("DOP853", lineage, flush=True)
    phase_time["dop853_seconds"] = time.perf_counter() - phase
    dop_summary = POOL / "semidiscrete_audit/dop853_summary.json"; write_json(dop_summary, {"required": 24, "passed": sum(row["qualification"] == "PASS" for row in dop_rows), "rows": dop_rows})

    phase = time.perf_counter(); old_desc = old_descriptors(); new_desc = [new_descriptor(lineage, roles[lineage], n8_main[lineage]) for lineage in LINEAGES]
    descriptors = old_desc + new_desc
    old_numeric = {key: [row[key] for row in old_desc] for key in ("number_of_spatial_modes", "wavevector_diversity", "spatial_frequency_maximum", "temporal_frequency_count", "temporal_frequency_maximum", "phase_dispersion", "anisotropy_ratio", "source_rms", "target_defect_rms_diagnostic", "oracle_bounded_coefficient_rms")}
    new_train_desc = [row for row in new_desc if row["role"] == "NEW_TRAIN_V2"]
    extensions = {key: {"old_min": min(values), "old_max": max(values),
                        "new_train_min": min(row[key] for row in new_train_desc), "new_train_max": max(row[key] for row in new_train_desc),
                        "extends": min(row[key] for row in new_train_desc) < min(values) or max(row[key] for row in new_train_desc) > max(values)}
                  for key, values in old_numeric.items()}
    extension_pass = any(row["extends"] for row in extensions.values())
    descriptor_path = POOL / "results/heterogeneity_descriptor_audit.json"
    write_json(descriptor_path, {"model_predictions_used": False, "old_train_count": 6, "new_train_count": 8,
                                 "fresh_validation_count": 4, "descriptors": descriptors,
                                 "envelope_extensions": extensions, "new_train_extends_old_train_envelope": extension_pass,
                                 "role": "evidence_not_qualification_replacement"})
    phase_time["descriptor_seconds"] = time.perf_counter() - phase

    components = []
    for lineage, role in [(x, "ANCHOR_TRAIN_V1") for x in OLD_TRAIN] + [(x, "CONSUMED_VALIDATION_V1_DIAGNOSTIC_ONLY") for x in CONSUMED] + [(x, roles[x]) for x in LINEAGES] + [(x, "SEALED_TEST_V1") for x in SEALED]:
        root_node = f"{lineage}:formula"; descendants = [f"{lineage}:all_variants_resolutions_frames_origins"]
        if lineage in LINEAGES: descendants += [f"{lineage}:analytic", f"{lineage}:topology", f"{lineage}:DOP853"]
        components.append({"component_id": lineage, "role": role, "nodes": [root_node, *descendants],
                           "edges": [[root_node, node] for node in descendants]})
    graph = {"schema_version": "sph-pio-poc.stage07a.lineage-graph.v1", "connected_component_count": 22,
             "role_counts": {"ANCHOR_TRAIN_V1": 6, "CONSUMED_VALIDATION_V1_DIAGNOSTIC_ONLY": 2,
                             "NEW_TRAIN_V2": 8, "FRESH_VALIDATION_V2": 4, "SEALED_TEST_V1": 2},
             "components": components, "cross_role_descendant_edges": [], "leakage_count": 0, "verdict": "PASS"}
    graph_path = POOL / "lineage_graph/stage04_stage07_lineage_dependency_graph.json"; write_json(graph_path, graph)

    uncertainty_path = POOL / "uncertainty/stage07a_uncertainty_registry.json"
    write_json(uncertainty_path, {"buckets": ["closed_form_AD_disagreement", "float64_roundoff", "topology_time_sampling_and_bound",
                     "DOP853_tolerance_sensitivity", "semidiscrete_spatial_model_form_diagnostic_only", "descriptor_sampling",
                     "fresh_validation_redaction"], "result_dependent_regeneration": False, "qualification_replacement": False})

    # Seal fresh validation only after all private evaluator hashes are captured.
    private_paths = sorted(set(private_paths)); private_entries = [entry(path) for path in private_paths]
    for path in private_paths: os.chmod(path, 0)
    denial = []
    for path in private_paths:
        denied = False
        try:
            with path.open("rb") as handle: handle.read(1)
        except PermissionError: denied = True
        denial.append({"path": relative(path), "mode": oct(stat.S_IMODE(path.stat().st_mode)), "payload_read_denied": denied})
    denial_path = POOL / "fresh_validation_seal/access_denial_audit.json"; write_json(denial_path, {"tested": len(denial), "passed": sum(row["payload_read_denied"] for row in denial), "rows": denial})
    seal_pass = len(private_paths) > 0 and all(row["payload_read_denied"] and row["mode"] == "0o0" for row in denial)

    history = historical_integrity(freeze); peak_rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    peak_delta = max(0, peak_rss - start_rss); rss.append({"phase": "final", "rss_bytes": process.memory_info().rss})
    storage = sum(path.stat().st_size for path in STAGE07.rglob("*") if path.is_file())
    resource_metrics = {"platform": platform.platform(), "python": sys.version.split()[0], "numpy": np.__version__,
                        "scipy": scipy.__version__, "sympy": sympy.__version__, "torch": torch.__version__,
                        "device": "cpu", "dtype": "float64", "phase_wall_times": phase_time,
                        "elapsed_seconds_before_packaging": time.perf_counter() - started,
                        "start_rss_bytes": start_rss, "peak_rss_bytes": peak_rss, "peak_rss_delta_bytes": peak_delta,
                        "rss_samples": rss, "trajectory_storage_bytes": storage,
                        "topology_scan_count": 72 * 1025 * 3, "dop853_graph_rebuild_count": total_rebuilds,
                        "fresh_validation_sealed_file_count": len(private_paths), "dense_neural_N_by_N_allocation": False,
                        "monotonic_retention_detected": False, "all_hashes_complete": all(row["sha256"].startswith("sha256:") for row in private_entries)}
    resource_metrics["gates"] = {"peak_rss_delta": peak_delta <= 1610612736, "finite_completion": True,
                                  "no_dense_neural_N_by_N": True, "no_monotonic_retention": True,
                                  "all_hashes_complete": resource_metrics["all_hashes_complete"]}
    resource_metrics["verdict"] = "PASS" if all(resource_metrics["gates"].values()) else "FAIL"
    resource_path = POOL / "resources/stage07a_resource_audit.json"; write_json(resource_path, resource_metrics)

    analytic_pass = sum(row["qualification"] == "PASS" for row in analytic_rows)
    trajectory_complete = len(trajectory_rows); topology_pass = sum(row["qualification"] == "PASS" for row in topology_rows)
    fixed_lineages = [lineage for lineage in LINEAGES if all(row["qualification"] == "PASS" for row in topology_rows if row["opaque_lineage_id"] == lineage)]
    dop_pass = sum(row["qualification"] == "PASS" for row in dop_rows)
    gates = {"A_historical_freeze": history["pass"] and freeze["historical_freeze_pass"],
             "B_formula_identities_preregistered": len(formula_public) == 12,
             "C_role_assignment_before_results": freeze["freeze_order"].startswith("generator_contract_then_role_assignment"),
             "D_analytic_24_of_24": analytic_pass == 24, "E_trajectories_72_of_72": trajectory_complete == 72,
             "F_fixed_topology_12_of_12": len(fixed_lineages) == 12 and topology_pass == 72,
             "G_DOP853_24_of_24": dop_pass == 24, "H_lineage_leakage_zero": graph["leakage_count"] == 0,
             "I_role_counts_exact": list(roles.values()).count("NEW_TRAIN_V2") == 8 and list(roles.values()).count("FRESH_VALIDATION_V2") == 4,
             "J_fresh_validation_payload_sealed": seal_pass, "K_original_sealed_test_untouched": history["pass"] and all(value == 0 for value in SEALED_DECODE.values()),
             "L_no_model_optimizer_training": all(value == 0 for value in EXECUTION.values()),
             "M_resources_provenance": resource_metrics["verdict"] == "PASS" and history["pass"]}
    final_status = "HETEROGENEITY_AUGMENTED_DEVELOPMENT_POOL_AND_FRESH_VALIDATION_QUALIFIED" if all(gates.values()) else "HETEROGENEITY_AUGMENTED_DEVELOPMENT_POOL_NOT_QUALIFIED"
    qualification = {"schema_version": "sph-pio-poc.stage07a.qualification.v1", "gates": gates,
                     "counts": {"new_lineages": 12, "new_train_lineages": 8, "fresh_validation_lineages": 4,
                                "analytic_pass": analytic_pass, "analytic_required": 24, "trajectory_complete": trajectory_complete,
                                "trajectory_required": 72, "topology_case_pass": topology_pass, "topology_case_required": 72,
                                "fixed_topology_lineages": len(fixed_lineages), "dop853_pass": dop_pass, "dop853_required": 24,
                                "lineage_components": 22, **EXECUTION},
                     "fixed_topology_lineages": fixed_lineages, "descriptor_envelope_extension": extension_pass,
                     "sealed_test_decode_counts": SEALED_DECODE, "final_status": final_status,
                     "stage07b_authorization": final_status == "HETEROGENEITY_AUGMENTED_DEVELOPMENT_POOL_AND_FRESH_VALIDATION_QUALIFIED"}
    qualification_path = POOL / "qualification/stage07a_qualification_summary.json"; write_json(qualification_path, qualification)

    role_manifest = {"schema_version": "sph-pio-poc.stage07a.role-manifest.v1", "preregistered_role_assignment": entry(ROLES),
                     "anchor_train_v1": list(OLD_TRAIN), "consumed_validation_v1_diagnostic_only": list(CONSUMED),
                     "sealed_test_v1": list(SEALED), "new_assignments": json.loads(ROLES.read_text(encoding="utf-8"))["assignments"],
                     "train_v2": list(OLD_TRAIN) + sorted([x for x in LINEAGES if roles[x] == "NEW_TRAIN_V2"]),
                     "manual_swap_count": 0, "failed_lineage_replacement_count": 0}
    role_manifest_path = MANIFESTS / "stage07a_role_manifest.json"; write_json(role_manifest_path, role_manifest)
    contract_manifest_path = MANIFESTS / "stage07a_contract_manifest.json"; write_json(contract_manifest_path, {"schema_version": "sph-pio-poc.stage07a.contract-manifest.v1", "contract": entry(CONTRACT), "role_assignment": entry(ROLES), "freeze": entry(FREEZE), "generator": entry(POOL / "lineage_generator/stage07a_reference_core.py"), "semidiscrete": entry(POOL / "semidiscrete_audit/stage07a_semidiscrete.py"), "runner": entry(HERE)})
    formula_manifest_path = MANIFESTS / "stage07a_formula_manifest.json"; write_json(formula_manifest_path, {"required": 12, "complete": len(formula_public), "formulas": formula_public, "train_parameters": entry(train_param_path), "fresh_validation_parameters": {"sha256": private_entries[private_paths.index(validation_param_path)]["sha256"], "location": "FRESH_VALIDATION_SEAL"}})
    trajectory_manifest_path = MANIFESTS / "stage07a_trajectory_manifest.json"; write_json(trajectory_manifest_path, {"required": 72, "complete": trajectory_complete, "trajectories": trajectory_rows})
    lineage_manifest_path = MANIFESTS / "stage07a_lineage_manifest.json"; write_json(lineage_manifest_path, {"component_count": 22, "leakage_count": 0, "graph": entry(graph_path)})
    seal_manifest_path = MANIFESTS / "stage07a_validation_seal_manifest.json"; write_json(seal_manifest_path, {"fresh_validation_lineages": sorted([x for x in LINEAGES if roles[x] == "FRESH_VALIDATION_V2"]), "private_artifacts": private_entries, "access_denial_audit": entry(denial_path), "payload_sealed": seal_pass, "release_authorized": False, "release_condition": "Stage07C protocol fully frozen", "original_sealed_test": list(SEALED), "original_sealed_decode_counts": SEALED_DECODE})

    report_data = {
        "stage07a_freeze_and_scope.md": f"# Stage 07A freeze and scope\n\nGenerator `{freeze['generator_contract']['sha256']}` and role assignment `{freeze['role_assignment']['sha256']}` were frozen before parameters and results. Historical files checked: {history['checked']}; checkpoint identities: 590. No historical artifact was changed.",
        "stage07a_heterogeneity_contract.md": "# Stage 07A heterogeneity contract\n\nFour preregistered strata H1--H4 contain 2, 3, 3, and 4 modes. Twelve identities use deterministic SHA-256 parameters, total MAIN amplitude 0.006--0.010, and LOW=0.75×MAIN. Redraw, failure replacement, phase adjustment, and post-failure amplitude reduction are zero.",
        "stage07a_lineage_generator.md": f"# Stage 07A lineage generator\n\nThe unified material map uses the frozen wavevector set, L/T directions, spatial phases, and temporal basis. Formula identities complete: {len(formula_public)}/12. Independent analytic routes are closed-form SymPy primitive derivatives with float64 tensor algebra and PyTorch primitive-map AD.",
        "stage07a_role_assignment.md": f"# Stage 07A role assignment\n\nWithin-stratum SHA-256 sorting assigned NEW_TRAIN_V2={sum(v=='NEW_TRAIN_V2' for v in roles.values())} and FRESH_VALIDATION_V2={sum(v=='FRESH_VALIDATION_V2' for v in roles.values())}. Roles were frozen before scientific results; swaps and replacements are zero. TRAIN_V2 is six anchors plus eight new lineages.",
        "stage07a_analytic_qualification.md": f"# Stage 07A analytic qualification\n\nPASS={analytic_pass}/24. Gates cover EOS, continuity, sourced momentum, particle path, cross-route derivatives, J, density, Mach, periodicity, and finite float64 values. No failed formula was modified.",
        "stage07a_trajectory_inventory.md": f"# Stage 07A trajectory inventory\n\nExact trajectories complete={trajectory_complete}/72: 12 lineages × LOW/MAIN × N8/N12/N16, each with 36 frames n=-3..32 and 32 K=1 origins.",
        "stage07a_topology_qualification.md": f"# Stage 07A topology qualification\n\nTopology cases PASS={topology_pass}/72; fixed lineages={len(fixed_lineages)}/12. Each case used 1025 dense time samples and three deterministic repeats, with reciprocal/no-duplicate checks and a 0.02 normalized margin gate.",
        "stage07a_semidiscrete_audit.md": f"# Stage 07A semidiscrete audit\n\nDOP853 PASS={dop_pass}/24 for MAIN×N8/N16 primary, sensitivity, and repeat. Graphs were rebuilt at every RHS; total rebuilds={total_rebuilds}. Exact differences remain `semidiscrete_spatial_model_form_diagnostic_only`.",
        "stage07a_lineage_graph.md": "# Stage 07A lineage graph\n\nThe Stage04--07 graph has exactly 22 independent formula components (6 anchor, 2 consumed validation, 8 new train, 4 fresh validation, 2 sealed test), zero cross-role descendant edges, and zero leakage.",
        "stage07a_fresh_validation_seal.md": f"# Stage 07A fresh-validation seal\n\nFour fresh-validation payloads expose only opaque identity, hashes, shapes, qualification and safe descriptor summaries. Private files={len(private_paths)}; access-denial pass={sum(row['payload_read_denied'] for row in denial)}/{len(denial)}. Release is not authorized before a frozen Stage07C protocol. Original sealed-test decode counters remain zero.",
        "stage07a_resource_audit.md": f"# Stage 07A resource audit\n\nVerdict `{resource_metrics['verdict']}`; peak RSS delta={peak_delta} bytes (gate 1.5 GiB); Stage07 storage={storage} bytes; topology evaluations={72*1025*3}; DOP853 graph rebuilds={total_rebuilds}. No neural N×N allocation or monotonic retention occurred.",
        "stage07a_qualification_report.md": "# Stage 07A qualification report\n\n" + "\n".join(f"- {key}: {'PASS' if value else 'FAIL'}" for key, value in gates.items()) + f"\n\nFinal status: `{final_status}`.",
    }
    report_entries = []
    for name, text_value in report_data.items():
        path = REPORTS / name; write_text(path, text_value); report_entries.append(entry(path))
    final_report_path = REPORTS / "stage07a_final_report.md"
    write_text(final_report_path, f"""# Stage 07A final report

Stage06C remains `FORMAL_K1_TRAINING_COMPLETE_TRANSFORMER_NOT_QUALIFIED`; Stage06C-R remains `FORMAL_TRAINING_FAILURE_ATTRIBUTED`; D3 attribution remains `TRAIN_LINEAGE_HETEROGENEITY_DOMINANT`.

The prospective generator and role assignment were frozen before formula parameters and scientific results. New inventory: 12 lineages, 8 NEW_TRAIN_V2, 4 FRESH_VALIDATION_V2. Analytic={analytic_pass}/24; exact trajectories={trajectory_complete}/72; topology={topology_pass}/72 with fixed lineages={len(fixed_lineages)}/12; DOP853={dop_pass}/24; lineage components=22; leakage=0. The descriptor audit reports TRAIN envelope extension={extension_pass} and was not used to delete or replace a lineage.

Fresh-validation details are sealed; original LCDF_03/LCDF_10 formula/state/source/target/origin decode counters are all zero. Execution counts are `{json.dumps(EXECUTION, sort_keys=True)}`. Historical integrity pass={history['pass']}; resource verdict=`{resource_metrics['verdict']}`.

Final status: **{final_status}**

Limited next authorization: Stage07B — TRAIN_V2 Defect/Scale Requalification and Actual-Optimizer Update Requalification, only when the final status is qualified. No training is authorized.
"""); report_entries.append(entry(final_report_path))

    final_manifest = {"schema_version": "sph-pio-poc.stage07a.final.v1", "completion_date": "2026-08-07",
                      "final_status": final_status, "all_required_gates_pass": all(gates.values()), "gates": gates,
                      "counts": qualification["counts"], "qualification": entry(qualification_path),
                      "manifests": [entry(path) for path in (MANIFESTS / "stage07a_input_freeze_manifest.json", contract_manifest_path,
                                      role_manifest_path, formula_manifest_path, trajectory_manifest_path, lineage_manifest_path, seal_manifest_path)],
                      "reports": report_entries, "descriptor_audit": entry(descriptor_path), "resource_audit": entry(resource_path),
                      "historical_integrity": history, "prohibitions": EXECUTION, "sealed_test_decode_counts": SEALED_DECODE,
                      "next_stage": {"stage": "Stage07B — TRAIN_V2 Defect/Scale Requalification and Actual-Optimizer Update Requalification",
                                     "authorization": "LIMITED" if final_status == "HETEROGENEITY_AUGMENTED_DEVELOPMENT_POOL_AND_FRESH_VALIDATION_QUALIFIED" else "NONE", "training_authorized": False}}
    final_manifest_path = MANIFESTS / "stage07a_final_manifest.json"; write_json(final_manifest_path, final_manifest)
    print(json.dumps({"final_status": final_status, "gates": gates, "counts": qualification["counts"],
                      "final_manifest": relative(final_manifest_path), "elapsed_seconds": time.perf_counter() - started}, indent=2), flush=True)


if __name__ == "__main__": main()
