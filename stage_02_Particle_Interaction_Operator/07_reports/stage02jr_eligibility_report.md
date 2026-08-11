# Stage 02J-R Eligibility Report

The realized dataset still contains the five existing PV records. They retain 12/14 gates: family preregistration, historical reference/target/conservation, schema, canonical, provenance, uncertainty, topology, determinism, family assignment, and leakage pass. The expanded prefrozen split fails and normalization is blocked.

Dataset-record verdicts:

- 0 `eligible_for_future_training`;
- 5 `diagnostic`;
- 0 `rejected`.

The 15 new target candidates are separately retained as `diagnostic_nonmaterialized_candidate`. Each has accepted references and pair-only conservation but only 5/6 attribution, with reason `DIAG_PCG64_PERMUTED_NULL_RATIO_GATE_FAIL`. They are not dataset records or training labels.

Manual override is forbidden. Stage 02K authorization remains false.

The two Stage 02J jitter records remain distribution-shift diagnostic-only. Stage 01 R3 shear and acoustic remain whole-class independent validation-only; none were used for formulas, family expansion, normalization, threshold selection, or eligibility improvement.

