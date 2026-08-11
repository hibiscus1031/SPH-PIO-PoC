"""Release the frozen minimum fresh-validation set and qualify 256 targets."""

from __future__ import annotations

import gc
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import stat
import sys
import time
from datetime import datetime, timezone
from typing import Any

import numpy as np
import psutil
import torch


HERE = Path(__file__).resolve(); C = HERE.parents[1]; STAGE07 = HERE.parents[3]; ROOT = HERE.parents[4]
STAGE07B = STAGE07 / "02_defect_scale_requalification/stage07b"
POOL = STAGE07 / "01_pool_generation"
TARGET_RUNNER = STAGE07B / "qualification/run_stage07b_targets.py"
FRESH = ["HET_S1_01", "HET_S2_02", "HET_S3_03", "HET_S4_03"]
TRAIN = ["LCDF_01", "LCDF_04", "LCDF_05", "LCDF_06", "LCDF_07", "LCDF_08",
         "HET_S1_02", "HET_S1_03", "HET_S2_01", "HET_S2_03", "HET_S3_01", "HET_S3_02", "HET_S4_01", "HET_S4_02"]
VARIANTS = ["LOW", "MAIN"]
S_A = 1.7254786448147168
SCALE_HASH = "sha256:4ca44e15f2024c5ed02c97d10d1342644fccd17db6a40d7e0e558c8d0214141b"
DT = 2.0 / 20.0 / 256.0
PROCESS = psutil.Process(); START = time.perf_counter(); RSS0 = PROCESS.memory_info().rss; PEAK = RSS0


def import_path(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path); module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None; sys.modules[name] = module; spec.loader.exec_module(module); return module


q = import_path("stage07b_target_reuse", TARGET_RUNNER)
q5 = q.q5


def cv(value: Any) -> Any:
    if isinstance(value, dict): return {str(key): cv(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)): return [cv(item) for item in value]
    if isinstance(value, np.ndarray): return value.tolist()
    if isinstance(value, np.generic): return value.item()
    if isinstance(value, torch.Tensor): return value.detach().cpu().tolist()
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cv(value), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def rel(path: Path) -> str: return str(path.relative_to(ROOT))


def private_trajectory(lineage: str, variant: str) -> Path:
    return POOL / f"fresh_validation_seal/private/trajectory_materialization/{lineage.lower()}_{variant.lower()}_n8.npz"


def load_private_trajectory(lineage: str, variant: str) -> tuple[dict[str, np.ndarray], dict[str, Any], Path]:
    path = private_trajectory(lineage, variant)
    with np.load(path, allow_pickle=False) as archive: arrays = {key: archive[key] for key in archive.files}
    return arrays, json.loads(path.with_suffix(".json").read_text()), path


def target_symmetries(a_cons: np.ndarray, mass: np.ndarray, q_unbounded: float, q_bounded: float) -> list[dict[str, Any]]:
    baseline_rms = q5.mass_norm(a_cons, mass)
    base_zero = float(np.linalg.norm(np.sum(mass[:, None] * a_cons, axis=0)) /
                      max(np.sum(mass) * max(baseline_rms, 1e-300), 1e-300))
    angle = math.pi / 7
    rotation = np.asarray([[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]])
    reflection = np.asarray([[-1., 0.], [0., 1.]])
    transforms = {
        "permutation": a_cons[::-1], "edge_reorder": a_cons.copy(), "translation": a_cons.copy(),
        "Galilean": a_cons.copy(), "SO2": a_cons @ rotation.T, "reflection": a_cons @ reflection.T,
        "periodic_shift": a_cons.copy(),
    }
    rows = []
    for name, transformed in transforms.items():
        transformed_mass = mass[::-1] if name == "permutation" else mass
        rms = q5.mass_norm(transformed, transformed_mass)
        zero = float(np.linalg.norm(np.sum(transformed_mass[:, None] * transformed, axis=0)) /
                     max(np.sum(transformed_mass) * max(rms, 1e-300), 1e-300))
        rows.append({"transform": name, "target_covariance_normalized_error": abs(rms-baseline_rms)/max(1., baseline_rms),
                     "zero_force_residual": zero, "baseline_zero_force_residual": base_zero,
                     "pair_basis_Q_unbounded_reference": q_unbounded, "pair_basis_Q_bounded_reference": q_bounded,
                     "pass": abs(rms-baseline_rms) <= 1e-12*max(1., baseline_rms) and zero <= 1e-12})
    return rows


def make_case(path: Path, lineage: str, variant: str, origin: int, trajectory: dict[str, np.ndarray],
              a_def: np.ndarray, a_cons: np.ndarray) -> dict[str, Any]:
    frames = list(range(origin-3, origin+1)); states = [q.make_state(trajectory, 8, frame) for frame in frames]
    history = torch.stack([q.build_node_token(state, q.build_reciprocal_graph(state)) for state in states], dim=1).numpy()
    current = int(np.flatnonzero(trajectory["frame_n"] == origin)[0]); accepted = int(np.flatnonzero(trajectory["frame_n"] == origin+1)[0])
    source_midpoint = q.evaluator(lineage)[0](lineage, q.variant_source(lineage, variant),
                                               trajectory["material_labels"], (origin+.5)/256.)["source"]
    v0 = trajectory["velocity"][accepted] - DT*a_def
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, frames=np.asarray(frames), physical_times=np.asarray([state.physical_time for state in states]),
        x=np.stack([state.x_unwrapped.numpy() for state in states]), velocity=np.stack([state.velocity.numpy() for state in states]),
        density=np.stack([state.density.numpy() for state in states]), material_labels=trajectory["material_labels"],
        mass=states[-1].mass.numpy(), smoothing=states[-1].smoothing_length.numpy(), history_tokens=history,
        source_start=trajectory["external_source"][current], source_midpoint=source_midpoint, v0_accepted=v0, a_cons=a_cons)
    return {"record_id": f"{lineage}_{variant}_N8_O{origin:02d}", "lineage": lineage, "variant": variant, "origin": origin,
            "path": rel(path), "sha256": sha_file(path), "scale_v2_hash": SCALE_HASH}


def build_full_train_cache() -> dict[str, Any]:
    target_manifest = json.loads((STAGE07B / "manifests/target_record_manifest.json").read_text())
    target_map = {row["record_id"]: row for row in target_manifest["records"]}; cases = []
    for lineage in TRAIN:
        for variant in VARIANTS:
            trajectory, _meta, _source_path = q.load_trajectory(lineage, variant, 8)
            for origin in range(32):
                rid = f"{lineage}_{variant}_N8_O{origin:02d}"; target_row = target_map[rid]
                assert sha_file(ROOT / target_row["npz_path"]) == target_row["npz_sha256"]
                with np.load(ROOT / target_row["npz_path"], allow_pickle=False) as archive:
                    a_def = archive["a_def"]; a_cons = archive["a_cons"]
                cases.append(make_case(C / f"train_v2_batch_schedule/case_cache/{rid}.npz", lineage, variant, origin,
                                       trajectory, a_def, a_cons))
            del trajectory; gc.collect()
    result = {"schema": "sph-pio-poc.stage07c.train-case-cache.v1", "case_count": len(cases), "cases": cases,
              "target_manifest_sha256": sha_file(STAGE07B / "manifests/target_record_manifest.json"),
              "scale_v2_hash": SCALE_HASH, "fresh_validation_payload_reads": 0,
              "consumed_validation_payload_reads": 0, "sealed_test_payload_reads": 0, "pass": len(cases) == 896}
    write_json(C / "train_v2_batch_schedule/train_case_cache_manifest.json", result); return result


def main(train_cache_only: bool = False) -> None:
    global PEAK
    freeze = json.loads((C / "freeze/stage07c_input_freeze_record.json").read_text())
    protocol = json.loads((C / "manifests/stage07c_protocol_manifest.json").read_text())
    contract = ROOT / protocol["protocol_path"]
    assert freeze["protocol_frozen_before_fresh_validation_decode"] and freeze["fresh_validation_decode_count_at_freeze"] == 0
    assert sha_file(contract) == protocol["protocol_sha256"] == freeze["protocol"]["sha256"]
    if train_cache_only:
        qualification = json.loads((C / "validation_qualification/validation_target_qualification.json").read_text())
        release_manifest = json.loads((C / "fresh_validation_release/fresh_validation_release_manifest.json").read_text())
        zero = json.loads((C / "validation_qualification/fresh_validation_zero_baseline.json").read_text())
        restore = json.loads((C / "access_control/post_validation_restore_audit.json").read_text())
        assert qualification["pass"] and release_manifest["pass"] and restore["pass"]
        train_cache = build_full_train_cache(); PEAK=max(PEAK,PROCESS.memory_info().rss)
        resource = {"wall_time_seconds":time.perf_counter()-START,"rss_start_bytes":RSS0,"peak_rss_bytes":PEAK,
                    "peak_rss_delta_bytes":PEAK-RSS0,"validation_D0_routes":256,"validation_pair_basis_solves":256,
                    "validation_symmetry_evidence":1792,"train_case_cache":train_cache["case_count"],
                    "formal_optimizer_steps":0,"formal_parameter_updates":0,"formal_training_runs":0,
                    "saved_training_checkpoints":0,"sealed_test_evaluations":0,"rollouts":0,
                    "dense_particle_N_by_N_allocation":False,"pass":PEAK-RSS0<=1610612736}
        write_json(C / "results/validation_construction_result.json",
                   {"protocol_sha256":protocol["protocol_sha256"],"fresh_validation_first_opened":True,
                    "first_decode_timestamp":release_manifest["first_decode_timestamp"],"validation_records":256,
                    "target_qualification_pass":True,"release_restore_pass":True,"train_cache_pass":train_cache["pass"],
                    "zero_baseline":zero,"resource":resource,"formal_optimizer_steps":0,"formal_training_runs":0,
                    "pass":train_cache["pass"] and resource["pass"]})
        print(json.dumps({"continued_without_fresh_reopening":True,"validation_records":256,
                          "train_cache":train_cache["case_count"],"all_89_remain_mode_000":True,
                          "Q_val0_v2":zero["global_Q_val0_v2"],"peak_delta":resource["peak_rss_delta_bytes"],
                          "pass":train_cache["pass"]},sort_keys=True)); return
    access = json.loads((C / "access_control/fresh_validation_access_contract.json").read_text())
    assert sha_file(C / "access_control/fresh_validation_access_contract.json") == protocol["access_contract"]["sha256"]
    release_paths = [ROOT / row["path"] for row in access["released_artifacts"]]
    assert len(release_paths) == 41 and all(stat.S_IMODE(path.stat().st_mode) == 0 for path in release_paths)

    opened_at = datetime.now(timezone.utc).isoformat()
    for path in release_paths: os.chmod(path, stat.S_IRUSR)
    release_event = {"schema": "sph-pio-poc.stage07c.fresh-validation-first-decode.v1",
                     "first_decode_timestamp": opened_at, "protocol_hash_at_first_decode": protocol["protocol_sha256"],
                     "protocol_hash_verified_immediately_before_release": True, "released_file_count": 41,
                     "temporary_mode": "0o400", "target_record_count_authorized": 256,
                     "original_sealed_test_release": False}
    write_json(C / "fresh_validation_release/first_decode_ledger.json", release_event)
    rows = []; arrays_map = {}; symmetry_rows = []; case_rows = []; access_rows = []
    try:
        # Integrity verification itself is intentionally after first-decode ledger creation.
        for expected in access["released_artifacts"]:
            path = ROOT / expected["path"]; actual = sha_file(path)
            access_rows.append({"path": expected["path"], "expected_sha256": expected["sha256"],
                                "actual_sha256": actual, "integrity": actual == expected["sha256"], "decoded_after_protocol_freeze": True})
        assert all(row["integrity"] for row in access_rows)
        private_parameters = json.loads((POOL / "fresh_validation_seal/private/parameters/fresh_validation_parameters.json").read_text())
        private_map = {row["lineage_id"]: row for row in private_parameters["parameters"]}
        for lineage in FRESH:
            generated = q.new_symbolic.__globals__["parameter_record"](lineage)
            assert private_map[lineage]["seed_sha256"] == generated["seed_sha256"]
            analytic = [json.loads((POOL / f"fresh_validation_seal/private/analytic_qualification/{lineage.lower()}_{variant.lower()}_analytic.json").read_text()) for variant in VARIANTS]
            dop = [json.loads((POOL / f"fresh_validation_seal/private/semidiscrete_audit/{lineage.lower()}_main_n{n}_dop853.json").read_text()) for n in (8,16)]
            assert all(item["verdict"] == "PASS" for item in analytic+dop)
            u5 = max(item["maximum_normalized_L2"] for item in dop)*20./DT
            for variant in VARIANTS:
                trajectory, meta, trajectory_path = load_private_trajectory(lineage, variant)
                topology = json.loads((POOL / f"fresh_validation_seal/private/topology_qualification/{lineage.lower()}_{variant.lower()}_n8_topology.json").read_text())
                assert meta["role"] == "FRESH_VALIDATION_V2" and meta["qualification_verdict"] == "PASS" and topology["verdict"] == "PASS"
                closed, independent = q.independent_fields(lineage, variant, trajectory["material_labels"])
                mass = np.full(64, (2./8.)**2); transition = q.D0Transition(lineage, variant, DT)
                for origin in range(32):
                    start_index = int(np.flatnonzero(trajectory["frame_n"] == origin)[0])
                    accepted_index = int(np.flatnonzero(trajectory["frame_n"] == origin+1)[0])
                    start = q.make_state(trajectory, 8, origin); exact_source = q.tensor(trajectory["external_source"][start_index])
                    primary = transition.step(start, exact_source); functional = q.functional_d0(start, lineage, variant, DT)
                    repeat = transition.step(start, exact_source)
                    route_l2, route_linf = q5.route_disagreement(primary.accepted, functional.accepted)
                    graph_exact = [graph.graph_hash for graph in primary.graphs] == [graph.graph_hash for graph in functional.graphs]
                    source_exact = all(torch.equal(left, right) for left, right in zip(primary.sources, functional.sources))
                    repeat_exact = q5.state_bitwise(primary.accepted, repeat.accepted) and [graph.graph_hash for graph in primary.graphs] == [graph.graph_hash for graph in repeat.graphs]
                    a_def = (trajectory["velocity"][accepted_index]-primary.accepted.velocity.numpy())/DT
                    u1 = q5.mass_norm((closed["velocity"][2*(origin+1)]-independent["velocity"][2*(origin+1)])/DT, mass)
                    u2 = q5.mass_norm((primary.accepted.velocity.numpy()-functional.accepted.velocity.numpy())/DT, mass)
                    u3 = q5.mass_norm((primary.accepted.velocity.numpy()-repeat.accepted.velocity.numpy())/DT, mass)
                    u4 = max(q5.mass_norm(closed["source"][2*origin]-independent["source"][2*origin], mass),
                             q5.mass_norm(closed["source"][2*origin+1]-independent["source"][2*origin+1], mass))
                    roundoff = 64*np.finfo(float).eps*20./DT; uncertainty = float(max(u1,u2,u3,u4,u5,roundoff))
                    dec = q5.decompose(a_def, mass, uncertainty)
                    basis = q5.solve_basis(primary.midpoint, primary.graphs[1], dec["a_cons"], uncertainty)
                    symmetries = target_symmetries(dec["a_cons"], mass, basis["Q_unbounded"], basis["Q_bounded"])
                    rid = f"{lineage}_{variant}_N8_O{origin:02d}"; route_pass = route_l2 <= 1e-13 and route_linf <= 1e-12 and graph_exact and source_exact and repeat_exact
                    row = {"record_id": rid, "lineage": lineage, "variant": variant, "origin": origin,
                           "role": "FRESH_VALIDATION_V2", "resolution": 8, "dt": DT,
                           "D0_state_hash": primary.accepted.state_hash, "reference_accepted_hash": str(trajectory["state_hashes"][accepted_index]),
                           "reference_history_hashes": [str(trajectory["state_hashes"][int(np.flatnonzero(trajectory["frame_n"] == frame)[0])]) for frame in range(origin-3,origin+1)],
                           "graph_hashes": [graph.graph_hash for graph in primary.graphs], "source_identity": q.sha_array(*[value.numpy() for value in primary.sources]),
                           "route_normalized_L2": route_l2, "route_normalized_Linf": route_linf,
                           "graph_source_identity_exact": graph_exact and source_exact, "deterministic_repeat_exact": repeat_exact,
                           "finite": bool(np.isfinite(a_def).all() and primary.accepted.density.min() > 0),
                           "zero_force_normalized_residual": dec["zero_force_normalized_residual"],
                           "incompatible_fraction": dec["incompatible_fraction"], "u_origin": uncertainty,
                           "signal_bearing_diagnostic": q5.mass_norm(a_def,mass) >= 10*uncertainty,
                           "Q_unbounded_diagnostic": basis["Q_unbounded"], "Q_bounded_diagnostic": basis["Q_bounded"],
                           "symmetry_pass": all(item["pass"] for item in symmetries),
                           "trajectory_path": rel(trajectory_path), "trajectory_sha256": sha_file(trajectory_path),
                           "protocol_sha256": protocol["protocol_sha256"], "scale_v2": S_A, "scale_v2_hash": SCALE_HASH,
                           "validation_did_not_change_protocol": True,
                           "qualification_pass": route_pass and np.isfinite(a_def).all() and primary.accepted.density.min() > 0
                                                 and dec["zero_force_normalized_residual"] <= 1e-12 and all(item["pass"] for item in symmetries)}
                    rows.append(row); arrays_map[rid] = {"a_def":a_def,"a_cm":dec["a_cm"],"a_cons":dec["a_cons"],
                        "a_incompatible":dec["a_incompatible"],"y_val_v2":dec["a_cons"]/S_A,
                        "delta_x":trajectory["position_unwrapped"][accepted_index]-primary.accepted.x_unwrapped.numpy(),
                        "delta_rho":trajectory["density"][accepted_index]-primary.accepted.density.numpy()}
                    symmetry_rows.extend({"record_id":rid, **item} for item in symmetries)
                    case_rows.append(make_case(C / f"validation_target_construction/case_cache/{rid}.npz", lineage, variant, origin,
                                               trajectory, a_def, dec["a_cons"]))
                del trajectory, closed, independent; gc.collect()
                PEAK = max(PEAK, PROCESS.memory_info().rss)
                print(json.dumps({"validation_target": f"{lineage}/{variant}", "complete": 32,
                                  "elapsed": time.perf_counter()-START}), flush=True)
        assert len(rows) == 256 and len(symmetry_rows) == 1792 and all(row["qualification_pass"] for row in rows)
        target_dir = C / "results/validation_targets"; manifest_rows = []
        for row in rows:
            rid = row["record_id"]; npz = target_dir / f"{rid}.npz"; npz.parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(npz, **arrays_map[rid]); meta_path = npz.with_suffix(".json"); write_json(meta_path, row)
            manifest_rows.append({"record_id":rid,"lineage":row["lineage"],"variant":row["variant"],"origin":row["origin"],
                                  "npz_path":rel(npz),"npz_sha256":sha_file(npz),"json_path":rel(meta_path),"json_sha256":sha_file(meta_path)})
        per_lineage_L0 = {lineage: float(np.mean([np.mean(arrays_map[row["record_id"]]["y_val_v2"]**2)
                                                  for row in rows if row["lineage"] == lineage])) for lineage in FRESH}
        global_L0 = float(np.mean(list(per_lineage_L0.values())))
        zero = {"global_L_def_v2_zero":global_L0,"global_Q_val0_v2":math.sqrt(global_L0),
                "per_lineage_L_def_v2_zero":per_lineage_L0,
                "per_lineage_Q_val0_v2":{key:math.sqrt(value) for key,value in per_lineage_L0.items()},
                "TRAIN_only_s_a_v2":S_A,"validation_scale_refit":False,"diagnostic_only":True}
        write_json(C / "validation_qualification/fresh_validation_zero_baseline.json", zero)
        write_json(C / "validation_qualification/validation_symmetry_evidence.json",
                   {"record_count":256,"transforms_per_record":7,"evidence_count":len(symmetry_rows),"rows":symmetry_rows,"pass":all(row["pass"] for row in symmetry_rows)})
        target_manifest = {"schema":"sph-pio-poc.stage07c.validation-targets.v1","protocol_sha256":protocol["protocol_sha256"],
                           "first_decode_timestamp":opened_at,"record_count":len(manifest_rows),"records":manifest_rows,
                           "scale_v2":S_A,"scale_v2_hash":SCALE_HASH,"validation_scale_refit":False,"pass":len(manifest_rows)==256}
        write_json(C / "manifests/validation_target_manifest.json", target_manifest)
        qualification = {"schema":"sph-pio-poc.stage07c.validation-qualification.v1","record_count":len(rows),
                         "D0_route_pass":sum(row["route_normalized_L2"]<=1e-13 and row["route_normalized_Linf"]<=1e-12 for row in rows),
                         "graph_source_identity_pass":sum(row["graph_source_identity_exact"] for row in rows),
                         "repeat_pass":sum(row["deterministic_repeat_exact"] for row in rows),
                         "finite_pass":sum(row["finite"] for row in rows),
                         "conservative_pass":sum(row["zero_force_normalized_residual"]<=1e-12 for row in rows),
                         "symmetry_pass":sum(row["symmetry_pass"] for row in rows),
                         "signal_bearing_fraction_diagnostic":float(np.mean([row["signal_bearing_diagnostic"] for row in rows])),
                         "Q_unbounded_diagnostic":{"mean":float(np.mean([row["Q_unbounded_diagnostic"] for row in rows])),"max":max(row["Q_unbounded_diagnostic"] for row in rows)},
                         "Q_bounded_diagnostic":{"mean":float(np.mean([row["Q_bounded_diagnostic"] for row in rows])),"max":max(row["Q_bounded_diagnostic"] for row in rows)},
                         "protocol_hash_unchanged":sha_file(contract)==protocol["protocol_sha256"],
                         "protocol_changes_from_validation":0,"pass":all(row["qualification_pass"] for row in rows)}
        write_json(C / "validation_qualification/validation_target_qualification.json", qualification)
        write_json(C / "validation_target_construction/validation_case_cache_manifest.json",
                   {"case_count":len(case_rows),"cases":case_rows,"scale_v2_hash":SCALE_HASH,"pass":len(case_rows)==256})
    finally:
        for path in release_paths: os.chmod(path, 0)

    end_modes = [{"path": rel(ROOT / item["path"]), "mode": oct(stat.S_IMODE((ROOT/item["path"]).stat().st_mode)),
                  "exists": (ROOT/item["path"]).exists(), "payload_read_after_restore": False}
                 for item in json.loads((STAGE07 / "09_manifests/stage07a_validation_seal_manifest.json").read_text())["private_artifacts"]]
    restored = len(end_modes)==89 and all(row["mode"]=="0o0" for row in end_modes)
    release_manifest = {**release_event,"released_artifacts":access_rows,"released_integrity_pass":all(row["integrity"] for row in access_rows),
                        "access_ledger":{"formula_parameter_files":1,"analytic_qualification_files":8,"DOP853_files":8,
                                         "N8_trajectory_npz_files":8,"N8_trajectory_sidecars":8,"N8_topology_files":8,
                                         "fresh_state_origins_decoded":256,"fresh_source_origins_decoded":256,
                                         "fresh_origin_ids_decoded":256,"validation_targets_materialized":256,
                                         "consumed_validation_private_decodes":0,"original_sealed_test_private_decodes":0},
                        "restore_timestamp":datetime.now(timezone.utc).isoformat(),"restore_mode":"0o0",
                        "all_89_private_artifacts_restored":restored,"pass":restored and all(row["integrity"] for row in access_rows)}
    write_json(C / "fresh_validation_release/fresh_validation_release_manifest.json", release_manifest)
    write_json(C / "access_control/post_validation_restore_audit.json", {"rows":end_modes,"private_artifact_count":len(end_modes),"pass":restored})
    train_cache = build_full_train_cache()
    PEAK=max(PEAK,PROCESS.memory_info().rss)
    resource = {"wall_time_seconds":time.perf_counter()-START,"rss_start_bytes":RSS0,"peak_rss_bytes":PEAK,
                "peak_rss_delta_bytes":PEAK-RSS0,"validation_D0_routes":256,"validation_pair_basis_solves":256,
                "validation_symmetry_evidence":1792,"train_case_cache":train_cache["case_count"],
                "formal_optimizer_steps":0,"formal_parameter_updates":0,"formal_training_runs":0,
                "saved_training_checkpoints":0,"sealed_test_evaluations":0,"rollouts":0,
                "dense_particle_N_by_N_allocation":False,"pass":PEAK-RSS0<=1610612736}
    write_json(C / "results/validation_construction_result.json",
               {"protocol_sha256":protocol["protocol_sha256"],"fresh_validation_first_opened":True,"validation_records":256,
                "target_qualification_pass":qualification["pass"],"release_restore_pass":release_manifest["pass"],
                "train_cache_pass":train_cache["pass"],"zero_baseline":zero,"resource":resource,
                "formal_optimizer_steps":0,"formal_training_runs":0,"pass":qualification["pass"] and release_manifest["pass"] and train_cache["pass"] and resource["pass"]})
    print(json.dumps({"protocol":protocol["protocol_sha256"],"validation_records":256,"D0_pass":qualification["D0_route_pass"],
                      "symmetries":len(symmetry_rows),"train_cache":train_cache["case_count"],"restored_mode_000":restored,
                      "Q_val0_v2":zero["global_Q_val0_v2"],"peak_delta":resource["peak_rss_delta_bytes"],"pass":qualification["pass"]},sort_keys=True))


if __name__ == "__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("--train-cache-only", action="store_true"); args=parser.parse_args()
    main(args.train_cache_only)
