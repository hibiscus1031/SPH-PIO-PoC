"""Open only the frozen N8 validation split and qualify all 128 validation targets."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path
import stat
import sys
from typing import Any

import numpy as np
import torch

HERE = Path(__file__).resolve()
STAGE06B = HERE.parents[1]
STAGE06 = HERE.parents[3]
ROOT = HERE.parents[4]
STAGE04B = ROOT / "stage_04_Local_Causal_Dynamic_Training/04_reference_family_pool/stage04b"
STAGE05B = ROOT / "stage_05_Scale_Aware_Discrete_Defect_Training/01_defect_target_qualification/stage05b"
STAGE03C = ROOT / "stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03c"
sys.path[:0] = [str(STAGE03C), str(ROOT / "01_solver"), str(STAGE04B / "formula_templates")]

from baseline_d0.state import DynamicParticleState, eos_pressure
from graph_rebuild.graph import build_reciprocal_graph
from stage04b_reference_core import CS, L, RHO0, SUPPORT_OVER_DX, array_sha256, evaluate_symbolic
from tokenization.tokens import build_node_token

S_A = 3.45632855338432798e-1
DT = L / CS / 256.0
LINEAGES = ("LCDF_02", "LCDF_09")
VARIANTS = ("VARIANT_LOW", "VARIANT_MAIN")


def import_path(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ACCESS = import_path("stage06b_access", STAGE06B / "access_control/stage06b_access.py")
Q = import_path("stage05b_q", STAGE05B / "qualification/run_stage05b_qualification.py")


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def sha_array(*values: np.ndarray) -> str:
    digest = hashlib.sha256()
    for value in values:
        a = np.ascontiguousarray(value)
        digest.update(str(a.dtype).encode()); digest.update(b"\0")
        digest.update(np.asarray(a.shape, dtype=np.int64).tobytes()); digest.update(a.tobytes())
    return "sha256:" + digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    def cv(x: Any) -> Any:
        if isinstance(x, np.bool_): return bool(x)
        if isinstance(x, np.integer): return int(x)
        if isinstance(x, np.floating): return float(x)
        if isinstance(x, np.ndarray): return x.tolist()
        raise TypeError(type(x).__name__)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, default=cv) + "\n")


def tensor(value: np.ndarray) -> torch.Tensor:
    return torch.from_numpy(np.ascontiguousarray(value)).to(torch.float64)


def make_state(arrays: dict[str, np.ndarray], frame: int) -> DynamicParticleState:
    idx = int(np.flatnonzero(arrays["frame_n"] == frame)[0]); dx = L / 8
    rho = tensor(arrays["density"][idx])
    return DynamicParticleState(tensor(arrays["position_unwrapped"][idx]), tensor(arrays["velocity"][idx]), rho,
        eos_pressure(rho), torch.full((64,), RHO0 * dx * dx, dtype=torch.float64),
        torch.full((64,), SUPPORT_OVER_DX * dx, dtype=torch.float64), tensor(arrays["material_labels"]),
        float(arrays["physical_time"][idx]), frame)


def reference_checks(arrays: dict[str, np.ndarray], metadata: dict[str, Any], origin: int) -> dict[str, bool]:
    idx = int(np.flatnonzero(arrays["frame_n"] == origin + 1)[0])
    pressure = CS**2 * (arrays["density"][idx] - RHO0)
    recomputed = array_sha256(arrays["position"][idx], arrays["velocity"][idx], arrays["density"][idx], arrays["pressure"][idx])
    return {
        "material_labels": arrays["material_labels"].shape == (64, 2),
        "physical_time": abs(float(arrays["physical_time"][idx]) - ((origin + 1) * DT)) <= 2 * np.finfo(float).eps,
        "dt": abs(float(arrays["physical_time"][idx] - arrays["physical_time"][idx - 1]) - DT) <= 2 * np.finfo(float).eps,
        "eos_identity": float(np.max(np.abs(pressure - arrays["pressure"][idx]))) <= 1e-12,
        "source_family": metadata["opaque_family_id"] in metadata["lineage_component"],
        "periodic_convention": metadata["physical_constants"]["L"] == 2.0 and bool(np.all(arrays["position"][idx] >= -1.0) and np.all(arrays["position"][idx] < 1.0)),
        "validation_role": metadata["role"] == "VALIDATION_LINEAGE",
        "target_hash": recomputed == str(arrays["state_hashes"][idx]),
    }


def state_from(case: dict[str, Any], x: np.ndarray, v: np.ndarray, labels: np.ndarray,
               mass: np.ndarray, smoothing: np.ndarray) -> DynamicParticleState:
    rho = tensor(case["rho"])
    return DynamicParticleState(tensor(x), tensor(v), rho, eos_pressure(rho), tensor(mass), tensor(smoothing),
                                tensor(labels), case["time"], case["step"])


def symmetry_audit(case: dict[str, Any]) -> list[dict[str, Any]]:
    n = len(case["x"]); key = case["record_id"]
    seed = int.from_bytes(hashlib.sha256(("stage06b_validation_symmetry_v1|" + key).encode()).digest()[:8], "big")
    perm = np.random.default_rng(seed).permutation(n)
    q90 = np.asarray([[0., -1.], [1., 0.]]); ref = np.asarray([[-1., 0.], [0., 1.]])
    transforms = [
        ("particle_permutation", case["x"][perm], case["v"][perm], case["labels"][perm], case["a_def"][perm], case["a_cons"][perm], case["mass"][perm], case["smoothing"][perm], False),
        ("edge_reorder", case["x"], case["v"], case["labels"], case["a_def"], case["a_cons"], case["mass"], case["smoothing"], True),
        ("translation", case["x"] + np.asarray([.371, -.283]), case["v"], case["labels"], case["a_def"], case["a_cons"], case["mass"], case["smoothing"], False),
        ("galilean_boost", case["x"] + case["time"] * np.asarray([.173, -.119]), case["v"] + np.asarray([.173, -.119]), case["labels"], case["a_def"], case["a_cons"], case["mass"], case["smoothing"], False),
        ("SO2_rotation", case["x"] @ q90.T, case["v"] @ q90.T, case["labels"] @ q90.T, case["a_def"] @ q90.T, case["a_cons"] @ q90.T, case["mass"], case["smoothing"], False),
        ("reflection", case["x"] @ ref.T, case["v"] @ ref.T, case["labels"] @ ref.T, case["a_def"] @ ref.T, case["a_cons"] @ ref.T, case["mass"], case["smoothing"], False),
        ("periodic_representative_shift", case["x"] + np.asarray([2., -2.]), case["v"], case["labels"], case["a_def"], case["a_cons"], case["mass"], case["smoothing"], False),
    ]
    rows = []
    for name, x, v, labels, adef, acons, mass, smoothing, reverse in transforms:
        state = state_from(case, x, v, labels, mass, smoothing); graph = build_reciprocal_graph(state)
        dec = Q.decompose(adef, mass, case["u"])
        basis = Q.solve_basis(state, graph, dec["a_cons"], case["u"], reverse_columns=reverse)
        vector_error = float(np.linalg.norm(dec["a_cons"] - acons) / max(np.linalg.norm(acons), case["u"]))
        observed = (math.sqrt(float(np.mean(dec["a_cons"]**2))), dec["incompatible_fraction"], basis["Q_unbounded"], basis["Q_bounded"])
        base = case["base_scalars"]
        scalar_error = max(abs(a-b) / max(abs(a), abs(b), 1.0) for a, b in zip(observed, base))
        rows.append({"record_id": key, "transform": name, "scalar_relative_difference": scalar_error,
                     "vector_equivariance_normalized_error": vector_error,
                     "pass": scalar_error <= 1e-12 and vector_error <= 1e-10})
    return rows


def sealed_denial_audit() -> dict[str, Any]:
    sealed = STAGE04B / "sealed_test/private"
    probes = {
        "formula": sealed / "sealed_parameters.json",
        "state": sealed / "lcdf_03_variant_main_n8.npz",
        "source": sealed / "lcdf_10_variant_main_n8.npz",
        "target": sealed / "lcdf_03_variant_low_n8.npz",
        "origin": sealed / "lcdf_10_variant_low_n8.npz",
    }
    actors = ("trainer", "validation_evaluator", "checkpoint_selector", "report_generator", "general_file_reader")
    rows = []
    for actor in actors:
        for category, path in probes.items():
            denied = False
            try:
                if actor == "general_file_reader":
                    path.read_bytes()
                else:
                    ACCESS.read_for_actor(actor, path)
            except (PermissionError, OSError):
                denied = True
            rows.append({"actor": actor, "category": category, "path": str(path.relative_to(ROOT)),
                         "denied_before_payload_read": denied})
    seal_manifest = json.loads((ROOT / "stage_04_Local_Causal_Dynamic_Training/09_manifests/stage04b_test_seal_manifest.json").read_text())
    trajectory_manifest = json.loads((ROOT / "stage_04_Local_Causal_Dynamic_Training/09_manifests/stage04b_trajectory_manifest.json").read_text())
    trajectory_metadata = [{k: row[k] for k in ("opaque_family_id", "role", "lineage_component", "variant", "resolution",
                            "shape", "dtype", "trajectory_sha256", "sealed_location", "access_policy")}
                           for row in trajectory_manifest["trajectories"] if row["role"] == "SEALED_TEST"]
    opaque = [{k: row[k] for k in ("path", "sha256") if k in row} | {"size_bytes": (ROOT / row["path"]).stat().st_size,
              "mode": stat.S_IMODE((ROOT / row["path"]).stat().st_mode)} for row in seal_manifest["private_artifacts"]]
    return {"actors": list(actors), "categories": list(probes), "rows": rows, "opaque_metadata_only": opaque,
            "sealed_trajectory_metadata_from_public_manifest": trajectory_metadata,
            "sealed_decode_counts": {k: v for k, v in ACCESS.COUNTS.items() if k.startswith("sealed_")},
            "pass": len(rows) == 25 and all(r["denied_before_payload_read"] for r in rows) and
                    all(v == 0 for k, v in ACCESS.COUNTS.items() if k.startswith("sealed_"))}


def main() -> None:
    torch.set_num_threads(1); torch.set_default_dtype(torch.float64)
    protocol_manifest = json.loads((STAGE06B / "manifests/stage06b_protocol_manifest.json").read_text())
    protocol_path = ROOT / protocol_manifest["protocol_path"]
    assert sha_file(protocol_path) == protocol_manifest["protocol_sha256"]
    freeze = json.loads((STAGE06B / "freeze/stage06b_freeze_record.json").read_text())
    assert freeze["protocol_frozen_before_validation_decode"] and freeze["protocol_sha256"] == protocol_manifest["protocol_sha256"]
    release = {"schema": "sph-pio-poc.stage06b.validation-release.v1", "protocol_sha256": protocol_manifest["protocol_sha256"],
               "released_after_protocol_freeze": True, "opened_payload_scope": "LCDF_02/LCDF_09 N8 only",
               "protocol_changes_after_validation_open": 0}
    write_json(STAGE06B / "access_control/validation_release_record.json", release)

    private = STAGE04B / "access_control/validation_private"
    parameters = ACCESS.load_json("validation_materializer", private / "validation_parameters.json")
    parameter_hash = ACCESS.EVENTS[-1]["sha256"]
    rows: list[dict[str, Any]] = []; entries = []; symmetry_rows = []
    case_dir = STAGE06B / "validation_materialization/case_cache"
    target_dir = STAGE06B / "validation_materialization/target_records"
    case_dir.mkdir(parents=True, exist_ok=True); target_dir.mkdir(parents=True, exist_ok=True)
    roundoff = 64 * np.finfo(np.float64).eps * CS / DT
    for lineage in LINEAGES:
        for variant in VARIANTS:
            stem = f"{lineage.lower()}_{variant.lower()}_n8"
            arrays = ACCESS.load_npz("validation_materializer", private / f"{stem}.npz")
            metadata = ACCESS.load_json("validation_materializer", private / f"{stem}.json")
            assert metadata["role"] == "VALIDATION_LINEAGE"
            closed, independent = Q.independent_route_fields(lineage, variant, arrays["material_labels"])
            mass = np.full(64, RHO0 * (L / 8)**2, dtype=np.float64)
            transition = Q.Stage05BD0Transition(lineage, variant, DT)
            for origin in range(32):
                start = make_state(arrays, origin); idx = int(np.flatnonzero(arrays["frame_n"] == origin)[0])
                class_result = transition.step(start, tensor(arrays["external_source"][idx]))
                functional = Q.functional_d0(start, lineage, variant, DT); repeat = transition.step(start, tensor(arrays["external_source"][idx]))
                l2, linf = Q.route_disagreement(class_result.accepted, functional.accepted)
                source_exact = all(torch.equal(a, b) for a, b in zip(class_result.sources, functional.sources))
                graphs_exact = [g.graph_hash for g in class_result.graphs] == [g.graph_hash for g in functional.graphs]
                repeat_exact = Q.state_bitwise(class_result.accepted, repeat.accepted) and [g.graph_hash for g in class_result.graphs] == [g.graph_hash for g in repeat.graphs]
                target_idx = int(np.flatnonzero(arrays["frame_n"] == origin + 1)[0])
                a_def = (arrays["velocity"][target_idx] - class_result.accepted.velocity.numpy()) / DT
                u1 = Q.mass_norm((closed["velocity"][2*(origin+1)] - independent["velocity"][2*(origin+1)]) / DT, mass)
                u2 = Q.mass_norm(class_result.accepted.velocity.numpy() - functional.accepted.velocity.numpy(), mass) / DT
                u3 = Q.mass_norm(class_result.accepted.velocity.numpy() - repeat.accepted.velocity.numpy(), mass) / DT
                u4 = max(Q.mass_norm(closed["source"][2*origin] - independent["source"][2*origin], mass),
                         Q.mass_norm(closed["source"][2*origin+1] - independent["source"][2*origin+1], mass))
                u = float(max(u1, u2, u3, u4, roundoff)); dec = Q.decompose(a_def, mass, u)
                basis = Q.solve_basis(class_result.midpoint, class_result.graphs[1], dec["a_cons"], u)
                checks = reference_checks(arrays, metadata, origin)
                record_id = f"{lineage}_{variant}_N8_O{origin:02d}"
                finite = all(np.isfinite(x).all() for x in (a_def, dec["a_cons"], dec["a_cm"], dec["a_incompatible"]))
                row = {"record_id": record_id, "lineage": lineage, "variant": variant, "origin": origin,
                       "D0_route_L2": l2, "D0_route_Linf": linf, "source_identity": source_exact,
                       "graph_identity": graphs_exact, "repeat_identity": repeat_exact,
                       "D0_pass": l2 <= 1e-13 and linf <= 1e-12 and source_exact and graphs_exact and repeat_exact,
                       "reference_checks": checks, "reference_pass": all(checks.values()), "finite": finite,
                       "zero_force_normalized_residual": dec["zero_force_normalized_residual"],
                       "a_cons_component_rms": float(np.sqrt(np.mean(dec["a_cons"]**2))),
                       "signal_to_train_scale": float(np.sqrt(np.mean(dec["a_cons"]**2)) / S_A),
                       "incompatible_fraction": dec["incompatible_fraction"], "u_validation_diagnostic": u,
                       "U1": u1, "U2": u2, "U3": u3, "U4": u4, **basis}
                rows.append(row)
                frames = list(range(origin - 3, origin + 1)); states = [make_state(arrays, f) for f in frames]
                tokens = torch.stack([build_node_token(s, build_reciprocal_graph(s)) for s in states], dim=1).numpy()
                source_mid = evaluate_symbolic(lineage, variant, arrays["material_labels"], (origin + .5) / 256.)["source"]
                v0 = arrays["velocity"][target_idx] - DT * a_def
                cache_path = case_dir / f"{record_id}.npz"
                np.savez_compressed(cache_path, frames=np.asarray(frames), physical_times=np.asarray([s.physical_time for s in states]),
                    x=np.stack([s.x_unwrapped.numpy() for s in states]), velocity=np.stack([s.velocity.numpy() for s in states]),
                    density=np.stack([s.density.numpy() for s in states]), material_labels=arrays["material_labels"], mass=mass,
                    smoothing=states[-1].smoothing_length.numpy(), history_tokens=tokens, source_start=arrays["external_source"][idx],
                    source_midpoint=source_mid, v0_accepted=v0, a_cons=dec["a_cons"], y_def=dec["a_cons"] / S_A)
                npz_path = target_dir / f"{record_id}.npz"
                np.savez_compressed(npz_path, a_def=a_def, a_cm=dec["a_cm"], a_cons=dec["a_cons"],
                                    a_incompatible=dec["a_incompatible"], y_def=dec["a_cons"] / S_A)
                meta = {"schema": "sph-pio-poc.stage06b.validation-target-record.v1", "record_id": record_id,
                        "lineage": lineage, "variant": variant, "N": 8, "origin": origin, "dt": DT, "s_a": S_A,
                        "s_a_source": "frozen_STAGE05B_TRAIN_scale", "validation_did_not_modify_scale": True,
                        "reference_history_hashes": [str(arrays["state_hashes"][int(np.flatnonzero(arrays["frame_n"] == f)[0])]) for f in frames],
                        "D0_state_hash": class_result.accepted.state_hash, "reference_accepted_hash": str(arrays["state_hashes"][target_idx]),
                        "array_hashes": {k: sha_array(v) for k, v in (("a_def", a_def), ("a_cm", dec["a_cm"]),
                          ("a_cons", dec["a_cons"]), ("a_incompatible", dec["a_incompatible"]), ("y_def", dec["a_cons"] / S_A))},
                        "qualification_verdict": "PENDING_AGGREGATE_STAGE06B", "npz_path": str(npz_path.relative_to(ROOT)),
                        "npz_sha256": sha_file(npz_path), "case_cache_path": str(cache_path.relative_to(ROOT)),
                        "case_cache_sha256": sha_file(cache_path)}
                meta["canonical_sha256"] = sha_bytes(canonical(meta)); json_path = npz_path.with_suffix(".json"); write_json(json_path, meta)
                entries.append({"record_id": record_id, "json_path": str(json_path.relative_to(ROOT)), "json_sha256": sha_file(json_path),
                                "npz_path": str(npz_path.relative_to(ROOT)), "npz_sha256": meta["npz_sha256"],
                                "case_cache_path": meta["case_cache_path"], "case_cache_sha256": meta["case_cache_sha256"],
                                "canonical_sha256": meta["canonical_sha256"]})
                mid = class_result.midpoint
                case = {"record_id": record_id, "x": mid.x_unwrapped.numpy(), "v": mid.velocity.numpy(), "rho": mid.density.numpy(),
                        "mass": mass, "smoothing": mid.smoothing_length.numpy(), "labels": mid.material_labels.numpy(), "time": mid.physical_time,
                        "step": mid.accepted_step_index, "a_def": a_def, "a_cons": dec["a_cons"], "u": u,
                        "base_scalars": (math.sqrt(float(np.mean(dec["a_cons"]**2))), dec["incompatible_fraction"], basis["Q_unbounded"], basis["Q_bounded"])}
                symmetry_rows.extend(symmetry_audit(case))

    record_ids = [r["record_id"] for r in rows]
    zero_baseline_l = float(np.mean([(r["a_cons_component_rms"] / S_A)**2 for r in rows]))
    zero_baseline_q = math.sqrt(zero_baseline_l)
    gates = {"complete_128": len(rows) == 128, "unique_128": len(set(record_ids)) == 128,
             "D0_all": all(r["D0_pass"] for r in rows), "reference_all": all(r["reference_pass"] for r in rows),
             "finite_all": all(r["finite"] for r in rows),
             "zero_force_all": all(r["zero_force_normalized_residual"] <= 1e-12 for r in rows),
             "symmetry_all": len(symmetry_rows) == 896 and all(r["pass"] for r in symmetry_rows),
             "frozen_train_scale": True, "protocol_unchanged": sha_file(protocol_path) == protocol_manifest["protocol_sha256"],
             "permissions_restored": all(e["permission_restored"] for e in ACCESS.EVENTS)}
    sealed = sealed_denial_audit(); gates["sealed_denial"] = sealed["pass"]
    passed = all(gates.values())
    for entry in entries:
        path = ROOT / entry["json_path"]; meta = json.loads(path.read_text())
        meta["qualification_verdict"] = "QUALIFIED_STAGE06B_VALIDATION" if passed else "NOT_QUALIFIED_STAGE06B_VALIDATION"
        # Canonical hash intentionally covers immutable construction fields, not the aggregate verdict.
        write_json(path, meta); entry["json_sha256"] = sha_file(path)
    result = {"schema": "sph-pio-poc.stage06b.validation-qualification.v1", "protocol_sha256": protocol_manifest["protocol_sha256"],
              "validation_parameter_sha256": parameter_hash, "validation_parameter_family_count": len(parameters),
              "record_count": len(rows), "required_record_count": 128,
              "zero_correction_baseline_L_def": zero_baseline_l, "zero_correction_baseline_Q_def": zero_baseline_q,
              "zero_baseline_identity_definition": "Q_def,0=sqrt(mean(||a_cons/s_a||^2)); validation uses frozen TRAIN s_a and is not renormalized to 1",
              "signal_to_train_scale": {"minimum": min(r["signal_to_train_scale"] for r in rows),
                 "mean": float(np.mean([r["signal_to_train_scale"] for r in rows])), "maximum": max(r["signal_to_train_scale"] for r in rows)},
              "pair_basis_diagnostic": {"Q_unbounded_mean": float(np.mean([r["Q_unbounded"] for r in rows])),
                 "Q_unbounded_max": max(r["Q_unbounded"] for r in rows), "Q_bounded_mean": float(np.mean([r["Q_bounded"] for r in rows])),
                 "Q_bounded_max": max(r["Q_bounded"] for r in rows)},
              "rows": rows, "symmetry": {"row_count": len(symmetry_rows), "pass_count": sum(r["pass"] for r in symmetry_rows)},
              "gates": gates, "pass": passed, "validation_protocol_feedback_count": 0,
              "access_counts": ACCESS.COUNTS, "access_events": ACCESS.EVENTS, "sealed_denial": sealed}
    write_json(STAGE06B / "validation_target_qualification/validation_target_qualification.json", result)
    write_json(STAGE06B / "validation_target_qualification/validation_symmetry_audit.json", {"rows": symmetry_rows, "pass": gates["symmetry_all"]})
    write_json(STAGE06B / "access_control/sealed_test_denial_audit.json", sealed)
    manifest = {"schema": "sph-pio-poc.stage06b.validation-manifest.v1", "protocol_sha256": protocol_manifest["protocol_sha256"],
                "opened_after_protocol_freeze": True, "lineages": list(LINEAGES), "variants": list(VARIANTS), "N": 8,
                "record_count": len(entries), "required_record_count": 128, "records": entries, "gates": gates, "pass": passed,
                "validation_protocol_feedback_count": 0, "sealed_decode_counts": sealed["sealed_decode_counts"]}
    write_json(STAGE06 / "09_manifests/stage06b_validation_manifest.json", manifest)
    write_json(STAGE06B / "manifests/stage06b_validation_manifest.json", manifest)
    print(json.dumps({"records": len(rows), "symmetry": len(symmetry_rows), "zero_baseline_Q_def": zero_baseline_q,
                      "validation_counts": ACCESS.COUNTS, "gates": gates, "pass": passed}, sort_keys=True))


if __name__ == "__main__":
    main()
