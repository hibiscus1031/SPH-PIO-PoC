#!/usr/bin/env python3
"""Materialize the four preregistered blind analytic families after v0.3 freeze."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import yaml

REPO = Path(__file__).resolve().parents[4]
ROOT = REPO / "stage_02_Particle_Interaction_Operator/05_dataset/regularity_contract_v0_3"
FREEZE = ROOT / "blind_family_generator/blind_generator_freeze.yaml"
CONTRACT = ROOT / "contract_design/regularity_contract_v0_3.yaml"
AUTH = ROOT / "contract_design/v03_contract_authorization.json"
OUT = ROOT / "blind_family_generator/blind_family_formulas.json"


def file_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def amplitudes(rng: np.random.Generator, count: int, l1: float) -> list[float]:
    weights = rng.uniform(0.25, 1.0, size=count)
    weights *= l1 / float(np.sum(weights))
    signs = rng.choice(np.asarray([-1.0, 1.0]), size=count)
    return (weights * signs).tolist()


def main() -> int:
    if OUT.exists():
        raise FileExistsError(OUT)
    if not CONTRACT.is_file() or not AUTH.is_file():
        raise RuntimeError("v0.3 contract is not frozen and authorized")
    authorization = json.loads(AUTH.read_text(encoding="utf-8"))
    if not authorization["blind_formula_materialization_authorized"] or authorization["contract_hash"] != file_hash(CONTRACT):
        raise RuntimeError("v0.3 contract authorization/hash mismatch")
    freeze = yaml.safe_load(FREEZE.read_text(encoding="utf-8"))
    pool = [tuple(mode) for mode in freeze["mode_pool"]]
    families = []
    for spec in freeze["families"]:
        rng = np.random.Generator(np.random.PCG64(int(spec["root_seed"])))
        density_modes = [pool[index] for index in rng.choice(len(pool), size=3, replace=False)]
        ux_modes = [pool[index] for index in rng.choice(len(pool), size=4, replace=False)]
        uy_modes = [pool[index] for index in rng.choice(len(pool), size=4, replace=False)]
        family = {
            **spec,
            "density": {
                "modes": [list(mode) for mode in density_modes],
                "amplitudes": amplitudes(rng, 3, 0.0045),
                "phases": rng.uniform(0.0, 2.0 * math.pi, size=3).tolist(),
                "basis": "cos(2*pi*(kx*x+ky*y)+phase)",
            },
            "velocity_x": {
                "modes": [list(mode) for mode in ux_modes],
                "amplitudes_over_cs": amplitudes(rng, 4, 0.018),
                "phases": rng.uniform(0.0, 2.0 * math.pi, size=4).tolist(),
                "basis": "sin(2*pi*(kx*x+ky*y)+phase)",
            },
            "velocity_y": {
                "modes": [list(mode) for mode in uy_modes],
                "amplitudes_over_cs": amplitudes(rng, 4, 0.018),
                "phases": rng.uniform(0.0, 2.0 * math.pi, size=4).tolist(),
                "basis": "sin(2*pi*(kx*x+ky*y)+phase)",
            },
            "density_amplitude_absolute_sum": 0.0045,
            "velocity_component_L1": 0.018,
            "analytic_Mach_upper_bound": math.sqrt(2.0) * 0.018,
            "posthoc_rejection_or_replacement_used": False,
        }
        family["formula_hash"] = canonical_hash(family)
        families.append(family)
    output = {
        "generator_version": "stage02jt-blind-family-materialization-0.3.0",
        "generator_source_hash": file_hash(Path(__file__)),
        "generator_freeze_hash": file_hash(FREEZE),
        "contract_hash": file_hash(CONTRACT),
        "family_count": 4, "families": families,
        "formula_materialization_after_contract_freeze": True,
        "family_replacement_used": False,
    }
    OUT.write_text(json.dumps(output, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"families": 4, "contract_hash": output["contract_hash"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
