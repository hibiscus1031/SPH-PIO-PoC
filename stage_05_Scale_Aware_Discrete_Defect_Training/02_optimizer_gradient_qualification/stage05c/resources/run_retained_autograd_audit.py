"""Bounded repeated-backward audit for retained autograd objects."""

from __future__ import annotations

import gc
import json
from pathlib import Path
import sys

import torch
from torch.nn.attention import SDPBackend, sdpa_kernel


HERE = Path(__file__).resolve()
STAGE05C = HERE.parents[1]
ROOT = HERE.parents[4]
sys.path.insert(0, str(STAGE05C / "qualification"))
import run_stage05c_arm as q


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
    cases = q.load_cases()
    selected = [cases["LCDF_01_VARIANT_MAIN_N8_O09"]]
    torch.manual_seed(20500501)
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
        samples.append({"repeat": repeat, "live_autograd_tensor_count": live_autograd_tensor_count(), "finite_backward": bool(finite)})
    counts = [row["live_autograd_tensor_count"] for row in samples]
    result = {
        "schema": "sph-pio-poc.stage05c.retained-autograd-audit.v1",
        "arm": "D3",
        "seed": 20500501,
        "repeat_count": 6,
        "baseline_live_autograd_tensor_count": baseline,
        "samples": samples,
        "monotonic_growth": all(right > left for left, right in zip(counts, counts[1:])),
        "maximum_minus_minimum": max(counts) - min(counts),
        "model_instances": 1,
        "full_gradient_backward_count": 12,
        "optimizer_instances": 0,
        "optimizer_steps": 0,
        "persistent_parameter_updates": 0,
        "pass": all(row["finite_backward"] for row in samples) and not all(right > left for left, right in zip(counts, counts[1:])),
    }
    path = STAGE05C / "resources/retained_autograd_audit.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"counts": counts, "pass": result["pass"]}))


if __name__ == "__main__":
    main()
