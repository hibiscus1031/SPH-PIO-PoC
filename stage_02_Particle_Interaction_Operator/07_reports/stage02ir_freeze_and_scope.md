# Stage 02I-R Freeze and Scope

## Purpose

Stage 02I-R is an audit-only conservation-compatibility closure. It investigates the non-zero total-force residual in the two frozen jitter targets and qualifies the legal scope of a future PIO architecture. It does not execute Stage 02J.

## Frozen historical state

- Stage 01: `V2_QUALIFICATION_FAIL`.
- Stage 01H: `FINITE_RESOLUTION_DOMINANT`.
- Viscosity operator form: `NOT_CONFIRMED`.
- Stage 02I: `QUALIFIED_SPATIAL_TARGET_POOL_NOT_READY`.
- Stage 02I candidates: 7 `candidate_discretization_target`, comprising 5 `pair_force_compatible` and 2 `node_residual_only`.
- Historical Stage 02J authorization: `false`.

These values are quoted, not reclassified. The 7 Stage 02I target records remain authoritative and unmodified.

## Freeze implementation

`stage02ir_input_freeze_manifest.json` records SHA-256 hashes for 12 required Stage 02I/02H/02A evidence files and individual hashes for all 7 target records. The manifest includes the Stage 02I final report, case matrix, attribution paths, disorder and conservation evidence, eligibility results, Stage 02H acceptance evidence, and Stage 02A conservation contract.

The executable audit reads the frozen inputs but does not write to them. Its outputs are confined to `04_target_attribution/conservation_closure/` and `07_reports/stage02ir_*.md`.

## Permitted and prohibited operations

Permitted operations were limited to force decomposition, continuum momentum balance, particle quadrature diagnostics, SPH pair cancellation, graph representability, architecture-scope qualification, and deterministic controlled recomputation.

No target was modified. No target mean was subtracted. No pair projection was written back. No dataset, split, normalization, neural model, Transformer, optimizer, training, or benchmark performance result was produced.

## Decision rule freeze

`stage02ir_scope_and_decision_rules.yaml` freezes the architecture rules before the closure result is consumed. The hard evidence chain is continuum balance + SPH cancellation + particle quadrature + independent reference agreement + general antisymmetric pair representability. Central-force representability is retained only as an angular-momentum diagnostic.

