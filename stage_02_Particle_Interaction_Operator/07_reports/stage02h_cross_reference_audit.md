# Stage 02H — Cross-Reference Audit

## Comparison contract

Every candidate pair is compared on all six frozen cases using

\[
\lVert a_{ref1}-a_{ref2}\rVert.
\]

The audit records particle-RMS \(L_2\), particle-vector \(L_\infty\), the complete particlewise difference field, a Fourier signature difference, and the cosine between the two reference-target spatial patterns. A pair passes only if every case satisfies the predeclared normalized \(L_2\), normalized \(L_\infty\), and spatial-pattern thresholds.

## Pair outcomes

| Pair | Aggregate result |
|---|---|
| QWLS2 incumbent — CWLS3 | FAIL |
| QWLS2 incumbent — Fourier2 | FAIL |
| QWLS2 incumbent — analytic | FAIL |
| CWLS3 — Fourier2 | FAIL |
| CWLS3 — analytic | FAIL |
| Fourier2 — analytic | PASS |

The CWLS3 pair with analytic/Fourier approaches the thresholds as resolution increases and passes at 20×20, but it does not pass the complete frozen suite. Those earlier failures are retained.

## Stable independent pair

Fourier2 and analytic pass all six cases. Their particle-RMS \(L_2\) acceleration differences range from \(1.22\times10^{-14}\) to \(3.31\times10^{-14}\); normalized \(L_2\) ratios remain below \(1.00\times10^{-12}\), normalized \(L_\infty\) ratios remain below \(1.16\times10^{-12}\), and all target-pattern cosines are numerically 1.

This demonstrates reference stability for the frozen periodic-vortex audit family. It does not establish stability for arbitrary particle states or authorize a target dataset.

Evidence: `04_target_attribution/r2s_comparison/cross_reference_audit.json`.
