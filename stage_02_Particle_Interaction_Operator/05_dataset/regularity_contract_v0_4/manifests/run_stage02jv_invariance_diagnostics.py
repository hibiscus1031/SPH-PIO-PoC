#!/usr/bin/env python3
"""Retain exact evidence for the frozen v0.4 direction-only invariance failure."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[4]
ROOT = REPO / "stage_02_Particle_Interaction_Operator/05_dataset/regularity_contract_v0_4"
CORE = ROOT / "manifests/run_stage02jv_development.py"
OUT = ROOT / "invariance/direction_only_roundoff_diagnostics.json"


def load_core():
    spec = importlib.util.spec_from_file_location("stage02jv_diag_core", CORE)
    if spec is None or spec.loader is None:
        raise RuntimeError(CORE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    if OUT.exists():
        raise FileExistsError(OUT)
    core = load_core(); jt = core.load_jt(); contexts = jt.dev_contexts(); rows = []
    for context in contexts.values():
        if "resolution" not in context["path_membership"]:
            continue
        field = core.matched_positive("DIRECTION_ONLY_SMOOTH", context)
        perms = jt.permutations(context["case_id"], len(field))
        baseline = core.evaluate(jt, context, field, perms)
        for scale in (0.1, 10.0):
            transformed = field * scale
            result = core.evaluate(jt, context, transformed, perms)
            q0 = np.linalg.norm(field, axis=1); q1 = np.linalg.norm(transformed, axis=1)
            rows.append({
                "case_id": context["case_id"], "family_id": context["family_id"], "scale": scale,
                "baseline": baseline, "transformed": result,
                "baseline_magnitude_span": float(np.max(q0) - np.min(q0)),
                "transformed_magnitude_span": float(np.max(q1) - np.min(q1)),
                "M_h_invariant_within_metric_tolerance": abs(result["M_h"] - baseline["M_h"]) <= 1e-14 + 1e-12 * abs(baseline["M_h"]),
                "p_mag_exact_invariance": result["p_mag"] == baseline["p_mag"],
                "p_dir_exact_invariance": result["p_dir"] == baseline["p_dir"],
                "p_any_exact_invariance": result["p_any"] == baseline["p_any"],
            })
    output = {
        "audit_version": "stage02jv-direction-only-roundoff-diagnostics-0.4.0",
        "diagnostic_only_no_gate_change": True, "rows": rows,
        "p_mag_failure_count": sum(not row["p_mag_exact_invariance"] for row in rows),
        "metric_or_threshold_changed": False,
    }
    OUT.write_text(json.dumps(output, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(rows), "p_mag_failures": output["p_mag_failure_count"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
