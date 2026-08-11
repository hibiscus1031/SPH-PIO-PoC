"""Diagnostic-only N12/N16 checks for the prospective Stage 05C-Q seed/origins."""

from __future__ import annotations

import gc
import importlib.util
import json
import math
from pathlib import Path
import sys
import time

import psutil
import torch
from torch.nn.attention import SDPBackend, sdpa_kernel


HERE = Path(__file__).resolve()
STAGE05CQ = HERE.parents[1]
ROOT = HERE.parents[4]
STAGE05C = ROOT / "stage_05_Scale_Aware_Discrete_Defect_Training/02_optimizer_gradient_qualification/stage05c"
DIAGNOSTIC_SOURCE = STAGE05C / "resolution_diagnostics/run_stage05c_resolution_diagnostics.py"
SEED = 20500521
PROCESS = psutil.Process()


def import_path(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


sys.path.insert(0, str(STAGE05C / "qualification"))
d = import_path("stage05c_diagnostic_primitives_for_q", DIAGNOSTIC_SOURCE)
access = import_path("stage05cq_diagnostic_access", STAGE05CQ / "access_control/stage05cq_train_access.py")
d.STAGE05C = STAGE05CQ
d.ACCESS = access
d.SEED = SEED
q = d.q
cq = import_path("stage05cq_formal_primitives_for_diagnostics", STAGE05CQ / "qualification/run_stage05cq_seed.py")


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_context(arm: str, resolution: int, case, model: torch.nn.Module):
    adapter = q.DefectAdapter(arm, model)
    params = tuple(parameter for _, parameter in adapter.named_parameters())
    names = [name for name, _ in adapter.named_parameters()]
    before = q.parameter_hash(model)
    losses, grads, traces = q.full_gradient(adapter, [case])
    flat = torch.cat([gradient.reshape(-1) for gradient in grads[0]])
    finite_backward = bool(torch.isfinite(flat).all())
    norm = float(torch.linalg.vector_norm(flat))
    positive_direction = tuple(gradient / max(norm, 1.0e-30) for gradient in grads[0])
    reverse = None
    fd = None
    if resolution == 12:
        reverse = q.reverse_jvp(adapter, [case], params, names, positive_direction, grads[0])
        theta_norm = math.sqrt(sum(float(parameter.detach().square().sum()) for parameter in params))
        theta_ref = max(theta_norm, math.sqrt(sum(parameter.numel() for parameter in params)) * 1.0e-3)
        fd = cq.extended_fd(adapter, [case], params, names, positive_direction, theta_ref,
                            reverse["reverse"], reverse["near_zero"], traces[0]["topology"],
                            SEED + q.LINEAGES.index(case.lineage) * 100000)
    descent = q.local_descent(adapter, [case], params, names, grads[0], losses, traces[0],
                              SEED + resolution * 1000 + q.LINEAGES.index(case.lineage) * 100)
    after = q.parameter_hash(model)
    result = {
        "arm": arm, "resolution": resolution, "seed": SEED, "lineage": case.lineage,
        "variant": case.variant, "origin": case.origin, "record_id": case.record_id,
        "uses_N8_s_a": True, "s_a": q.S_A, "loss_repeats": losses,
        "loss_repeat_exact": losses[0] == losses[1], "finite_backward": finite_backward,
        "gradient_L2": norm, "gradient_RMS": float(torch.sqrt(flat.square().mean())),
        "gradient_Linf": float(flat.abs().max()), "gradient_exact_nonzero_count": int((flat != 0).sum()),
        "reverse_jvp": reverse, "optimizer_path_fd": fd, "local_descent": descent,
        "parameter_hash_before": before, "parameter_hash_after": after, "parameter_unchanged": before == after,
        "diagnostic_pass": finite_backward and (reverse is None or reverse["pass"])
                           and (fd is None or fd["stable"]) and descent["window"] and before == after,
        "affects_N8_qualification": False, "forward_count": adapter.forward_count,
        "graph_rebuild_count": adapter.graph_rebuild_count,
    }
    del adapter, params, grads, traces, flat
    gc.collect()
    return result


def main() -> None:
    torch.set_num_threads(1)
    started = time.perf_counter()
    rss_start = PROCESS.memory_info().rss
    peak_rss = rss_start
    origins = json.loads((STAGE05CQ / "blind_origin_selection/preregistered_blind_origins.json").read_text())
    selected = {(row["resolution"], row["lineage"]): row for row in origins["resolution_diagnostics"]}
    identities = json.loads((STAGE05CQ / "blind_model_seeds/preregistered_blind_model_identities.json").read_text())["models"]
    decode = {
        "diagnostic_train_trajectory_npz_decode_count": 0,
        "diagnostic_train_trajectory_json_decode_count": 0,
        "validation_state_decode_count": 0,
        "validation_target_decode_count": 0,
        "sealed_formula_decode_count": 0,
        "sealed_state_decode_count": 0,
        "sealed_source_decode_count": 0,
        "sealed_target_decode_count": 0,
        "sealed_origin_decode_count": 0,
    }
    cases = {}
    provenance = {}
    for resolution in (12, 16):
        for lineage in q.LINEAGES:
            row = selected[(resolution, lineage)]
            case, prov = d.make_case(lineage, resolution, row["origin"], decode)
            cases[(resolution, lineage)] = case
            provenance[(resolution, lineage)] = {**prov, "selection_key": row["key"], "stage05c_origin_overlap": row["overlap"]}

    rows = []
    model_instances = 0
    for arm in ("D1", "D2", "D3"):
        torch.manual_seed(SEED)
        model = q.ARMS[arm]().to(dtype=torch.float64, device="cpu")
        model.eval()
        model_instances += 1
        expected = next(row for row in identities if row["arm"] == arm and row["seed"] == SEED)
        if q.parameter_hash(model) != expected["complete_parameter_sha256"]:
            raise RuntimeError(f"prospective diagnostic model identity mismatch: {arm}")
        for resolution in ((12, 16) if arm == "D3" else (12,)):
            for lineage in q.LINEAGES:
                with sdpa_kernel(SDPBackend.MATH):
                    result = run_context(arm, resolution, cases[(resolution, lineage)], model)
                result["input_provenance"] = provenance[(resolution, lineage)]
                result["prospective_seed"] = True
                result["prospective_origin"] = True
                rows.append(result)
                peak_rss = max(peak_rss, PROCESS.memory_info().rss)
                print(json.dumps({"arm": arm, "resolution": resolution, "lineage": lineage,
                                  "pass": result["diagnostic_pass"]}), flush=True)
        del model
        gc.collect()

    summary = {
        "schema": "sph-pio-poc.stage05cq.resolution-diagnostics.v1",
        "role": "DIAGNOSTIC_ONLY",
        "affects_N8_qualification": False,
        "modifies_s_a": False,
        "resolution_generalization_claim": False,
        "spatial_convergence_claim": False,
        "N8_s_a": q.S_A,
        "seed": SEED,
        "row_count": len(rows),
        "N12_row_count": sum(row["resolution"] == 12 for row in rows),
        "N16_row_count": sum(row["resolution"] == 16 for row in rows),
        "finite_backward_count": sum(row["finite_backward"] for row in rows),
        "N12_reverse_jvp_pass_count": sum(row["resolution"] == 12 and row["reverse_jvp"]["pass"] for row in rows),
        "N12_optimizer_path_fd_stable_count": sum(row["resolution"] == 12 and row["optimizer_path_fd"]["stable"] for row in rows),
        "local_descent_window_count": sum(row["local_descent"]["window"] for row in rows),
        "parameter_restoration_count": sum(row["parameter_unchanged"] for row in rows),
        "diagnostic_pass_count": sum(row["diagnostic_pass"] for row in rows),
        "model_instances": model_instances,
        "full_gradient_backward_count": len(rows) * 2,
        "reverse_jvp_count": sum(row["resolution"] == 12 for row in rows),
        "optimizer_path_FD_evaluation_path_count": sum(row["optimizer_path_fd"]["evaluation_path_count"] for row in rows if row["resolution"] == 12),
        "local_descent_forward_count": len(rows) * 12,
        "graph_rebuild_count": sum(row["graph_rebuild_count"] for row in rows),
        "decode_counts": decode,
        "wall_time_seconds": time.perf_counter() - started,
        "rss_start_bytes": rss_start,
        "peak_rss_bytes": peak_rss,
        "peak_rss_delta_bytes": peak_rss - rss_start,
        "optimizer_instances": 0,
        "optimizer_steps": 0,
        "persistent_parameter_updates": 0,
        "training_runs": 0,
        "neural_rollouts": 0,
        "performance_evaluations": 0,
        "pass": len(rows) == 24 and all(row["diagnostic_pass"] for row in rows),
        "rows": rows,
    }
    write_json(STAGE05CQ / "resolution_diagnostics/resolution_diagnostics.json", summary)
    print(json.dumps({"rows": len(rows), "pass": summary["pass"], "wall": summary["wall_time_seconds"]}), flush=True)


if __name__ == "__main__":
    main()
