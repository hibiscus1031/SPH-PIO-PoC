#!/usr/bin/env python3
"""Quantify v0.1 single-seed sensitivity on the sealed development families."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
from scipy.stats import beta

REPO = Path(__file__).resolve().parents[4]
ROOT = REPO / "stage_02_Particle_Interaction_Operator/05_dataset/regularity_contract_v0_2"
AUDIT_PATH = ROOT / "manifests/run_stage02js_regularity_audit.py"
ORIGINAL_PATH = ROOT / "development_audit/original_gate_reproduction.json"
OUT = ROOT / "development_audit/single_seed_sensitivity.json"


def load_audit():
    spec = importlib.util.spec_from_file_location("stage02js_sensitivity_core", AUDIT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(AUDIT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cp(count: int, total: int = 256) -> list[float]:
    lo = 0.0 if count == 0 else float(beta.ppf(0.025, count, total - count + 1))
    hi = 1.0 if count == total else float(beta.ppf(0.975, count + 1, total - count))
    return [lo, hi]


def main() -> int:
    if OUT.exists():
        raise FileExistsError(OUT)
    audit = load_audit()
    contexts = {case_id: audit.context_from_record(case_id) for case_id in audit.PV_CASES}
    contexts.update(audit.new_contexts(("FAMILY_CROSSMODE_A",)))
    original = json.loads(ORIGINAL_PATH.read_text(encoding="utf-8"))
    selected = {row["case_id"]: row["permuted_null_ratio"] for row in original["rows"]}
    rows = []
    for case_id, context in sorted(contexts.items()):
        observed = audit.old_tv(context, context["field"])
        ratios = []
        for index in range(256):
            rng = np.random.Generator(np.random.PCG64(audit.seed64(20260207, case_id, index)))
            permutation = rng.permutation(len(context["field"]))
            ratios.append(observed / audit.old_tv(context, context["field"][permutation]))
        values = np.asarray(ratios, dtype=np.float64)
        pass_count = int(np.count_nonzero(values <= 0.8))
        chosen = selected[case_id]
        std = float(np.std(values, ddof=1))
        rows.append({
            "case_id": case_id, "family_id": context["family_id"],
            "particles_per_axis": context["particles_per_axis"], "path_membership": context["path_membership"],
            "historical_single_seed_ratio": chosen,
            "historical_ratio_percentile_in_256_case_hashed_permutations": float(np.count_nonzero(values <= chosen) / 256),
            "historical_ratio_z_score": float((chosen - np.mean(values)) / std),
            "ratio_distribution": {"min": float(np.min(values)), "mean": float(np.mean(values)), "std": std, "max": float(np.max(values))},
            "v0_1_gate_pass_count_across_256": pass_count,
            "v0_1_gate_pass_fraction_across_256": pass_count / 256.0,
            "v0_1_gate_pass_fraction_Clopper_Pearson_95": cp(pass_count),
            "historical_single_seed_gate": "PASS" if chosen <= 0.8 else "FAIL",
        })
    output = {
        "audit_version": "stage02js-v0.1-single-seed-sensitivity-0.2.0",
        "development_families_only": ["FAMILY_PV_EXISTING", "FAMILY_CROSSMODE_A"],
        "root_seed": 20260207, "permutation_count_per_case": 256,
        "ratio_threshold_changed": False, "seed_screening_used": False, "rows": rows,
        "family_resolution_summary": [
            {
                "family_id": family,
                "resolution_case_ids": [row["case_id"] for row in rows if row["family_id"] == family and "resolution" in row["path_membership"]],
                "historical_single_seed_ratios": [row["historical_single_seed_ratio"] for row in rows if row["family_id"] == family and "resolution" in row["path_membership"]],
                "gate_pass_fraction_range": [
                    min(row["v0_1_gate_pass_fraction_across_256"] for row in rows if row["family_id"] == family and "resolution" in row["path_membership"]),
                    max(row["v0_1_gate_pass_fraction_across_256"] for row in rows if row["family_id"] == family and "resolution" in row["path_membership"]),
                ],
            }
            for family in ("FAMILY_PV_EXISTING", "FAMILY_CROSSMODE_A")
        ],
    }
    OUT.write_text(json.dumps(output, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"case_count": len(rows), "selected_seed_gate_failures": sum(row["historical_single_seed_gate"] == "FAIL" for row in rows)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
