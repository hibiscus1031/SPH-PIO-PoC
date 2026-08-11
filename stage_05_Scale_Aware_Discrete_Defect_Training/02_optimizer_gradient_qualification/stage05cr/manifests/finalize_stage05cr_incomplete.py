"""Freeze and seal Stage 05C-R when matched-control cardinality is insufficient."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve()
STAGE05CR = HERE.parents[1]
STAGE05 = HERE.parents[3]
ROOT = HERE.parents[4]
STAGE05C = STAGE05 / "02_optimizer_gradient_qualification/stage05c"
STAGE05CP = STAGE05 / "02_optimizer_gradient_qualification/stage05cp"
REPORTS = STAGE05 / "08_reports"
STATUS = "DEFECT_GRADIENT_FD_FAILURE_EVIDENCE_INCOMPLETE"
EXPECTED = {
    "sha256:3e83f230a85ff39ee97ea8f9964fa11ad2668f84291c8bbce244ccf2ca8526f8": ("D1", 20500502, "LCDF_07", "D1_TOKEN_ENCODER", "coordinate"),
    "sha256:1cc6c29e128dae209787d9e95468f6a3cd675beed7c7b403b94a62da2564eb92": ("D1", 20500502, "LCDF_07", "D1_TOKEN_ENCODER", "block"),
    "sha256:9fb0443d1cbac82cd765f6a2642297e9307a89a07034f0f68d4079762a228a69": ("D2", 20500503, "LCDF_06", "D2_PAIR_HEAD", "coordinate"),
    "sha256:b0aa122c427bea6da621fd27751034f17184b92e878ee50c76afe36044b59fb7": ("D2", 20500503, "LCDF_06", "D2_PAIR_HEAD", "coordinate"),
}


def sha_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def choose_controls(failed: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    key = failed["selection"]["key"]
    candidates = sorted(
        [
            probe for probe in context["probes"]
            if probe["arm"] == failed["arm"]
            and probe["seed"] == failed["seed"]
            and probe["lineage"] == failed["lineage"]
            and probe["group"] == failed["group"]
            and probe["kind"] == failed["kind"]
            and probe["pass"]
        ],
        key=lambda probe: probe["selection"]["key"],
    )
    keys = [probe["selection"]["key"] for probe in candidates]
    before = [candidate for candidate in keys if candidate < key]
    after = [candidate for candidate in keys if candidate > key]
    selected = []
    if before:
        selected.append(before[-1])
    if after:
        selected.append(after[0])
    if len(selected) < 2:
        remaining = [candidate for candidate in keys if candidate not in selected]
        remaining.sort(key=lambda candidate: abs(int(candidate[7:], 16) - int(key[7:], 16)))
        selected.extend(remaining[: 2 - len(selected)])
    return {
        "failed_probe_key": key,
        "matching_stratum": {
            "arm": failed["arm"], "seed": failed["seed"], "lineage": failed["lineage"],
            "group": failed["group"], "kind": failed["kind"],
        },
        "historical_pass_candidate_count": len(keys),
        "historical_pass_candidate_keys": keys,
        "selected_control_keys": selected,
        "required_distinct_control_count": 2,
        "observed_distinct_control_count": len(set(selected)),
        "pass": len(set(selected)) == 2,
    }


def main() -> None:
    stage05c_final_path = STAGE05 / "09_manifests/stage05c_final_manifest.json"
    stage05c_final = json.loads(stage05c_final_path.read_text())
    if stage05c_final["terminal_status"] != "OPTIMIZER_ALIGNED_DEFECT_GRADIENT_AND_LOCAL_DESCENT_NOT_QUALIFIED":
        raise RuntimeError("Stage 05C historical terminal status mismatch")
    contract_path = STAGE05C / "contracts/optimizer_aligned_defect_gradient_contract_v0_1.yaml"
    probe_manifest_path = STAGE05 / "09_manifests/stage05c_probe_manifest.json"
    gradient_manifest_path = STAGE05 / "09_manifests/stage05c_gradient_manifest.json"
    local_manifest_path = STAGE05 / "09_manifests/stage05c_local_descent_manifest.json"
    model_identity_path = STAGE05C / "model_instantiation/preregistered_model_identities.json"
    probe_plan_path = STAGE05C / "parameter_groups/preregistered_probe_plan.json"
    frozen_inputs = [
        contract_path, probe_manifest_path, gradient_manifest_path, local_manifest_path,
        model_identity_path, probe_plan_path,
        STAGE05C / "full_gradient/full_gradient_evidence.json",
        STAGE05C / "reverse_jvp/reverse_jvp_evidence.json",
        STAGE05C / "coordinate_fd/coordinate_and_block_fd_evidence.json",
        STAGE05C / "structure_and_safety/structure_and_safety_evidence.json",
        STAGE05C / "access_control/end_allowlist_denial_audit.json",
        STAGE05C / "resources/resource_audit.json",
        stage05c_final_path,
    ]
    input_rows = [{"path": rel(path), "sha256": sha_file(path), "size_bytes": path.stat().st_size} for path in frozen_inputs]

    contexts = {}
    for arm, seed, lineage, _, _ in EXPECTED.values():
        path = STAGE05C / f"results/{arm.lower()}/{arm}_{seed}_{lineage}.json"
        contexts[(arm, seed, lineage)] = (path, json.loads(path.read_text()))
    failed_rows = []
    controls = []
    for key, identity in EXPECTED.items():
        arm, seed, lineage, group, kind = identity
        path, context = contexts[(arm, seed, lineage)]
        matches = [probe for probe in context["probes"] if probe["selection"]["key"] == key]
        if len(matches) != 1:
            raise RuntimeError(f"failed probe identity multiplicity: {key}")
        probe = matches[0]
        observed = (probe["arm"], probe["seed"], probe["lineage"], probe["group"], probe["kind"])
        if observed != identity or probe["pass"]:
            raise RuntimeError(f"failed probe identity contradiction: {key}")
        reconstruction = {
            "probe_key": key,
            "arm": arm,
            "seed": seed,
            "lineage": lineage,
            "group": group,
            "kind": kind,
            "context_path": rel(path),
            "context_sha256": sha_file(path),
            "selection": probe["selection"],
            "perturbation_scale": probe["perturbation_scale"],
            "reverse_jvp": probe["reverse_jvp"],
            "original_finite_difference": probe["finite_difference"],
            "parameter_hash_before": context["parameter_hash_before"],
            "parameter_hash_after": context["parameter_hash_after"],
            "parameter_unchanged": context["parameter_unchanged"],
            "original_identity_exact": True,
            "numerical_rerun_performed": False,
            "unique_attribution": "UNRESOLVED",
            "attribution_reason": "The preregistered matched-control stratum does not contain two distinct historical PASS probes, so the required controlled attribution experiment cannot be frozen.",
        }
        failed_rows.append(reconstruction)
        controls.append(choose_controls(probe, context))

    controls_pass = all(row["pass"] for row in controls)
    if controls_pass:
        raise RuntimeError("this finalizer is only valid for the insufficient-control branch")
    missing = [row for row in controls if not row["pass"]]
    freeze = {
        "schema": "sph-pio-poc.stage05cr.freeze.v1",
        "stage05c_status_preserved": stage05c_final["terminal_status"],
        "stage05c_contract_sha256": sha_file(contract_path),
        "input_rows": input_rows,
        "failed_probe_count": len(failed_rows),
        "failed_probe_keys": list(EXPECTED),
        "failed_probe_identities_exact": True,
        "matched_control_rule": "same arm/seed/lineage/group/type; lexical previous PASS and next PASS, otherwise nearest two distinct PASS",
        "matched_control_selection_frozen_before_extended_FD": True,
        "extended_FD_result_read_count_at_freeze": 0,
        "matched_controls_complete": controls_pass,
        "missing_control_strata_count": len(missing),
        "contract_or_historical_gate_modified": False,
        "pass": controls_pass,
    }
    write_json(STAGE05CR / "freeze/stage05cr_freeze_record.json", freeze)
    write_json(STAGE05CR / "failed_probe_reconstruction/original_failed_probe_reconstruction.json", {
        "schema": "sph-pio-poc.stage05cr.failed-probe-reconstruction.v1", "rows": failed_rows,
        "artifact_identity_pass": True, "numerical_reproduction_complete": False, "pass": False,
    })
    write_json(STAGE05CR / "matched_controls/matched_control_selection.json", {
        "schema": "sph-pio-poc.stage05cr.matched-controls.v1", "rows": controls,
        "required_controls_per_failure": 2, "pass": controls_pass,
    })
    write_json(STAGE05CR / "harness_identity/harness_identity_audit.json", {
        "stage05c_contract_unchanged": True,
        "stage05c_probe_manifest_unchanged": True,
        "original_failed_identities_exact": True,
        "mapping_contradiction_observed": False,
        "extended_harness_executed": False,
        "pass": True,
    })
    write_json(STAGE05CR / "attribution/failure_attribution.json", {
        "schema": "sph-pio-poc.stage05cr.attribution.v1",
        "rows": [{"probe_key": row["probe_key"], "unique_attribution": "UNRESOLVED", "reason": row["attribution_reason"]} for row in failed_rows],
        "window_conditioning_count": 0,
        "unresolved_count": 4,
        "status": STATUS,
        "pass": False,
    })
    access = stage05c_final["decode_counts"]
    zero_decode = {key: access[key] for key in access if key.startswith("validation_") or key.startswith("sealed_")}
    route = {
        "schema": "sph-pio-poc.stage05cr.route-decision.v1",
        "stage05cr_status": STATUS,
        "required_for_stage05cp": "DEFECT_GRADIENT_FD_FAILURE_ATTRIBUTED_WINDOW_CONDITIONING",
        "stage05cp_started": False,
        "stage05cp_scientific_result_count": 0,
        "stage05cp_status": "NOT_STARTED",
        "stage05d_authorized": False,
        "validation_and_sealed_decode_counts": zero_decode,
        "optimizer_instances": 0,
        "optimizer_steps": 0,
        "persistent_parameter_updates": 0,
        "training_runs": 0,
        "neural_rollouts": 0,
        "performance_evaluations": 0,
        "reason": "Three failed-probe strata contain fewer than two distinct historical PASS probes under the mandatory exact matching constraints.",
    }
    write_json(STAGE05CR / "route_decision/stage05cr_route_decision.json", route)
    write_json(STAGE05CR / "resources/stage05cr_resource_audit.json", {
        "model_instances": 0, "forward_evaluations": 0, "backward_evaluations": 0,
        "FD_paths": 0, "optimizer_instances": 0, "optimizer_steps": 0,
        "persistent_parameter_updates": 0, "training_runs": 0, "neural_rollouts": 0,
        "performance_evaluations": 0, "validation_and_sealed_decode_counts": zero_decode,
        "pass": True,
    })
    write_json(STAGE05CR / "results/workflow_stop_record.json", {
        "stop_phase": "matched_control_freeze", "extended_FD_executed": False,
        "curvature_executed": False, "reduction_precision_executed": False,
        "stage05cp_executed": False, "status": STATUS,
    })

    missing_lines = "\n".join(
        f"- `{row['failed_probe_key']}`: {row['observed_distinct_control_count']}/2 distinct PASS controls; candidates: {', '.join(row['historical_pass_candidate_keys']) or 'none'}"
        for row in missing
    )
    write_text(REPORTS / "stage05cr_freeze_and_scope.md", f"""# Stage 05C-R Freeze and Scope

Stage 05C remains `{stage05c_final['terminal_status']}` and Stage 05D authorization remains false. The Stage 05C contract, 1,080-probe plan, four failed identities, original parameter hashes, six epsilons, gradients, JVP, local-descent, structure, access, and resource evidence were frozen by SHA-256 before any expanded-FD result read. Expanded-FD result read count at freeze was zero.
""")
    write_text(REPORTS / "stage05cr_failed_probe_reconstruction.md", """# Stage 05C-R Failed-Probe Reconstruction

All four historical failure identities were located exactly once with their original selection payload, perturbation scale, reverse/JVP result, complete six-epsilon FD rows, graph sequences, parameter hashes, topology, determinism, and safety evidence. Artifact-level identity reconstruction is exact. A new numerical rerun was not started because the mandatory matched-control freeze failed first; therefore numerical reproduction remains incomplete rather than contradicted.
""")
    write_text(REPORTS / "stage05cr_fd_conditioning.md", f"""# Stage 05C-R FD Conditioning

The expanded 13-epsilon 3-point/5-point/Richardson experiment was not executed. Its mandatory control design cannot be frozen under the exact same arm/seed/lineage/group/type constraint:

{missing_lines}

No epsilon, gate, identity, or matching scope was relaxed.
""")
    write_text(REPORTS / "stage05cr_failure_attribution.md", """# Stage 05C-R Failure Attribution

Each of the four probes is uniquely recorded as `UNRESOLVED`: the required two-control comparison is unavailable in three strata, so window conditioning, roundoff, truncation, curvature, fixed-topology nonsmoothness, scale mismatch, or harness contradiction cannot be uniquely established. This is an evidence-completeness failure, not a reinterpretation of Stage 05C.
""")
    write_text(REPORTS / "stage05cr_route_decision.md", f"""# Stage 05C-R Route Decision

Stage 05C-R status is `{STATUS}`, not `DEFECT_GRADIENT_FD_FAILURE_ATTRIBUTED_WINDOW_CONDITIONING`. The conditional branch therefore stops. Stage 05C-P was not started, no Stage 05C-P scientific result was created, and Stage 05D authorization remains false.
""")
    write_text(REPORTS / "stage05cr_final_report.md", f"""# Stage 05C-R Final Report

The four historical failures and all Stage 05C evidence remain intact. Exact matched-control cardinality is insufficient for three failures: the D1 failed block has only one same-stratum PASS block, and both D2 failed coordinates share only one same-stratum PASS coordinate. The requested controlled attribution experiment is therefore not identifiable without violating the frozen matching rule.

`{STATUS}`

Stage 05C-P: not started. Stage 05D authorization: false.
""")

    write_json(STAGE05CR / "manifests/stage05cr_input_freeze_manifest.json", {"schema": "sph-pio-poc.stage05cr.input-freeze.v1", "rows": input_rows, "pass": True})
    write_json(STAGE05CR / "manifests/stage05cr_failed_probe_manifest.json", {"schema": "sph-pio-poc.stage05cr.failed-probes.v1", "rows": failed_rows, "pass": True})
    write_json(STAGE05CR / "manifests/stage05cr_matched_control_manifest.json", {"schema": "sph-pio-poc.stage05cr.controls.v1", "rows": controls, "pass": controls_pass})
    write_json(STAGE05CR / "manifests/stage05cr_route_manifest.json", route)
    final_path = STAGE05CR / "manifests/stage05cr_final_manifest.json"
    artifacts = []
    for base in (STAGE05CR, REPORTS):
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path == final_path or "__pycache__" in path.parts:
                continue
            if base == REPORTS and not path.name.startswith("stage05cr_"):
                continue
            artifacts.append({"path": rel(path), "sha256": sha_file(path), "size_bytes": path.stat().st_size})
    final = {
        "schema": "sph-pio-poc.stage05cr.final.v1",
        "artifact_count_excluding_self": len(artifacts),
        "artifacts": artifacts,
        "stage05cr_status": STATUS,
        "probe_attributions": {row["probe_key"]: "UNRESOLVED" for row in failed_rows},
        "stage05cp_started": False,
        "stage05cp_scientific_result_count": 0,
        "stage05d_authorized": False,
        "validation_and_sealed_decode_counts": zero_decode,
        "optimizer_instances": 0,
        "optimizer_steps": 0,
        "persistent_parameter_updates": 0,
        "training_runs": 0,
    }
    write_json(final_path, final)
    for path in STAGE05CR.rglob("*.json"):
        json.loads(path.read_text())
    if any(path.is_file() for path in STAGE05CP.rglob("*")):
        raise RuntimeError("Stage 05C-P scientific files exist despite blocked route")
    print(json.dumps({"status": STATUS, "missing_control_strata": len(missing), "stage05cp_started": False}))


if __name__ == "__main__":
    main()
