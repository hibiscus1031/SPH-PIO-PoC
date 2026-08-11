"""Freeze Stage 03C inputs by bytes only; trajectory arrays are never decoded here."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
STAGE = ROOT / "stage_03_Dynamic_SPH_Transformer_Hybrid"
OUT = STAGE / "10_manifests" / "stage03c_input_freeze_manifest.json"


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def entry(relative: str, role: str) -> dict[str, object]:
    path = ROOT / relative
    return {
        "path": relative,
        "role": role,
        "byte_count": path.stat().st_size,
        "sha256": sha(path),
    }


def main() -> None:
    explicit = [
        ("stage_03_Dynamic_SPH_Transformer_Hybrid/09_reports/stage03a_final_report.md", "stage03a_authorization"),
        ("stage_03_Dynamic_SPH_Transformer_Hybrid/01_governing_contract/hybrid_equations.md", "governing_equations"),
        ("stage_03_Dynamic_SPH_Transformer_Hybrid/02_temporal_architecture/causal_token_contract.md", "temporal_contract"),
        ("stage_03_Dynamic_SPH_Transformer_Hybrid/02_temporal_architecture/hidden_state_contract.md", "temporal_contract"),
        ("stage_03_Dynamic_SPH_Transformer_Hybrid/02_temporal_architecture/reciprocal_pair_head_contract.md", "temporal_contract"),
        ("stage_03_Dynamic_SPH_Transformer_Hybrid/02_temporal_architecture/temporal_transformer_contract.md", "temporal_contract"),
        ("stage_03_Dynamic_SPH_Transformer_Hybrid/02_temporal_architecture/zero_fallback_contract.md", "zero_contract"),
        ("stage_03_Dynamic_SPH_Transformer_Hybrid/03_time_integration/rk2_stage_semantics.md", "rk2_contract"),
        ("stage_03_Dynamic_SPH_Transformer_Hybrid/03_time_integration/graph_rebuild_contract.md", "graph_contract"),
        ("stage_03_Dynamic_SPH_Transformer_Hybrid/03_time_integration/history_commit_contract.md", "history_contract"),
        ("stage_03_Dynamic_SPH_Transformer_Hybrid/03_time_integration/topology_differentiability_boundary.md", "topology_boundary"),
        ("stage_03_Dynamic_SPH_Transformer_Hybrid/09_reports/stage03b_final_report.md", "stage03b_authorization"),
        ("stage_03_Dynamic_SPH_Transformer_Hybrid/09_reports/stage03b_reference_contract.md", "reference_contract"),
        ("stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03b_final_manifest.json", "stage03b_final_manifest"),
        ("stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03b_trajectory_manifest.json", "trajectory_manifest"),
        ("stage_03_Dynamic_SPH_Transformer_Hybrid/04_reference_and_trajectory/stage03b/analytic_core/reference_core.py", "source_definition"),
        ("stage_03_Dynamic_SPH_Transformer_Hybrid/04_reference_and_trajectory/stage03b/dr2_semidiscrete_time_reference/semidiscrete_rhs.py", "dr2_reference_implementation"),
        ("stage_03_Dynamic_SPH_Transformer_Hybrid/04_reference_and_trajectory/stage03b/topology_events/dr1b_topology_event_registry.json", "topology_registry"),
        ("stage_03_Dynamic_SPH_Transformer_Hybrid/04_reference_and_trajectory/stage03b/uncertainty/trajectory_reference_uncertainty.json", "uncertainty"),
        ("01_solver/structure_preserving/neighborhood.py", "baseline_graph"),
        ("01_solver/structure_preserving/kernels.py", "baseline_kernel_and_continuity"),
        ("01_solver/structure_preserving/conservative_pressure.py", "baseline_pressure"),
        ("01_solver/structure_preserving/conservative_viscosity.py", "baseline_viscosity"),
        ("01_solver/dynamic_solver/equation_of_state.py", "baseline_eos"),
    ]
    records = sorted(
        (STAGE / "04_reference_and_trajectory/stage03b/trajectory_records").glob("*")
    )
    inputs = [entry(path, role) for path, role in explicit]
    for path in records:
        role = "canonical_trajectory_array" if path.suffix == ".npz" else "canonical_trajectory_sidecar"
        inputs.append(entry(str(path.relative_to(ROOT)), role))
    manifest = {
        "schema_version": "sph-pio-poc.stage03c.input-freeze.v1",
        "stage": "Stage 03C",
        "freeze_date": "2026-08-05",
        "authorization": "Stage 03B:DYNAMIC_REFERENCE_TRAJECTORY_QUALIFICATION_COMPLETE",
        "freeze_method": "byte_hash_only_no_trajectory_array_decode",
        "implementation_contract": {
            "path": str((STAGE / "05_dynamic_solver_implementation/stage03c/contracts/dynamic_solver_implementation_contract_v0_1.yaml").relative_to(ROOT)),
            "sha256": sha(STAGE / "05_dynamic_solver_implementation/stage03c/contracts/dynamic_solver_implementation_contract_v0_1.yaml"),
        },
        "historical_verdicts": {
            "Stage_01": "V2_QUALIFICATION_FAIL",
            "Stage_01H": "FINITE_RESOLUTION_DOMINANT",
            "viscosity_operator_form": "NOT_CONFIRMED",
            "Stage_02_static_learning_route": "TERMINATED",
        },
        "inputs": inputs,
        "input_count": len(inputs),
        "trajectory_array_count": sum(i["role"] == "canonical_trajectory_array" for i in inputs),
        "trajectory_sidecar_count": sum(i["role"] == "canonical_trajectory_sidecar" for i in inputs),
        "historical_files_mutable": False,
    }
    OUT.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
