# Stage 02F — Target Attribution

## Six-component rule

A candidate can be promoted only when all six components pass: spatial consistency, resolution trend, support consistency, temporal contamination, reference sensitivity, and model-form compatibility. There is no manual verdict override.

## Results

All five candidates have the same categorical vector:

| Component | Result | Evidence boundary |
|---|---|---|
| spatial consistency | PASS | nonzero target, topology PASS, R2S qualification PASS |
| resolution trend | DIAGNOSTIC | smoothness ratio exceeds the frozen 0.9 bound |
| support consistency | PASS | fixed-N three-level path passes |
| temporal contamination | PASS | no temporal derivative or temporal input is used |
| reference sensitivity | PASS | primary/pseudoinverse difference is below \(10^{-10}\) |
| model-form compatibility | PASS, R2S internal scope | same physical model/EOS/kernel; no continuum-form confirmation |

Each candidate therefore has 5/6 passing components and verdict `diagnostic`. Counts are:

- qualified candidate: 0;
- diagnostic: 5;
- rejected: 0;
- nonzero target retained: 5;
- zero target retained: 0;
- topology failure retained: 0.

The reason code for all five records is `UNRESOLVED_RESOLUTION_ATTRIBUTION`. No candidate is designated `candidate_discretization_target`.

## Failure retention and historical interpretation

The unresolved smoothness result remains in the attribution ledger with full target vectors, hashes, and provenance. The protocol would likewise retain zero targets and topology failures; none occurred in this five-case matrix. The R2S-internal compatibility pass does not alter Stage 01 `V2_QUALIFICATION_FAIL`, Stage 01H `FINITE_RESOLUTION_DOMINANT`, Stage 02E's zero candidate count, or viscosity operator form `NOT CONFIRMED`.

Machine-readable results are in `04_target_attribution/qualification/spatial_attribution_results.json`.
