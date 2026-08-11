"""Bounded repeated-backward retention audit on a prospective Stage 05C-Q case."""

from __future__ import annotations

import gc
import json
from pathlib import Path
import sys

import torch
from torch.nn.attention import SDPBackend, sdpa_kernel


HERE = Path(__file__).resolve()
STAGE05CQ = HERE.parents[1]
sys.path.insert(0, str(STAGE05CQ / "qualification"))
import run_stage05cq_seed as cq

q = cq.q


def live_autograd_tensor_count() -> int:
    count = 0
    for item in gc.get_objects():
        try:
            if isinstance(item, torch.Tensor) and item.grad_fn is not None:
                count += 1
        except Exception:
            continue
    return count


def main() -> None:
    torch.set_num_threads(1)
    cases = cq.load_cases()
    origins = json.loads((STAGE05CQ / "blind_origin_selection/preregistered_blind_origins.json").read_text())
    selected = [cq.batch_for("LCDF_01", cases, origins)[0]]
    torch.manual_seed(20500521)
    model = q.D3CausalTemporalTransformerPIO().to(dtype=torch.float64, device="cpu")
    model.eval()
    adapter = q.DefectAdapter("D3", model)
    samples = []
    gc.collect()
    baseline = live_autograd_tensor_count()
    for repeat in range(6):
        with sdpa_kernel(SDPBackend.MATH):
            losses, gradients, traces = q.full_gradient(adapter, selected)
        finite = all(torch.isfinite(gradient).all() for gradient in gradients[0])
        del losses, gradients, traces
        gc.collect()
        samples.append({"repeat": repeat, "live_autograd_tensor_count": live_autograd_tensor_count(),
                        "finite_backward": bool(finite)})
    counts = [row["live_autograd_tensor_count"] for row in samples]
    monotonic = all(right > left for left, right in zip(counts, counts[1:]))
    result = {
        "schema": "sph-pio-poc.stage05cq.retained-autograd-audit.v1",
        "arm": "D3",
        "seed": 20500521,
        "record_id": selected[0].record_id,
        "repeat_count": 6,
        "baseline_live_autograd_tensor_count": baseline,
        "samples": samples,
        "monotonic_growth": monotonic,
        "maximum_minus_minimum": max(counts) - min(counts),
        "model_instances": 1,
        "full_gradient_backward_count": 12,
        "graph_rebuild_count": adapter.graph_rebuild_count,
        "optimizer_instances": 0,
        "optimizer_steps": 0,
        "persistent_parameter_updates": 0,
        "pass": all(row["finite_backward"] for row in samples) and not monotonic,
    }
    path = STAGE05CQ / "resources/retained_autograd_audit.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"counts": counts, "pass": result["pass"]}))


if __name__ == "__main__":
    main()
