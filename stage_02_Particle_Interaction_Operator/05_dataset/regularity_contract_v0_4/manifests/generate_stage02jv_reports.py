#!/usr/bin/env python3
"""Generate Stage 02J-V route-termination reports."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[4]
STAGE = REPO / "stage_02_Particle_Interaction_Operator"
ROOT = STAGE / "05_dataset/regularity_contract_v0_4"
REPORT = STAGE / "07_reports"


def read(name: str) -> dict[str, Any]:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def write(name: str, body: str) -> None:
    path = REPORT / name
    if path.exists(): raise FileExistsError(path)
    path.write_text(body.rstrip() + "\n", encoding="utf-8")


def main() -> int:
    freeze = read("freeze/stage02jv_input_freeze_manifest.json")
    necessity = read("necessity_controls/positive_control_results.json")
    ablation = read("necessity_controls/signflip_ablation_results.json")
    development = read("development/development_real_target_results.json")
    calibration = read("calibration/hard_negative_calibration.json")
    invariance = read("invariance/v04_invariance_results.json")
    diag = read("invariance/direction_only_roundoff_diagnostics.json")
    gate = read("contract_design/v04_development_gate.json")
    nonqual = read("contract_design/v04_contract_nonqualification.json")
    blind_mat = read("blind_materialization/blind_materialization_status.json")
    blind_ref = read("blind_reference/blind_reference_status.json")
    blind_cons = read("blind_conservation/blind_conservation_status.json")
    blind_reg = read("blind_regularity/blind_regularity_status.json")
    auxiliary = read("auxiliary_transfer/auxiliary_transfer_status.json")
    route = read("manifests/route_termination_decision.json")
    integrity = read("manifests/historical_integrity_verification.json")

    positive_rows = "\n".join(
        f"| {row['case_id']} | {row['control_id']} | {row['p_mag']:.12f} | {row['p_dir']:.12f} | {row['p_any']:.12f} | {row['status']} |"
        for row in necessity["rows"]
    )
    dev_rows = "\n".join(
        f"| {row['case_id']} | {row['p_mag']:.12f} | {row['p_dir']:.12f} | {row['p_any']:.12f} | PASS |"
        for row in development["rows"]
    )
    cal_rows = "\n".join(
        f"| {row['case_id']} | {row['control_id']} | {row['false_positive_count']}/512 | {row['raw_rate']:.6f} | {row['one_sided_95_Clopper_Pearson_upper']:.6f} | {row['status']} |"
        for row in calibration["rows"]
    )
    failure_rows = "\n".join(
        f"| {row['case_id']} | {row['population']} | {row['transformation']} | p_mag only |"
        for row in invariance["rows"] if row["status"] == "FAIL"
    )
    refinement_rows = "\n".join(
        f"| {row['family_id']} | {row['magnitude']['applicability']} | {row['magnitude']['OLS_slope']:.12f} | "
        f"{row['direction']['applicability']} | {row['direction']['OLS_slope']:.12f} | {row['status']} |"
        for row in development["family_summaries"]
    )

    write("stage02jv_freeze_and_scope.md", f"""# Stage 02J-V Freeze and Scope

Stage 02J-T remains `REGULARITY_GATE_V03_NOT_QUALIFIED`; the final v0.3 contract remains absent. Stage 02J-U and Stage 02K remain unauthorized. No historical target, candidate verdict, generator, seed, or contract was changed.

- Historical files frozen: {freeze['historical_file_count']}.
- Historical files verified unchanged: {integrity['verified_file_count']}.
- v0.4 single-candidate preregistration hash: `{freeze['candidate_preregistration_hash']}`.
- Frozen blind generator source hash: `{freeze['blind_generator_source_hash']}`.
- Frozen blind generator configuration hash: `{freeze['blind_generator_freeze_hash']}`.

The stage permitted only prospective controls and qualification. It created no dataset, split, normalization, model, optimizer, training, or performance result.
""")

    write("stage02jv_necessity_controls.md", f"""# Stage 02J-V Necessity Controls

## Necessity argument

A vector correction may be spatially identifiable through magnitude, direction, or both. Requiring simultaneous component significance is therefore not necessary. The sole prospective statistic was `p_any=min(1,2*min(p_mag,p_dir))`, with the factor 2 frozen before execution.

| Case | Control | p_mag | p_dir | p_any | Status |
|---|---|---:|---:|---:|---|
{positive_rows}

All {necessity['positive_control_case_count']} learnable positive-control cases passed. The six CONSTANT_VECTOR cases uniquely produced `M_h=D_h=0`, `p_mag=p_dir=p_any=1` and passed zero-variation handling; they were not treated as learnable corrections.

RANDOM_PARTICLE_SIGN_FLIP was retained as `DIRECTION_ABLATION_CONTROL`, not a hard negative: all {ablation['magnitude_mapping_preserved_count']}/{ablation['realization_count']} magnitude mappings were preserved, {ablation['p_any_PASS_count']} realizations had `p_any<=0.01`, and none contributed to hard-negative false-positive counts.
""")

    write("stage02jv_contract_design.md", f"""# Stage 02J-V Contract Design

Exactly one v0.4 candidate was preregistered. It directly reused the frozen M/D edge set, distance normalization, RMS normalization, epsilon values, and 256 case-hashed PCG64 permutations. No metric sweep was performed.

The candidate froze:

- `p_any=min(1,2*min(p_mag,p_dir)) <= 0.01`;
- four hard negatives and sign-flip ablation semantics;
- 512-realization, one-sided 95% Clopper–Pearson calibration;
- component-applicable refinement;
- exact invariance of `M_h`, `D_h`, `p_mag`, `p_dir`, and `p_any`.

Gate results: decomposition reuse PASS, positive controls PASS, hard-negative calibration PASS, development targets PASS, invariance FAIL. Consequently `regularity_contract_v0_4.yaml` was not generated and its final hash is **NOT GENERATED**. No factor, threshold, or tolerance was changed.
""")

    write("stage02jv_development_results.md", f"""# Stage 02J-V Development Results

| Case | p_mag | p_dir | p_any | Real-target gate |
|---|---:|---:|---:|---|
{dev_rows}

All six development real targets passed `p_any<=0.01` and the four frozen non-null gates.

| Family | M applicability | M slope | D applicability | D slope | Result |
|---|---|---:|---|---:|---|
{refinement_rows}

For CROSSMODE_A, low-resolution magnitude is non-significant (`p_mag=0.778210116732`), so M refinement is diagnostic; direction is significant and its endpoint/slope refinement passes. No convergence order is claimed.
""")

    write("stage02jv_control_calibration.md", f"""# Stage 02J-V Hard-Negative Calibration

Each of 24 development case/control combinations used 512 preregistered realizations and 256 permutation nulls per realization. Seeds used the frozen `stage02jv || case || control || realization` SHA-256 rule without screening.

| Case | Hard negative | False positives | Raw rate | One-sided 95% CP upper | Status |
|---|---|---:|---:|---:|---|
{cal_rows}

All combinations pass `CP upper <= 0.05`; the maximum upper bound is `{max(row['one_sided_95_Clopper_Pearson_upper'] for row in calibration['rows']):.12f}`. Sign flip was excluded from this false-positive rate exactly as preregistered.
""")

    write("stage02jv_invariance.md", f"""# Stage 02J-V Invariance

The audit executed {len(invariance['rows'])} transformations across six real targets and 18 learnable positive-control fields. Nine checks failed:

| Case | Population | Transformation | Failed quantity |
|---|---|---|---|
{failure_rows}

Every failure is confined to exact `p_mag` equality for DIRECTION_ONLY_SMOOTH under amplitude scaling. The theoretical magnitude component is zero, but float64 magnitude spans of order `1e-19`–`1e-16` changed permutation tie ranks. `M_h` remained within the frozen metric tolerance, while `D_h`, `p_dir`, and the decision statistic `p_any` remained invariant.

The contract nevertheless requires all five quantities to remain invariant. No unregistered zero threshold or tie rule was introduced, so the invariance gate is `FAIL` and is retained as a scientific qualification failure.
""")

    write("stage02jv_blind_family_materialization.md", f"""# Stage 02J-V Blind Family Materialization

The blind generator source, mode pool, four identities, roles, and seeds remain frozen and unchanged. Because no final v0.4 contract hash was generated, the materialization gate did not open.

- Concrete blind formulas materialized: {blind_mat['formula_count']}.
- Family replacement or seed redraw: false.
- Formula, derivative, lineage, density-bound, or Mach-bound artifacts claimed: none.
- Status: `{blind_mat['status']}`.
""")

    write("stage02jv_blind_reference_and_conservation.md", f"""# Stage 02J-V Blind Reference and Conservation

Blind formulas were not materialized. Therefore density positivity, Mach bounds, derivative tests, Fourier–analytic reference acceptance, reference uncertainty, deterministic repeat, total-force residual, and antisymmetric representability were not executed.

- Reference families evaluated/qualified: {blind_ref['families_evaluated']}/{blind_ref['reference_qualified']}.
- Conservation families evaluated: {blind_cons['families_evaluated']}.
- Total-force qualified: {blind_cons['total_force_qualified']}.
- Antisymmetric-representability qualified: {blind_cons['antisymmetric_representability_qualified']}.

These are gated non-execution results, not inferred failures of unseen formulas.
""")

    write("stage02jv_blind_regularity.md", f"""# Stage 02J-V Blind Regularity

Blind regularity required a frozen final v0.4 contract plus physical/reference/conservation qualification. The upstream invariance failure prevented all of these gates.

- Blind families evaluated: {blind_reg['families_evaluated']}/4.
- Blind families with 3/3 PASS: {blind_reg['families_3_of_3_PASS']}/4.
- Contract, threshold, seed, or family modification: none.
- Status: `{blind_reg['status']}`.
""")

    write("stage02jv_auxiliary_transfer.md", f"""# Stage 02J-V Auxiliary Transfer

DIAGONAL_B and MIXED_C remain `historical_nonblind_auxiliary_only`. Auxiliary v0.4 evaluation was permitted only after 4/4 blind qualification, which was not reached.

- DIAGONAL_B: `{auxiliary['DIAGONAL_B_status']}`.
- MIXED_C: `{auxiliary['MIXED_C_status']}`.
- Counted in qualification or blind proof: false.
- Threshold-selection use: none.
""")

    write("stage02jv_final_report.md", f"""# Stage 02J-V Final Report

## Final status

**REGULARITY_HARD_GATE_ROUTE_TERMINATED**

Stage 02J-U authorization: **false**. Stage 02K authorization: **false**. No v0.5 design is permitted.

## 1–6. Historical preservation, necessity, controls, ablation, and Bonferroni statistic

Stage 02J-T remains `REGULARITY_GATE_V03_NOT_QUALIFIED`; its evidence and absent final v0.3 contract are preserved. v0.4 tested the preregistered necessity argument that vector structure may occur in magnitude, direction, or both. The sole test was `p_any=min(1,2*min(p_mag,p_dir))<=0.01`; neither factor nor threshold changed after execution.

All 18 magnitude-only, direction-only, and joint positive-control cases passed. All six constant-vector zero-variation checks passed. RANDOM_PARTICLE_SIGN_FLIP remained a reported direction-ablation control and did not enter hard-negative false-positive counts.

## 7–10. Calibration, development targets, refinement, and invariance

All 24 hard-negative case/control combinations passed the 512-realization one-sided 95% Clopper–Pearson gate; the maximum upper bound was `{max(row['one_sided_95_Clopper_Pearson_upper'] for row in calibration['rows']):.12f}`.

All six PV/CROSSMODE real targets passed `p_any` and their non-null gates. Component applicability behaved as preregistered: CROSSMODE N12 magnitude refinement was diagnostic because `p_mag=0.778210116732`, while direction refinement was hard and passed.

Invariance failed 9/192 transformation rows. Every failure was exact `p_mag` equality for DIRECTION_ONLY_SMOOTH under amplitude scaling: metric magnitudes stayed inside tolerance and `p_dir/p_any` stayed exact, but near-zero float64 magnitude variation changed the permutation rank. The contract required `p_mag` itself to remain invariant, so this is a hard scientific-gate failure; no posthoc zero threshold was added.

## 11–17. Contract, blind, and auxiliary evidence

- Final v0.4 contract hash: **NOT GENERATED**.
- Concrete blind formulas: not materialized.
- Blind physical bounds/references: not evaluated.
- Blind conservation: not evaluated.
- Blind regularity: 0/4 evaluated.
- DIAGONAL_B/MIXED_C: retained as historical non-blind auxiliary-only; not evaluated or counted.

## 18–23. Route termination and prohibitions

The regularity-hard-gate route is terminated. v0.1, v0.2, the v0.3 candidate, and the v0.4 candidate remain preserved. No v0.5 may be designed. Smoothness/regularity may be used only as diagnostic evidence and may not replace dataset eligibility.

- Stage 02J-U authorized: **false**.
- Stage 02K authorized: **false**.
- Dataset materialization, split, or normalization: **none**.
- Model, Transformer, attention, or neural network: **none**.
- Optimizer or training: **none**.
- Performance claim: **none**.
- Historical hashes unchanged: {integrity['verified_file_count']}/{integrity['expected_file_count']}; mismatches: {len(integrity['mismatches'])}.
- Stage 01 modified: **no**.
""")

    names = [
        "stage02jv_freeze_and_scope.md", "stage02jv_necessity_controls.md", "stage02jv_contract_design.md",
        "stage02jv_development_results.md", "stage02jv_control_calibration.md", "stage02jv_invariance.md",
        "stage02jv_blind_family_materialization.md", "stage02jv_blind_reference_and_conservation.md",
        "stage02jv_blind_regularity.md", "stage02jv_auxiliary_transfer.md", "stage02jv_final_report.md",
    ]
    manifest = {
        "manifest_version": "stage02jv-run-manifest-0.4.0",
        "final_status": "REGULARITY_HARD_GATE_ROUTE_TERMINATED",
        "candidate_preregistration_hash": freeze["candidate_preregistration_hash"],
        "final_v04_contract_hash": None, "v0_5_design_permitted": False,
        "blind_formulas_materialized": False, "stage02ju_authorized": False, "stage02k_authorized": False,
        "dataset_materialized": False, "model_generated": False, "training_performed": False,
        "report_hashes": {name: sha(REPORT / name) for name in names},
    }
    path = ROOT / "manifests/stage02jv_run_manifest.json"
    if path.exists(): raise FileExistsError(path)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"reports": len(names), "status": manifest["final_status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
