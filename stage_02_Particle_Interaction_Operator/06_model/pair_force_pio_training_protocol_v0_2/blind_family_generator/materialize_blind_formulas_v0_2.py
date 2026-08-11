#!/usr/bin/env python3
"""Single materialization of the two protocol-v0.2 blind formulas after protocol hash."""

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
ROOT = STAGE / "06_model/pair_force_pio_training_protocol_v0_2"
SOURCE = STAGE / "05_dataset/regularity_contract_v0_3/blind_family_generator/generate_blind_families.py"
CONFIG = ROOT / "blind_family_generator/blind_generator_config_v0_2.yaml"
PROTOCOL = ROOT / "freeze/training_protocol_v0_2.yaml"
HASH_RECORD = ROOT / "freeze/protocol_v0_2_hash.json"
OUT = ROOT / "blind_family_generator/blind_family_formulas_v0_2.json"


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def content_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def load_module() -> Any:
    spec = importlib.util.spec_from_file_location("stage02mp_frozen_generator", SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError(SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def term(basis: str, amplitude: float, mode: tuple[int, int], phase: float) -> str:
    return f"({amplitude:.17g})*{basis}(2*pi*(({mode[0]})*x+({mode[1]})*y)+({phase:.17g}))"


if OUT.exists():
    raise FileExistsError("single materialization already completed")
hash_record = json.loads(HASH_RECORD.read_text())
if hash_record["status"] != "PASS" or sha(PROTOCOL) != hash_record["protocol_sha256"]:
    raise RuntimeError("protocol hash is absent or changed")
config = yaml.safe_load(CONFIG.read_text())
generator = load_module()
pool = [tuple(mode) for mode in config["mode_pool"]]
families = []
for family_spec in config["families"]:
    rng = np.random.Generator(np.random.PCG64(int(family_spec["root_seed"])))
    density_modes = [pool[index] for index in rng.choice(len(pool), size=3, replace=False)]
    ux_modes = [pool[index] for index in rng.choice(len(pool), size=4, replace=False)]
    uy_modes = [pool[index] for index in rng.choice(len(pool), size=4, replace=False)]
    density_amplitudes = generator.amplitudes(rng, 3, 0.0045)
    density_phases = rng.uniform(0.0, 2.0 * math.pi, size=3).tolist()
    ux_amplitudes = generator.amplitudes(rng, 4, 0.018)
    ux_phases = rng.uniform(0.0, 2.0 * math.pi, size=4).tolist()
    uy_amplitudes = generator.amplitudes(rng, 4, 0.018)
    uy_phases = rng.uniform(0.0, 2.0 * math.pi, size=4).tolist()
    density = {"modes": [list(x) for x in density_modes], "amplitudes": density_amplitudes, "phases": density_phases, "basis": "cos"}
    ux = {"modes": [list(x) for x in ux_modes], "amplitudes_over_cs": ux_amplitudes, "phases": ux_phases, "basis": "sin"}
    uy = {"modes": [list(x) for x in uy_modes], "amplitudes_over_cs": uy_amplitudes, "phases": uy_phases, "basis": "sin"}
    formula = {
        "family_id": family_spec["family_id"],
        "role": family_spec["role"],
        "root_seed": int(family_spec["root_seed"]),
        "lineage_id": f"{family_spec['family_id']}_PCG64_{family_spec['root_seed']}_FROZEN_V02",
        "density": density,
        "velocity_x": ux,
        "velocity_y": uy,
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
        "source_ancestry": {"generator": "Stage02J-T frozen blind generator", "draw_rule": "single deterministic draw after protocol hash; no redraw", "root_seed": int(family_spec["root_seed"]), "parent_family": None},
    }
    formula["formula_hash"] = content_hash({key: value for key, value in formula.items() if key not in ("formula_hash", "derivative_hash")})
    formula["derivative_hash"] = content_hash(formula["derivative_definition"] | {"density": density, "velocity_x": ux, "velocity_y": uy})
    families.append(formula)
output = {
    "materialization_version": "stage02mp-frozen-blind-generator-1.0.0",
    "protocol_sha256": hash_record["protocol_sha256"],
    "generator_source_hash": sha(SOURCE),
    "generator_config_hash": sha(CONFIG),
    "family_count": 2,
    "families": families,
    "materialized_after_protocol_hash": True,
    "single_materialization": True,
    "family_replacement_or_redraw_used": False,
    "result_dependent_regeneration_used": False,
}
OUT.write_text(json.dumps(output, indent=2, sort_keys=True, allow_nan=False) + "\n")
print(json.dumps({"family_count": 2, "protocol_sha256": hash_record["protocol_sha256"], "formula_hashes": [row["formula_hash"] for row in families]}, sort_keys=True))
