#!/usr/bin/env python3
"""Execute the frozen Stage 02J-T blind generator after eligibility freeze."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import yaml

REPO = Path(__file__).resolve().parents[4]
STAGE = REPO / "stage_02_Particle_Interaction_Operator"
ROOT = STAGE / "05_dataset/blind_multifamily_pair_scope_v1_0"
FREEZE_PATH = ROOT / "freeze/stage02jw_input_freeze_manifest.json"
CONTRACT_PATH = ROOT / "eligibility_contract/blind_dataset_eligibility_contract_v1_0.yaml"
GENERATOR_PATH = STAGE / "05_dataset/regularity_contract_v0_3/blind_family_generator/generate_blind_families.py"
GENERATOR_FREEZE_PATH = STAGE / "05_dataset/regularity_contract_v0_3/blind_family_generator/blind_generator_freeze.yaml"
OUT = ROOT / "blind_family_materialization/blind_family_formulas.json"


def file_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def load_module() -> Any:
    spec = importlib.util.spec_from_file_location("stage02jw_frozen_generator", GENERATOR_PATH)
    if spec is None or spec.loader is None: raise RuntimeError(GENERATOR_PATH)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


def term(basis: str, amplitude: float, mode: list[int] | tuple[int, int], phase: float) -> str:
    return f"({amplitude:.17g})*{basis}(2*pi*(({mode[0]})*x+({mode[1]})*y)+({phase:.17g}))"


def main() -> int:
    if OUT.exists(): raise FileExistsError(OUT)
    freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    if file_hash(CONTRACT_PATH) != freeze["eligibility_contract_hash"]: raise RuntimeError("Eligibility contract hash mismatch")
    if file_hash(GENERATOR_PATH) != freeze["blind_generator_source_hash"]: raise RuntimeError("Frozen generator source mismatch")
    if file_hash(GENERATOR_FREEZE_PATH) != freeze["blind_generator_configuration_hash"]: raise RuntimeError("Frozen generator configuration mismatch")
    generator = load_module(); config = yaml.safe_load(GENERATOR_FREEZE_PATH.read_text(encoding="utf-8")); pool = [tuple(mode) for mode in config["mode_pool"]]
    families = []
    for spec in config["families"]:
        rng = np.random.Generator(np.random.PCG64(int(spec["root_seed"])))
        density_modes = [pool[index] for index in rng.choice(len(pool), size=3, replace=False)]
        ux_modes = [pool[index] for index in rng.choice(len(pool), size=4, replace=False)]
        uy_modes = [pool[index] for index in rng.choice(len(pool), size=4, replace=False)]
        density_amplitudes = generator.amplitudes(rng, 3, 0.0045); density_phases = rng.uniform(0.0, 2.0 * math.pi, size=3).tolist()
        ux_amplitudes = generator.amplitudes(rng, 4, 0.018); ux_phases = rng.uniform(0.0, 2.0 * math.pi, size=4).tolist()
        uy_amplitudes = generator.amplitudes(rng, 4, 0.018); uy_phases = rng.uniform(0.0, 2.0 * math.pi, size=4).tolist()
        density = {"modes": [list(x) for x in density_modes], "amplitudes": density_amplitudes, "phases": density_phases, "basis": "cos"}
        ux = {"modes": [list(x) for x in ux_modes], "amplitudes_over_cs": ux_amplitudes, "phases": ux_phases, "basis": "sin"}
        uy = {"modes": [list(x) for x in uy_modes], "amplitudes_over_cs": uy_amplitudes, "phases": uy_phases, "basis": "sin"}
        formula = {
            "family_id": spec["family_id"], "role": spec["role"], "root_seed": int(spec["root_seed"]),
            "lineage_id": f"{spec['family_id']}_PCG64_{spec['root_seed']}_FROZEN_V1",
            "density": density, "velocity_x": ux, "velocity_y": uy,
            "rho_formula": "rho0*(1+" + "+".join(term("cos", a, m, p) for a, m, p in zip(density_amplitudes, density_modes, density_phases)) + ")",
            "ux_formula": "cs*(" + "+".join(term("sin", a, m, p) for a, m, p in zip(ux_amplitudes, ux_modes, ux_phases)) + ")",
            "uy_formula": "cs*(" + "+".join(term("sin", a, m, p) for a, m, p in zip(uy_amplitudes, uy_modes, uy_phases)) + ")",
            "derivative_definition": {
                "grad_p": "cs^2*rho0*sum[-a*2*pi*(kx,ky)*sin(2*pi*(kx*x+ky*y)+phase)]",
                "laplacian_velocity": "cs*sum[-b*(2*pi)^2*(kx^2+ky^2)*sin(2*pi*(kx*x+ky*y)+phase)]_per_component",
                "acceleration": "-grad_p/rho+nu*laplacian_velocity",
            },
            "density_relative_bounds": [1.0 - sum(abs(x) for x in density_amplitudes), 1.0 + sum(abs(x) for x in density_amplitudes)],
            "density_amplitude_absolute_sum": sum(abs(x) for x in density_amplitudes),
            "velocity_component_L1": [sum(abs(x) for x in ux_amplitudes), sum(abs(x) for x in uy_amplitudes)],
            "analytic_Mach_upper_bound": math.sqrt(sum(abs(x) for x in ux_amplitudes) ** 2 + sum(abs(x) for x in uy_amplitudes) ** 2),
            "mode_inventory": {"density": [list(x) for x in density_modes], "velocity_x": [list(x) for x in ux_modes], "velocity_y": [list(x) for x in uy_modes]},
            "result_dependent_regeneration_used": False,
        }
        formula["formula_hash"] = canonical_hash({key: value for key, value in formula.items() if key not in ("formula_hash", "derivative_hash")})
        formula["derivative_hash"] = canonical_hash(formula["derivative_definition"] | {"density": density, "velocity_x": ux, "velocity_y": uy})
        families.append(formula)
    output = {
        "materialization_version": "stage02jw-frozen-blind-generator-1.0.0",
        "eligibility_contract_hash": freeze["eligibility_contract_hash"],
        "generator_source_hash": file_hash(GENERATOR_PATH), "generator_configuration_hash": file_hash(GENERATOR_FREEZE_PATH),
        "generator_hashes_match_frozen": True, "family_count": 4, "families": families,
        "materialized_after_eligibility_contract_hash": True, "family_replacement_or_redraw_used": False,
    }
    OUT.write_text(json.dumps(output, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"families": 4, "hashes_match": True, "formula_hashes": [x["formula_hash"] for x in families]}, sort_keys=True))
    return 0


if __name__ == "__main__": raise SystemExit(main())

