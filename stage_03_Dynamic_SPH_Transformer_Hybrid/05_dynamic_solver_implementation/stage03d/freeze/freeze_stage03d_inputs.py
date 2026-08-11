"""Freeze Stage 03D inputs without decoding any trajectory state array."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import torch


HERE = Path(__file__).resolve()
STAGE03D = HERE.parents[1]
STAGE03 = HERE.parents[3]
ROOT = HERE.parents[4]
STAGE03C = STAGE03 / "05_dynamic_solver_implementation/stage03c"
for candidate in (STAGE03C, ROOT / "01_solver"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from arm_d1.model import D1InstantaneousPairMLP
from arm_d2.model import D2CausalRecurrentPairPIO
from arm_d3.model import D3CausalTemporalTransformerPIO
from contracts.model_factory import parameter_hash


CONTRACT = STAGE03D / "contracts/dynamic_multistep_adfd_topology_contract_v0_1.yaml"
EXPECTED_CONTRACT_HASH = "sha256:a506af65ac124f8edf843e507f70c88566852fdfefb017eea127ddbe227fa692"
OUTPUT = STAGE03 / "10_manifests/stage03d_input_freeze_manifest.json"
LEDGER = STAGE03D / "freeze/historical_tree_hash_ledger.json"
SEEDS = (20300401, 20300402, 20300403)
PROBES = {
    "D1": (("encoder.linear_1.bias", (0,)), ("pair_head.output.bias", (0,))),
    "D2": (("recurrent.bias_ih", (0,)), ("pair_head.output.bias", (0,))),
    "D3": (
        ("encoder.linear_1.bias", (0,)),
        ("temporal.layers.0.self_attn.in_proj_bias", (0,)),
        ("pair_head.output.bias", (0,)),
    ),
}


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def historical_paths() -> list[Path]:
    roots = [ROOT / "stage_01_verification", ROOT / "stage_02_Particle_Interaction_Operator", ROOT / "01_solver"]
    paths: list[Path] = []
    for base in roots:
        paths.extend(path for path in base.rglob("*") if path.is_file())
    for path in STAGE03.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(STAGE03).as_posix()
        if relative.startswith("05_dynamic_solver_implementation/stage03d/"):
            continue
        if relative.startswith("09_reports/stage03d_") or relative.startswith("10_manifests/stage03d_"):
            continue
        paths.append(path)
    return sorted(set(paths), key=rel)


def model_for(arm: str, seed: int) -> torch.nn.Module:
    constructors = {
        "D1": D1InstantaneousPairMLP,
        "D2": D2CausalRecurrentPairPIO,
        "D3": D3CausalTemporalTransformerPIO,
    }
    torch.manual_seed(seed)
    model = constructors[arm]().to(device="cpu", dtype=torch.float64)
    model.eval()
    return model


def parameter_inventory() -> dict[str, Any]:
    result: dict[str, Any] = {}
    for arm in ("D1", "D2", "D3"):
        result[arm] = {}
        for seed in SEEDS:
            model = model_for(arm, seed)
            named = dict(model.named_parameters())
            resolved = []
            for path, index in PROBES[arm]:
                tensor = named.get(path)
                valid = tensor is not None
                if valid:
                    try:
                        value = float(tensor[index].detach())
                    except IndexError:
                        valid = False
                        value = None
                else:
                    value = None
                resolved.append({"module_path": path, "tensor_index": list(index), "resolved": valid, "frozen_value": value})
            result[arm][str(seed)] = {
                "parameter_count": sum(parameter.numel() for parameter in model.parameters()),
                "parameter_hash": parameter_hash(model),
                "probe_paths": resolved,
            }
    return result


def selected_evidence() -> list[dict[str, Any]]:
    selected = [
        STAGE03 / "09_reports/stage03a_final_report.md",
        STAGE03 / "06_vv_contract/multistep_ad_fd_contract.md",
        STAGE03 / "03_time_integration/topology_differentiability_boundary.md",
        STAGE03 / "09_reports/stage03b_final_report.md",
        STAGE03 / "04_reference_and_trajectory/stage03b/topology_events/dr1b_topology_event_registry.json",
        STAGE03 / "09_reports/stage03c_final_report.md",
        STAGE03C / "contracts/dynamic_solver_implementation_contract_v0_1.yaml",
        STAGE03C / "results/zero_correction_results.json",
        STAGE03C / "results/checkpoint_resume_results.json",
        STAGE03C / "results/differentiability_smoke_results.json",
        STAGE03C / "results/resource_audit_results.json",
        STAGE03 / "10_manifests/stage03b_trajectory_manifest.json",
        STAGE03 / "10_manifests/stage03c_final_manifest.json",
    ]
    source_subdirs = (
        "baseline_d0",
        "graph_rebuild",
        "source_interface",
        "rk2_core",
        "temporal_history",
        "tokenization",
        "pair_force_head",
        "arm_d1",
        "arm_d2",
        "arm_d3",
    )
    for name in source_subdirs:
        selected.extend(path for path in (STAGE03C / name).rglob("*.py"))
    records = []
    for path in sorted(set(selected), key=rel):
        records.append({"path": rel(path), "byte_count": path.stat().st_size, "sha256": sha(path)})
    return records


def main() -> None:
    if sha(CONTRACT) != EXPECTED_CONTRACT_HASH:
        raise RuntimeError("Stage 03D contract hash is not the frozen value")
    stage03c_final = json.loads((STAGE03 / "10_manifests/stage03c_final_manifest.json").read_text(encoding="utf-8"))
    if stage03c_final.get("final_status") != "DYNAMIC_RK2_HYBRID_IMPLEMENTATION_VERIFIED":
        raise RuntimeError("Stage 03C authorization missing")

    paths = historical_paths()
    records = [{"path": rel(path), "byte_count": path.stat().st_size, "sha256": sha(path)} for path in paths]
    tree_digest = hashlib.sha256()
    for item in records:
        tree_digest.update(item["path"].encode("utf-8"))
        tree_digest.update(b"\0")
        tree_digest.update(item["sha256"].encode("ascii"))
        tree_digest.update(b"\n")
    ledger = {
        "schema_version": "sph-pio-poc.stage03d.historical-tree-ledger.v1",
        "freeze_method": "byte_hash_only_no_trajectory_array_decode",
        "file_count": len(records),
        "aggregate_sha256": "sha256:" + tree_digest.hexdigest(),
        "files": records,
    }
    write_json(LEDGER, ledger)

    trajectories = [item for item in records if item["path"].endswith(".npz") and "/stage03b/trajectory_records/" in item["path"]]
    sidecars = [item for item in records if item["path"].endswith(".json") and "/stage03b/trajectory_records/" in item["path"]]
    parameters = parameter_inventory()
    all_paths_resolved = all(
        probe["resolved"]
        for arm in parameters.values()
        for seed in arm.values()
        for probe in seed["probe_paths"]
    )
    manifest = {
        "schema_version": "sph-pio-poc.stage03d.input-freeze.v1",
        "stage": "Stage 03D",
        "freeze_date": "2026-08-05",
        "authorization": "Stage 03C:DYNAMIC_RK2_HYBRID_IMPLEMENTATION_VERIFIED",
        "freeze_method": "contract_frozen_then_byte_hash_only_no_trajectory_array_decode",
        "contract": {"path": rel(CONTRACT), "sha256": sha(CONTRACT), "immutable": True},
        "historical_tree_ledger": {"path": rel(LEDGER), "sha256": sha(LEDGER), "file_count": len(records), "aggregate_sha256": ledger["aggregate_sha256"]},
        "selected_evidence": selected_evidence(),
        "trajectory_array_count": len(trajectories),
        "trajectory_sidecar_count": len(sidecars),
        "trajectory_arrays_decoded_during_freeze": 0,
        "parameter_inventory": parameters,
        "all_parameter_paths_uniquely_resolved": all_paths_resolved,
        "historical_verdicts": {
            "Stage_01": "V2_QUALIFICATION_FAIL",
            "Stage_01H": "FINITE_RESOLUTION_DOMINANT",
            "viscosity_operator_form": "NOT_CONFIRMED",
            "Stage_02_static_learning_route": "TERMINATED",
            "Stage_03B_required_topology": "NO_EVENT_FIXED_TOPOLOGY",
            "Stage_03C": "fixed_topology_implementation_verified",
        },
        "pass": len(trajectories) == 18 and len(sidecars) == 18 and all_paths_resolved,
    }
    write_json(OUTPUT, manifest)


if __name__ == "__main__":
    main()
