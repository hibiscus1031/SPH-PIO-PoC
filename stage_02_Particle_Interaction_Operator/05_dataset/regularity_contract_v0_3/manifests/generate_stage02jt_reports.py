#!/usr/bin/env python3
"""Generate Stage 02J-T reports from the stopped development-gate path."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[4]
STAGE = REPO / "stage_02_Particle_Interaction_Operator"
ROOT = STAGE / "05_dataset/regularity_contract_v0_3"
REPORT = STAGE / "07_reports"


def read(name: str) -> dict[str, Any]:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write(name: str, body: str) -> None:
    path = REPORT / name
    if path.exists():
        raise FileExistsError(path)
    path.write_text(body.rstrip() + "\n", encoding="utf-8")


def main() -> int:
    freeze = read("freeze/stage02jt_input_freeze_manifest.json")
    decomp = read("decomposition/development_metric_decomposition.json")
    sign = read("control_semantics/signflip_semantics.json")
    calibration = read("statistical_calibration/control_calibration.json")
    structured = read("statistical_calibration/development_structured_results.json")
    invariance = read("decomposition/v03_invariance.json")
    gate = read("contract_design/v03_development_gate.json")
    nonqual = read("contract_design/v03_contract_nonqualification.json")
    blind_gen = read("blind_family_generator/blind_generation_status.json")
    blind_ref = read("blind_reference_qualification/blind_reference_qualification_status.json")
    blind_target = read("blind_target_qualification/blind_target_qualification_status.json")
    transfer = read("blind_transfer/blind_transfer_decision.json")
    integrity = read("manifests/historical_integrity_verification.json")
    generator_freeze = yaml.safe_load((ROOT / "blind_family_generator/blind_generator_freeze.yaml").read_text(encoding="utf-8"))

    decomposition_rows = "\n".join(
        f"| {row['case_id']} | {row['S_h']:.12f} | {row['M_h']:.12f} | {row['D_h']:.12f} | {row['closure_absolute_error']:.3e} | {row['closure_status']} |"
        for row in decomp["rows"]
    )
    calibration_rows = "\n".join(
        f"| {row['case_id']} | {row['control_id']} | {row['joint_false_positive_count']}/512 | "
        f"{row['empirical_joint_false_positive_rate']:.6f} | {row['one_sided_95_Clopper_Pearson_upper']:.6f} | {row['status']} |"
        for row in calibration["rows"]
    )
    structured_rows = "\n".join(
        f"| {row['case_id']} | {row['M_h']:.12f} | {row['D_h']:.12f} | {row['p_mag']:.12f} | {row['p_dir']:.12f} | "
        f"{'PASS' if row['joint_structured_PASS'] else 'FAIL'} |"
        for row in structured["rows"] if "resolution" in row["path_membership"]
    )
    blind_rows = "\n".join(
        f"| {row['family_id']} | {row['role']} | {row['root_seed']} | NOT MATERIALIZED |"
        for row in generator_freeze["families"]
    )

    write("stage02jt_freeze_and_scope.md", f"""# Stage 02J-T Freeze and Scope

Stage 02J-R remains `MULTIFAMILY_CONTROLLED_DATASET_NOT_READY`; Stage 02J-S remains `VERSIONED_MULTIFAMILY_DATASET_NOT_READY`. The 15 v0.1 candidates remain diagnostic/nonmaterialized, the v0.2 qualified count remains zero, and Stage 02K authorization remains false.

- Historical files frozen: {freeze['historical_file_count']}.
- Historical files verified unchanged: {integrity['verified_file_count']}.
- Candidate preregistration hash: `{freeze['candidate_preregistration_hash']}`.
- Blind generator source hash: `{freeze['blind_generator_source_hash']}`.
- Blind generator freeze hash: `{freeze['blind_generator_freeze_hash']}`.
- DIAGONAL_B/MIXED_C used for selection or blind proof: no.

No historical target, verdict, family formula, threshold, dataset, split, normalization, model, or training artifact was modified.
""")

    write("stage02jt_metric_decomposition.md", f"""# Stage 02J-T Metric Decomposition

The original v0.2 `S_h` was not redefined. For every active reciprocal undirected edge, the audit used `E_mag=(q_i-q_j)^2` and `E_dir=max(0, ||delta_i-delta_j||^2-E_mag)`, followed by the frozen distance and RMS normalization.

| Case | S_h | M_h | D_h | closure abs. error | Status |
|---|---:|---:|---:|---:|---|
{decomposition_rows}

All {len(decomp['rows'])} development cases satisfy `S_h^2=M_h^2+D_h^2`. The maximum absolute closure error is `{decomp['maximum_closure_absolute_error']:.3e}`, within the frozen float64 tolerance. The `max(0,·)` operation was used only on the edgewise roundoff residual.
""")

    write("stage02jt_signflip_semantics.md", f"""# Stage 02J-T Sign-Flip Semantics

All 384 Stage 02J-S RANDOM_PARTICLE_SIGN_FLIP realizations were reconstructed. Particlewise magnitude-position mappings were preserved in every realization.

- Historical S_h false positives: {sign['old_false_positive_count']}.
- Magnitude-significant among those: {int(sign['old_false_positive_magnitude_significance_rate']*sign['old_false_positive_count'])}/{sign['old_false_positive_count']} ({sign['old_false_positive_magnitude_significance_rate']:.6f}).
- Direction-significant among those: {int(sign['old_false_positive_direction_significance_rate']*sign['old_false_positive_count'])}/{sign['old_false_positive_count']} ({sign['old_false_positive_direction_significance_rate']:.6f}).
- v0.3 joint PASS across all 384 realizations: {sum(row['joint_v0_3_PASS'] for row in sign['rows'])}.
- Frozen semantic classification: **{sign['classification']}**.

The result is mixed under the preregistered 80%/20% classification rule: magnitude significance is common but does not reach the 80% dominance threshold; direction significance is rare. This conclusion was not preset and does not alter the Stage 02J-S failure.
""")

    write("stage02jt_statistical_calibration.md", f"""# Stage 02J-T Statistical Calibration

The audit evaluated six development resolution cases, five controls, 512 preregistered realizations per case/control, and 256 case-hashed permutations per realization. Seeds follow the exact frozen SHA-256 construction and were not screened or replaced.

| Case | Control | Joint FP | Raw rate | One-sided 95% CP upper | Status |
|---|---|---:|---:|---:|---|
{calibration_rows}

All 30 case/control combinations pass the required `Clopper–Pearson upper <= 0.05` gate. The largest upper bound is `{max(row['one_sided_95_Clopper_Pearson_upper'] for row in calibration['rows']):.12f}` (PV N12, RANDOM_PARTICLE_SIGN_FLIP, 7/512). Raw rate alone was not used as the qualification gate.
""")

    write("stage02jt_v03_contract.md", f"""# Stage 02J-T v0.3 Contract Decision

Exactly one candidate was preregistered: `attribution_contract_v0_3 = magnitude_direction_conjunction`. No metric sweep or post-observation selection was performed.

The development gate results are:

| Gate | Result |
|---|---|
| Decomposition identity | {gate['checks']['decomposition_identity']} |
| Sign-flip mechanism resolved | {gate['checks']['signflip_mechanism_resolved']} |
| Development structured targets | {gate['checks']['development_structured']} |
| Control calibration | {gate['checks']['control_calibration']} |
| Invariance | {gate['checks']['invariance']} |

Because development structured targets failed, `regularity_contract_v0_3.yaml` was not generated. Therefore the final v0.3 contract SHA-256 is **NOT GENERATED**; only the prospective candidate preregistration hash `{freeze['candidate_preregistration_hash']}` exists. Thresholds and equations were not modified after the failure.
""")

    write("stage02jt_blind_family_design.md", f"""# Stage 02J-T Blind Family Design

The generator code, ten-mode pool, roles, seeds, density L1 bound (0.0045), velocity component L1 bound (0.018), and analytic Mach upper bound (0.0254558441) were frozen before development execution.

| Family | Role | Root seed | Formula |
|---|---|---:|---|
{blind_rows}

The development gate did not authorize a final v0.3 contract hash. Consequently the generator was not executed and no concrete density or velocity formula was materialized or viewed. No family was rejected, replaced, or selected using target/regularity results.
""")

    write("stage02jt_blind_reference_qualification.md", f"""# Stage 02J-T Blind Reference Qualification

Blind formulas were not materialized, so the following were not executed or claimed:

- density positivity and Mach bound;
- closed-form derivative unit tests;
- Fourier–analytic reference acceptance;
- deterministic repeat and six-bucket uncertainty;
- pair-only total-force and antisymmetric representability audits.

Blind families evaluated: {blind_ref['blind_family_count_evaluated']}; reference qualified: {blind_ref['reference_qualified_count']}. This is a gated non-execution result, not missing provenance.
""")

    write("stage02jt_blind_transfer.md", f"""# Stage 02J-T Blind Transfer

The v0.3 contract-generation gate closed before blind formula materialization. Therefore:

- blind target fields generated: {blind_target['blind_target_count_generated']};
- blind conservation-qualified families: {blind_target['conservation_qualified_family_count']}/4;
- blind regularity-qualified families: {blind_target['regularity_qualified_family_count']}/4;
- blind families evaluated: {transfer['blind_family_evaluated_count']}/4;
- Stage 02J-U authorization: `{str(transfer['stage02ju_authorized']).lower()}`.

DIAGONAL_B and MIXED_C remain historical, non-blind evidence and were not counted. No auxiliary version-transfer audit was needed after the upstream failure.
""")

    write("stage02jt_final_report.md", f"""# Stage 02J-T Final Report

## Final status

**REGULARITY_GATE_V03_NOT_QUALIFIED**

Stage 02J-U authorization is **false**.

## 1–5. Historical preservation, decomposition, closure, semantics, and single candidate

Stage 02J-S remains `VERSIONED_MULTIFAMILY_DATASET_NOT_READY`; its negative-control failure and closed held-out gate are unchanged. The v0.1 candidate state remains diagnostic/nonmaterialized, v0.2 qualified candidates remain zero, and Stage 02K remains unauthorized.

The algebraic decomposition was evaluated without redefining `S_h`. All ten development cases satisfy `S_h^2=M_h^2+D_h^2`; the maximum absolute closure error is `{decomp['maximum_closure_absolute_error']:.3e}`. The Stage 02J-S sign-flip mechanism is **{sign['classification']}** under the preregistered semantic rule: 10/14 historical false positives were magnitude-significant, 1/14 direction-significant, and all particlewise magnitude-position mappings were preserved.

Only `attribution_contract_v0_3 = magnitude_direction_conjunction` was preregistered. No candidate sweep or post-result choice was used.

## 6–9. Calibration, Clopper–Pearson, structured targets, and invariance

All 30 development case/control combinations passed the 512-realization, one-sided 95% Clopper–Pearson gate. The maximum upper bound was `{max(row['one_sided_95_Clopper_Pearson_upper'] for row in calibration['rows']):.12f}`.

| Development resolution case | M_h | D_h | p_mag | p_dir | Joint |
|---|---:|---:|---:|---:|---|
{structured_rows}

PV_EXISTING passed 3/3. CROSSMODE_A failed because N12 has `p_mag=0.778210116732`, although `p_dir=1/257` and all refinement/non-null gates passed. This single required structured-gate failure prevents v0.3 qualification. All {len(invariance['rows'])} requested M/D/p invariance checks passed.

## 10–17. Contract hash, blind freeze, formulas, reference, conservation, transfer, and non-blind boundary

- Final `regularity_contract_v0_3.yaml` hash: **NOT GENERATED**.
- Prospective candidate hash: `{freeze['candidate_preregistration_hash']}`.
- Blind generator source/freeze hashes were recorded before development execution.
- Four preregistered blind identities and seeds were retained, but concrete formulas were not materialized.
- Positivity/Mach, blind references, uncertainties, conservation, and regularity were not evaluated because the contract hash gate never opened.
- No blind family was replaced.
- DIAGONAL_B/MIXED_C remained historical non-blind evidence and contributed nothing to qualification.

## 18–22. Authorization, prohibited work, and integrity

- Stage 02J-U authorized: **false**.
- Dataset records materialized: **no**.
- Split or normalization performed: **no**.
- Model, Transformer, attention, or neural network implemented: **no**.
- Training or optimizer executed: **no**.
- Performance claim produced: **no**.
- Historical files unchanged: {integrity['verified_file_count']}/{integrity['expected_file_count']}; mismatches: {len(integrity['mismatches'])}.
- Stage 01 modified: **no**.

No threshold, target, formula, family role, or verdict was changed to make a candidate pass.
""")

    names = [
        "stage02jt_freeze_and_scope.md", "stage02jt_metric_decomposition.md", "stage02jt_signflip_semantics.md",
        "stage02jt_statistical_calibration.md", "stage02jt_v03_contract.md", "stage02jt_blind_family_design.md",
        "stage02jt_blind_reference_qualification.md", "stage02jt_blind_transfer.md", "stage02jt_final_report.md",
    ]
    manifest = {
        "manifest_version": "stage02jt-run-manifest-0.3.0",
        "final_status": "REGULARITY_GATE_V03_NOT_QUALIFIED",
        "candidate_preregistration_hash": freeze["candidate_preregistration_hash"],
        "final_v03_contract_hash": None, "blind_formulas_materialized": False,
        "stage02ju_authorized": False, "dataset_materialized": False,
        "model_generated": False, "training_performed": False,
        "report_hashes": {name: sha(REPORT / name) for name in names},
    }
    path = ROOT / "manifests/stage02jt_run_manifest.json"
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"reports": len(names), "status": manifest["final_status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
