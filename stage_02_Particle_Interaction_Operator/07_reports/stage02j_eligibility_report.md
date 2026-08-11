# Stage 02J Eligibility Report

## Record gates

Every regular record passes the first ten gates:

1. source target qualified;
2. pair-only scope authorized;
3. schema;
4. canonical serialization;
5. provenance;
6. uncertainty;
7. topology;
8. determinism;
9. family assignment;
10. leakage audit.

Every record then encounters the same two blockers:

- split assignment: `FAIL_INSUFFICIENT_DISCONNECTED_FAMILIES`;
- normalization: `BLOCKED_NO_FORMAL_TRAIN_SPLIT`.

The derived counts are 0 `eligible_for_future_training`, 5 `diagnostic`, and 0 `rejected`. The reason codes are `DIAG_INSUFFICIENT_LEAKAGE_DISCONNECTED_FAMILIES` and `DIAG_NORMALIZATION_NOT_FITTED_NO_FORMAL_TRAIN_SPLIT`.

`manual_override_permitted=false`. Passing source, schema, topology, determinism, and provenance gates does not bypass family isolation, split, or normalization gates.

## Readiness and next-stage boundary

The controlled records are scientifically retained as a development/audit corpus, but the dataset is not ready for future training. Stage 02K authorization is `false`. No model or training stage may use these records under the current eligibility result.

