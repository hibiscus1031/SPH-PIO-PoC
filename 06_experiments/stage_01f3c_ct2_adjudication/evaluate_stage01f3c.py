"""Unique Stage 01F3C status adjudication."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / "06_experiments/stage_01f3c_ct2_adjudication"
CONFIG = STAGE / "configs/preregistered_stage01f3c.yml"
RESULTS = STAGE / "results"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name: str) -> dict[str, Any]:
    return json.loads((RESULTS / name).read_text())


def temporal_pass(payload: dict[str, Any]) -> bool:
    keys = (
        "temporal_endpoint_monotone",
        "temporal_integrated_monotone",
        "temporal_endpoint_order",
        "temporal_integrated_order",
    )
    return all(
        solution["checks"][key]
        for solution in payload["solutions"].values()
        for key in keys
    )


def cancellation_pass(payload: dict[str, Any]) -> bool:
    keys = (
        "reference_status_pass",
        "vector_closure_absolute",
        "vector_closure_relative",
        "temporal_endpoint_monotone",
        "temporal_integrated_monotone",
        "temporal_endpoint_order",
        "temporal_integrated_order",
        "coarse_negative_cross_endpoint",
        "coarse_negative_cross_integrated",
        "coarse_cross_explains_below_platform",
        "approaches_platform_from_below",
        "finest_platform_distance",
    )
    return all(
        solution["checks"][key]
        for solution in payload["solutions"].values()
        for key in keys
    )


def classify_status(
    evidence_complete: bool,
    n32_temporal: bool,
    heldout_temporal: bool,
    cancellation_confirmed: bool,
) -> str:
    if not evidence_complete:
        return "CT2_EVIDENCE_INCOMPLETE"
    if n32_temporal != heldout_temporal:
        return "CT2_MIXED_OR_UNRESOLVED"
    if not n32_temporal and not heldout_temporal:
        return "CT2_TRUE_TEMPORAL_DEGRADATION_CONFIRMED"
    if cancellation_confirmed:
        return "CT2_SPATIAL_TEMPORAL_CANCELLATION_CONFIRMED"
    return "CT2_MIXED_OR_UNRESOLVED"


def main() -> int:
    config = yaml.safe_load(CONFIG.read_text())
    prerequisite = load("prerequisite_checks.json")
    n32 = load("n32_error_decomposition.json")
    heldout = load("heldout_error_decomposition.json")
    audit = load("resource_determinism_audit.json")
    with (ROOT / config["frozen_stage01f3b"]["manifest"]).open() as stream:
        manifest = list(csv.DictReader(stream))
    historical_identity = all(
        sha(ROOT / row["path"]) == row["sha256"] for row in manifest
    )
    reference_ids = (
        "f3c_ref_n32_a",
        "f3c_ref_n32_b",
        "f3c_ref_heldout_a",
        "f3c_ref_heldout_b",
    )
    reference_provenance = True
    for run_id in reference_ids:
        summary = json.loads((STAGE / "run_summaries" / f"{run_id}.json").read_text())
        reference_provenance = reference_provenance and (
            sha(ROOT / summary["reference_path"]) == summary["reference_sha256"]
            and summary["config_sha256"] == sha(CONFIG)
            and bool(summary["code_sha256"])
            and bool(summary["parameter_sha256"])
        )
    vector_provenance = all(
        sha(ROOT / solution["vector_evidence_path"])
        == solution["vector_evidence_sha256"]
        for payload in (n32, heldout)
        for solution in payload["solutions"].values()
    )
    old_self_identity = n32["stage01f3b_self_difference_identity"]["status"] == "PASS"
    n32_temporal = temporal_pass(n32)
    heldout_temporal = temporal_pass(heldout)
    checks = {
        "stage01f3b_frozen_identity": prerequisite["status"] == "PASS"
        and historical_identity,
        "reference_provenance_complete": reference_provenance,
        "vector_provenance_complete": vector_provenance,
        "n32_references_pass": all(
            solution["checks"]["reference_status_pass"]
            for solution in n32["solutions"].values()
        ),
        "heldout_references_pass": all(
            solution["checks"]["reference_status_pass"]
            for solution in heldout["solutions"].values()
        ),
        "n32_vector_closure": all(
            solution["checks"]["vector_closure_absolute"]
            and solution["checks"]["vector_closure_relative"]
            for solution in n32["solutions"].values()
        ),
        "heldout_vector_closure": all(
            solution["checks"]["vector_closure_absolute"]
            and solution["checks"]["vector_closure_relative"]
            for solution in heldout["solutions"].values()
        ),
        "n32_temporal_second_order": n32_temporal,
        "heldout_temporal_second_order": heldout_temporal,
        "stage01f3b_self_difference_identity": old_self_identity,
        "n32_cancellation_mechanism": cancellation_pass(n32),
        "heldout_cancellation_mechanism": cancellation_pass(heldout),
        "source_conservation_topology_resource_determinism": audit["status"] == "PASS",
        "historical_status_unchanged": json.loads(
            (
                ROOT
                / config["frozen_stage01f3b"]["evaluator"]
            ).read_text()
        )["status"]
        == "MMS_CONVERGENCE_VERIFICATION_FAIL",
        "no_downstream_or_training_started": not any(
            config["scope"][key]
            for key in (
                "stage01f3d_started",
                "stage01g_started",
                "v3_started",
                "stage02_started",
                "training_started",
                "labels_generated",
            )
        ),
    }
    evidence_keys = (
        "stage01f3b_frozen_identity",
        "reference_provenance_complete",
        "vector_provenance_complete",
        "n32_references_pass",
        "heldout_references_pass",
        "n32_vector_closure",
        "heldout_vector_closure",
        "stage01f3b_self_difference_identity",
        "historical_status_unchanged",
        "no_downstream_or_training_started",
    )
    evidence_complete = all(checks[key] for key in evidence_keys)
    cancellation_confirmed = (
        checks["n32_cancellation_mechanism"]
        and checks["heldout_cancellation_mechanism"]
        and checks["source_conservation_topology_resource_determinism"]
        and checks["stage01f3b_self_difference_identity"]
    )
    status = classify_status(
        evidence_complete, n32_temporal, heldout_temporal, cancellation_confirmed
    )
    if status not in config["allowed_statuses"]:
        raise AssertionError(f"unregistered status {status}")
    payload = {
        "schema_version": "sph-pio-poc.stage01f3c.evaluation.v1",
        "status": status,
        "checks": checks,
        "evidence_complete": evidence_complete,
        "n32_temporal_second_order": n32_temporal,
        "heldout_temporal_second_order": heldout_temporal,
        "cancellation_confirmed": cancellation_confirmed,
        "stage01f3d_application_eligible": status
        == "CT2_SPATIAL_TEMPORAL_CANCELLATION_CONFIRMED",
        "stage01g_application_permitted": False,
        "historical_stage01f3b_status": "MMS_CONVERGENCE_VERIFICATION_FAIL",
        "historical_stage01f3b_reclassified": False,
        "scope": config["scope"],
        "config_sha256": sha(CONFIG),
    }
    output = RESULTS / "stage01f3c_evaluation.json"
    if output.exists():
        raise RuntimeError(f"refusing to overwrite {output.relative_to(ROOT)}")
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": status}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
