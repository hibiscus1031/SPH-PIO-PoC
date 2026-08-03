# Stage 01G-R final report — Execution Infrastructure Repair and Requalification

## 1. Stage 01G execution failure preservation

Stage 01G execution remains `V2_QUALIFICATION_EVIDENCE_INCOMPLETE`. Canonical `TypeError`, `infra_retry1` `KeyError`, and `infra_retry2` `AttributeError` evidence is retained byte-for-byte in a 21-item SHA-256 manifest. No failure was deleted, overwritten, reclassified, or treated as a benchmark failure.

## 2. Root cause

All three failures are execution-layer interface defects: missing explicit regular-layout arguments, a singular/plural reference serialization mismatch, and incorrect diagnostic use of the unsourced RK2 result schema. Categories are runner failure, runner failure, and diagnostic failure. Solver, environment, and benchmark failure are excluded.

## 3. Runner contract audit

Run ID, config, resolved parameters, output path, child launch, solver entry, diagnostic registration, and evidence writing now have explicit input/output schemas and stop boundaries. Diagnostic midpoint reconstruction is read-only and never feeds the solver. Audit: **PASS**.

## 4. Config resolution audit

`g_shear_n24` resolves every requested field explicitly, non-null, and hash-linked. No scientific parameter uses an implicit default. Audit: **PASS**.

## 5. Dry-run results

The 12 frozen run IDs pass config, directory, metadata, evaluator-schema, provenance-schema, and hash-link checks: **12/12 PASS**. The dry run did not import or call the solver.

## 6. Minimal smoke

The sole allowed `g_shear_n24_infra_smoke` completed exactly one step in an isolated CPU float64 child. Solver entry, diagnostic initialization, output schema, scalar-only parent aggregation, and child reclamation pass. No TypeError, KeyError, or AttributeError occurred. No formal benchmark metric, evaluator qualification, or V2 evidence was generated.

## 7. Modified files

All modifications are confined to `06_experiments/stage_01gr_execution_infrastructure_repair/`, six `07_reports/stage01gr_*` reports, and three `tests/test_stage01gr_*` tests. Historical Stage 01G, G-P, G-E, preflight-v2, and failed execution files are unchanged.

## 8. Solver identity

All 103 frozen numerical-source files match their recorded SHA-256 values. `01_solver/`, RK2, DOP853, pressure, viscosity, EOS, neighbor search, benchmark equations, evaluator, gates, thresholds, uncertainty budget, and run matrix have zero modifications. Solver identity: **PASS**.

## 9. Unique Stage 01G-R status

`EXECUTION_INFRA_READY_FOR_BENCHMARK`

Root cause, repair scope, solver identity, 12/12 dry resolution, one-step smoke, and provenance are complete.

## 10. Stage 01G execution reapplication

**Yes.** The project may submit a new, separately authorized Stage 01G execution application using the repaired infrastructure bundle. Stage 01G-R does not itself run or authorize formal benchmarks. Current V2 status remains `V2_QUALIFICATION_EVIDENCE_INCOMPLETE`.

V3, Stage 02, training, and label generation remain unstarted.
