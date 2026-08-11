#!/usr/bin/env python3
"""Freeze Stage 01/02 and Stage 03A-D-R before Stage 03D-S synthesis."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
STAGE = REPO / "stage_03_Dynamic_SPH_Transformer_Hybrid"
OUT = STAGE / "10_manifests/stage03ds_input_freeze_manifest.json"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return "sha256:" + h.hexdigest()


status_sources = {
    "Stage 01": {
        "status": "V2_QUALIFICATION_FAIL",
        "path": "07_reports/stage01h_final_report.md",
    },
    "Stage 01H": {
        "status": "FINITE_RESOLUTION_DOMINANT",
        "path": "07_reports/stage01h_final_report.md",
    },
    "Stage 02 route": {
        "status": "STAGE02_ROUTE_CLOSED_PUBLICATION_BOUNDARY_COMPLETE",
        "path": "stage_02_Particle_Interaction_Operator/07_reports/stage02ms_final_report.md",
    },
    "Stage 03A": {
        "status": "DYNAMIC_HYBRID_SOLVER_SPECIFICATION_COMPLETE",
        "path": "stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03a_final_manifest.json",
    },
    "Stage 03B": {
        "status": "DYNAMIC_REFERENCE_TRAJECTORY_QUALIFICATION_COMPLETE",
        "path": "stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03b_final_manifest.json",
    },
    "Stage 03C": {
        "status": "DYNAMIC_RK2_HYBRID_IMPLEMENTATION_VERIFIED",
        "path": "stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03c_final_manifest.json",
    },
    "Stage 03D": {
        "status": "DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED",
        "path": "stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03d_final_manifest.json",
    },
    "Stage 03D-R": {
        "status": "DYNAMIC_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED",
        "path": "stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03dr_final_manifest.json",
    },
}


def source_contains_status(row: dict[str, str]) -> bool:
    path = REPO / row["path"]
    if not path.is_file():
        return False
    return row["status"] in path.read_text(errors="replace")


historical_paths: set[Path] = set()
for base in (
    REPO / "stage_01_verification",
    REPO / "stage_02_Particle_Interaction_Operator",
    STAGE,
):
    for path in base.rglob("*"):
        if not path.is_file():
            continue
        if base == STAGE:
            rel = path.relative_to(STAGE)
            if rel.parts[0] == "08_route_closure":
                continue
            if rel.parts[0] == "documents" and path.name == "Stage_03_Research_Record.docx":
                continue
            if rel.parts[0] == "09_reports" and path.name.startswith("stage03ds_"):
                continue
            if rel.parts[0] == "10_manifests" and path.name.startswith("stage03ds_"):
                continue
        historical_paths.add(path)

for path in (REPO / "07_reports").glob("stage01*"):
    if path.is_file():
        historical_paths.add(path)

rows = [
    {
        "path": str(path.relative_to(REPO)),
        "byte_count": path.stat().st_size,
        "sha256": digest(path),
        "workflow_mode": "read_only_historical_input",
    }
    for path in sorted(historical_paths)
]

status_records = {}
for name, row in status_sources.items():
    path = REPO / row["path"]
    status_records[name] = {
        **row,
        "sha256": digest(path) if path.is_file() else None,
        "status_present": source_contains_status(row),
    }

checks = {
    "all_status_sources_present": all((REPO / row["path"]).is_file() for row in status_sources.values()),
    "all_frozen_statuses_verified": all(row["status_present"] for row in status_records.values()),
    "stage03d_failure_preserved": status_records["Stage 03D"]["status_present"],
    "stage03dr_non_override_status_preserved": status_records["Stage 03D-R"]["status_present"],
    "historical_files_treated_as_read_only": True,
    "historical_write_operations": 0,
}

manifest = {
    "schema_version": "sph-pio-poc.stage03ds.input-freeze.v1",
    "stage": "Stage 03D-S — Dynamic Route Closure, Evidence Synthesis and Publication Boundary",
    "freeze_timing": "before_stage03ds_evidence_synthesis",
    "historical_file_count": len(rows),
    "historical_files": rows,
    "status_sources": status_records,
    "preserved_states": {
        "stage03c": "DYNAMIC_RK2_HYBRID_IMPLEMENTATION_VERIFIED",
        "stage03d": "DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED",
        "stage03dr": "DYNAMIC_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED",
        "topology_component": "TOPOLOGY_EVENT_COMPONENT_QUALIFIED",
        "stage03e_authorization": False,
    },
    "scope_contract": {
        "noncomputational_closure": True,
        "new_adfd_contracts": 0,
        "new_epsilons": 0,
        "new_probes": 0,
        "new_backends": 0,
        "new_architectures": 0,
        "new_datasets": 0,
        "new_training_protocols": 0,
        "new_optimizer_steps": 0,
        "new_training_runs": 0,
        "new_rollouts": 0,
        "new_performance_evaluations": 0,
    },
    "checks": checks,
}
manifest["status"] = "PASS" if all(
    (isinstance(v, bool) and v) or (isinstance(v, int) and not isinstance(v, bool) and v == 0)
    for v in checks.values()
) else "FAIL"
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
print(json.dumps({"status": manifest["status"], "historical_file_count": len(rows), "status_sources": len(status_records)}, ensure_ascii=False))
