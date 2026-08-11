#!/usr/bin/env python3
"""Generate the Stage 02J-S evidence reports from immutable audit artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[4]
STAGE = REPO / "stage_02_Particle_Interaction_Operator"
ROOT = STAGE / "05_dataset/regularity_contract_v0_2"
REPORT = STAGE / "07_reports"


def read(name: str) -> dict[str, Any]:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write(name: str, text: str) -> None:
    path = REPORT / name
    if path.exists():
        raise FileExistsError(path)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def main() -> int:
    freeze = read("freeze/stage02js_input_freeze_manifest.json")
    original = read("development_audit/original_gate_reproduction.json")
    sensitivity = read("development_audit/single_seed_sensitivity.json")
    dev = read("development_audit/development_regularity_audit.json")
    negative = read("negative_controls/negative_control_audit.json")
    invariance = read("invariance/invariance_audit.json")
    release = read("heldout_validation/heldout_release_gate.json")
    req = read("requalification/versioned_target_requalification.json")
    material = read("materialization/materialization_decision.json")
    leakage = read("leakage/leakage_execution_status.json")
    split = read("splits/prefrozen_split_status.json")
    norm = read("normalization/train_only_normalization_status.json")
    eligibility = read("eligibility/dataset_eligibility_results.json")
    history = read("manifests/historical_integrity_verification.json")

    v01_rows = "\n".join(
        f"| {row['case_id']} | {row['permuted_null_ratio']:.12f} | {row['v0_1_gate']} | "
        f"{('exact' if row['historical_comparison_available'] and row['exact_reproduction_status']=='PASS' else 'computed; no archived ratio')} |"
        for row in original["rows"]
    )
    dev_resolution = "\n".join(
        f"| {item['family_id']} | {', '.join(f'{x:.12f}' for x in item['S_h'])} | {item['OLS_slope_against_level_index']:.12f} | {item['status']} |"
        for item in dev["resolution_summaries"]
    )
    neg_summary = "\n".join(
        f"| {row['control_id']} | {row['smooth_false_positive_count']}/{row['realization_count']} | "
        f"{row['aggregate_false_positive_rate']:.6f} | {row['maximum_case_false_positive_rate']:.6f} | {row['status']} |"
        for row in negative["control_summaries"]
    )
    neg_fail = "\n".join(
        f"| {row['case_id']} | {row['control_id']} | {row['smooth_false_positive_count']}/64 | {row['smooth_false_positive_rate']:.6f} |"
        for row in negative["rows"] if row["status"] == "FAIL"
    )
    sensitivity_rows = "\n".join(
        f"| {row['case_id']} | {row['historical_single_seed_ratio']:.12f} | "
        f"{row['ratio_distribution']['min']:.6f}–{row['ratio_distribution']['max']:.6f} | "
        f"{row['historical_ratio_percentile_in_256_case_hashed_permutations']:.6f} | "
        f"{row['v0_1_gate_pass_fraction_across_256']:.6f} |"
        for row in sensitivity["rows"] if "resolution" in row["path_membership"]
    )

    write("stage02js_freeze_and_scope.md", f"""# Stage 02J-S Freeze and Scope

## Frozen boundary

Stage 02J-S was executed as a versioned regularity-contract audit. The historical Stage 02J-R outcome remains `MULTIFAMILY_CONTROLLED_DATASET_NOT_READY`; its 15 candidates remain `diagnostic_nonmaterialized_candidate_v0_1`. Stage 02K authorization remains false.

The v0.2 contract was written before development metric execution and frozen at `{freeze['contract_hash']}`. The development families are `FAMILY_PV_EXISTING` and `FAMILY_CROSSMODE_A`; `FAMILY_DIAGONAL_B` and `FAMILY_MIXED_C` remain held out. Roles and the five-case family matrix are immutable after this freeze.

## Historical preservation

- Frozen historical files: {freeze['historical_file_count']}.
- Verified unchanged after execution: {history['verified_file_count']}.
- Hash mismatches: {len(history['mismatches'])}.
- Stage 01 modified: `{str(history['stage01_modified']).lower()}`.
- Stage 01 conclusions remain `V2_QUALIFICATION_FAIL`, `FINITE_RESOLUTION_DOMINANT`, and viscosity operator form `NOT CONFIRMED`.

No target formula, trajectory, jitter label, model, training, or performance artifact was changed or created.
""")

    write("stage02js_original_gate_audit.md", f"""# Stage 02J-S Original Gate Audit

## v0.1 preservation and exact reproduction

The historical contract remains: one PCG64 particle permutation with seed `20260207`, graph-total-variation ratio, and threshold `ratio <= 0.8`. It is not corrected, deleted, or overwritten.

| Case | Reproduced ratio | v0.1 gate | Comparison |
|---|---:|---|---|
{v01_rows}

All six development rows with archived ratios reproduced with zero ratio and graph-TV drift. Four development support rows had no archived v0.1 ratio and were deterministically computed without inventing a historical comparison. The requested 20-case reproduction was not completed: DIAGONAL_B and MIXED_C remained sealed after the negative-control gate failed.

## Single-seed sensitivity

| Resolution case | Historical ratio | 256-ratio range | Historical percentile | fraction passing 0.8 |
|---|---:|---:|---:|---:|
{sensitivity_rows}

Within the development scope, the 256 preregistered case-hashed permutations did not reverse any resolution-case v0.1 verdict: CROSSMODE N12 failed for every null, while the other five resolution cases passed for every null. This demonstrates development-scope seed stability; it does not establish v0.1 necessity or sufficiency on sealed families.
""")

    write("stage02js_regularity_contract_design.md", f"""# Stage 02J-S Regularity Contract Design

## Version relationship

`attribution_contract_v0_1` remains a historical single-null diagnostic. `attribution_contract_v0_2` is a new prospective contract; it does not use the old 0.8 threshold.

## Dimensionless graph-Sobolev statistic

For active, nonzero-kernel, reciprocal undirected edges,

\\[
S_h=\\frac{{\\sqrt{{\\operatorname{{mean}}_{{(i,j)}}\\left[\\lVert\\Delta a_i-\\Delta a_j\\rVert^2/((r_{{ij}}/h)^2+\\epsilon_r)\\right]}}}}{{\\operatorname{{RMS}}(\\Delta a)+\\epsilon_a}}.
\\]

The contract freezes `epsilon_r = 3.5527136788005009e-15` (16 binary64 epsilons) and `epsilon_a = 0`; a zero target is rejected separately. Computation uses CPU float64, one graph-balanced contribution per undirected edge, minimum-image distance, and deterministic canonical ordering.

Each case uses 256 unscreened PCG64 permutations with root seed `20260207`; case seeds are the first eight big-endian bytes of `SHA256(root_seed|case_id|index)`. The prospective gate is `p_smooth=(1+count(S_perm<=S_observed))/257 <= 0.01`. Resolution behavior additionally requires high-resolution `S_h` no greater than low-resolution `S_h`, nonpositive OLS slope against the three frozen levels, and continued PASS of the four historical non-PCG64 checks. No convergence order is inferred.

The immutable contract hash is `{freeze['contract_hash']}`.
""")

    write("stage02js_negative_control_audit.md", f"""# Stage 02J-S Negative-Control Audit

Five preregistered controls were evaluated for 64 fixed-seed realizations on each of six development resolution cases. A case/control false-positive rate above 0.05 fails the frozen operational rule.

| Control | Aggregate false positives | Aggregate rate | Maximum case rate | Status |
|---|---:|---:|---:|---|
{neg_summary}

Failed case/control combinations:

| Case | Control | False positives | Rate |
|---|---|---:|---:|
{neg_fail}

Although the RANDOM_PARTICLE_SIGN_FLIP aggregate rate is 0.036458, two preregistered case rates exceed 0.05. The threshold, seeds, controls, and aggregation records were not modified after observation. Therefore negative-control discrimination is `FAIL`, and the held-out gate remains closed.
""")

    write("stage02js_invariance_audit.md", f"""# Stage 02J-S Invariance Audit

The development audit covered amplitude scales 0.1/1/10, periodic translation, x/y exchange, 90-degree vector rotation, reverse-then-recanonicalize particle order, and reversed edge direction.

- Development cases: 10.
- Transformation checks: {len(invariance['rows'])}.
- Failures: {sum(row['status'] != 'PASS' for row in invariance['rows'])}.
- Frozen tolerance: `1e-14 + 1e-12*abs(S_h)`; p-values required exact equality.
- Result: `{'PASS' if invariance['all_invariance_PASS'] else 'FAIL'}`.

This confirms the implemented statistic's requested invariances on the development scope only. It does not override the negative-control failure.
""")

    write("stage02js_heldout_validation.md", f"""# Stage 02J-S Held-Out Validation

## Release gate

| Check | Result |
|---|---|
| Contract hash frozen | {release['checks']['contract_hash_frozen']} |
| Development structured targets | {release['checks']['development_structured_targets']} |
| Negative controls | {release['checks']['negative_controls']} |
| Invariance | {release['checks']['invariance']} |

`heldout_access_authorized={str(release['heldout_access_authorized']).lower()}`.

Because negative controls failed, DIAGONAL_B validation and MIXED_C test target arrays were not opened or evaluated by the held-out phase. No statistic, epsilon, seed, p threshold, case matrix, or family role was changed. Consequently neither held-out family received a v0.2 family decision.
""")

    write("stage02js_target_requalification.md", f"""# Stage 02J-S Target Requalification

The historical v0.1 state of all 15 new-family candidates remains `diagnostic_nonmaterialized_candidate_v0_1`; no historical field was overwritten.

- CROSSMODE_A: development structured-target regularity passed, but the global negative-control requirement failed; 0/5 upgraded.
- DIAGONAL_B: held-out gate closed; 0/5 evaluated or upgraded.
- MIXED_C: held-out gate closed; 0/5 evaluated or upgraded.
- `candidate_discretization_target_v0_2=true`: {req['candidate_discretization_target_v0_2_count']}.
- Manual override: forbidden and unused.

The outcome does not say that v0.1 was wrong or that v0.2 is preferable because it admits candidates. The v0.2 evidence failed its own prospective validity gate.
""")

    write("stage02js_dataset_materialization.md", f"""# Stage 02J-S Dataset Materialization

Conditional materialization required all three new families to achieve family-level 5/5 PASS under v0.2. That precondition was not met.

- New dataset identifier reserved: `controlled_multifamily_pair_scope_v0_3`.
- Materialization authorized: `{str(material['materialization_authorized']).lower()}`.
- New graph records: {material['new_graph_records_materialized']}.
- Existing Stage 02J full graph records preserved: {material['existing_graph_records_preserved']}.
- Total full graph records available: {material['total_full_graph_records']} (not 20).
- `controlled_multifamily_pair_scope_v0_2` overwritten: `{str(material['controlled_multifamily_pair_scope_v0_2_modified']).lower()}`.

No target dataset, edge-pair label, smoothing, filtering, augmentation, or partial-family materialization was produced.
""")

    write("stage02js_leakage_split_normalization.md", f"""# Stage 02J-S Leakage, Split, and Normalization

The four family roles remain preregistered:

- future train: PV_EXISTING and CROSSMODE_A;
- future validation: DIAGONAL_B;
- future test: MIXED_C.

The 20-record corpus was not materialized, so the frozen leakage graph was not executed (`{leakage['status']}`), four disconnected components were not claimed, and the formal split was not assigned (`{split['status']}`). No particle, edge, patch, or random-frame split was used.

Train-only graph-balanced normalization was not fitted (`{norm['status']}`). Validation, test, jitter, target, reference, and target-derived fields contributed to no statistic. No normalization statistics hash exists.
""")

    write("stage02js_eligibility_report.md", f"""# Stage 02J-S Eligibility Report

No v0.3 records exist, so no record could be evaluated as 14/14 PASS.

- v0.3 record count: {eligibility['record_count_in_v0_3']}.
- `eligible_for_future_training=true`: {eligibility['eligible_for_future_training_count']}.
- Fifteen new candidates: historical diagnostic/nonmaterialized state retained.
- Two jitter records: `distribution_shift_diagnostic_only`.
- Stage 01 R3 shear/acoustic: `independent_validation_only`.
- Manual override: false.
- Stage 02K authorization: `{str(eligibility['stage02k_authorized']).lower()}`.

The absence of eligibility is an upstream regularity-contract result, not a model or performance result.
""")

    write("stage02js_final_report.md", f"""# Stage 02J-S Final Report

## Decision

**VERSIONED_MULTIFAMILY_DATASET_NOT_READY**

Stage 02K authorization is **false**.

## 1–4. Historical failure, v0.1 reproduction, sensitivity, and v0.2 preregistration

Stage 02J-R's 15 diagnostic, nonmaterialized v0.1 candidates are preserved. On the two development families, all six archived v0.1 resolution ratios reproduced exactly; ten development cases were computed in total. CROSSMODE N12 remained above 0.8 for all 256 case-hashed nulls, while the other five development resolution cases remained below 0.8 for all 256. This is development-scope stability, not a correction or universal validation of v0.1.

The prospective graph-Sobolev contract was frozen before development execution at `{freeze['contract_hash']}`. It uses a dimensionless `S_h`, 256 PCG64 permutations per case, and `p_smooth<=0.01`; the historical 0.8 threshold is not reused in v0.2.

## 5–8. Statistic, permutation evidence, negative controls, and invariance

| Development family | Resolution S_h (low, mid, high) | OLS slope | Structured result |
|---|---|---:|---|
{dev_resolution}

All six development resolution cases had `p_smooth=1/257`, and both resolution paths satisfied the frozen endpoint and slope rules. All {len(invariance['rows'])} invariance checks passed.

Negative-control discrimination failed under its frozen per-case rule. RANDOM_PARTICLE_SIGN_FLIP produced 5/64 false positives (0.078125) for PV N16 and 4/64 (0.0625) for CROSSMODE N12; both exceed 0.05. Seeds and thresholds were not screened or changed.

## 9–11. Held-out isolation, DIAGONAL_B validation, and MIXED_C test

The held-out release gate is closed. DIAGONAL_B and MIXED_C target arrays were not opened by the held-out phase and neither family was evaluated. The full 20-case v0.1 reproduction was likewise not executed, because doing so would violate the closed gate.

## 12–17. Versioned decisions, materialization, leakage, split, normalization, eligibility

- New v0.2-qualified targets: 0/15.
- New v0.3 graph records: 0/15.
- Total existing full graph records: 5, not 20.
- Four leakage-disconnected components: not evaluated or claimed.
- Prefrozen split: roles retained, assignment not executed.
- Train-only normalization: not fitted.
- Future-training eligibility: 0 records.
- Jitter remains diagnostic-only; R3 shear/acoustic remains independent-validation-only.

## 18–21. Authorization, prohibited work, and integrity

- Stage 02K authorized: **false**.
- Model or architecture implemented: **no**.
- Training or optimizer executed: **no**.
- Performance claim produced: **no**.
- Target formula, family matrix, trajectory, smoothing, filtering, and jitter labels changed: **no**.
- Historical files verified unchanged: {history['verified_file_count']}/{history['expected_file_count']}; mismatches: {len(history['mismatches'])}.
- Stage 01 modified: **no**.

This result does not claim that 20 graphs form a large dataset, that validation/test generalizes to arbitrary flows, that any model is valid, that Transformer/attention is necessary, that Stage 01 V2 is restored, or that jitter is resolved.
""")

    report_names = [
        "stage02js_freeze_and_scope.md", "stage02js_original_gate_audit.md", "stage02js_regularity_contract_design.md",
        "stage02js_negative_control_audit.md", "stage02js_invariance_audit.md", "stage02js_heldout_validation.md",
        "stage02js_target_requalification.md", "stage02js_dataset_materialization.md",
        "stage02js_leakage_split_normalization.md", "stage02js_eligibility_report.md", "stage02js_final_report.md",
    ]
    manifest = {
        "manifest_version": "stage02js-run-manifest-0.2.0",
        "contract_hash": freeze["contract_hash"], "final_status": "VERSIONED_MULTIFAMILY_DATASET_NOT_READY",
        "heldout_access_authorized": False, "new_records_materialized": 0,
        "stage02k_authorized": False, "model_generated": False, "training_performed": False,
        "report_hashes": {name: sha(REPORT / name) for name in report_names},
    }
    path = ROOT / "manifests/stage02js_run_manifest.json"
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"reports": len(report_names), "status": manifest["final_status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
