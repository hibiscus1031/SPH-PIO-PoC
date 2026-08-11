# Stage 02I — Reference Scope Extension

## Procedure

The three regular `H/dx=2.6` resolution cases were matched to frozen Stage 02H evidence by record and acceleration hashes. The two new support cases and two N16 disorder cases were re-evaluated with the complete frozen Stage 02H acceptance contract: same state, same physics, determinism, low bias, Fourier–analytic agreement, and qualified uncertainty.

All numeric thresholds were read directly from `reference_acceptance_rules.yaml`; none was re-entered, approximated, or changed.

## Results

All seven cases pass for both `H_REF_FOURIER2` and `H_REF_ANALYTIC`. Fourier–analytic discrepancy statistics are:

| Case class | L2 discrepancy range | Normalized L2 range | Pattern cosine |
|---|---:|---:|---:|
| regular resolution | 1.22e-14–2.22e-14 | 3.85e-13–1.00e-12 | approximately 1 |
| support extension | 1.22e-14 | 1.73e-13–3.87e-13 | 1 |
| disorder extension | 1.72e-14–2.75e-14 | 1.82e-13–5.46e-13 | approximately 1 |

Every deterministic repeat has zero maximum acceleration difference. Consequently, all seven cases are admitted to target attribution. QWLS2 and CWLS3 remain diagnostic and were not used as target sources.

Machine audit: `04_target_attribution/qualified_spatial_targets/reference_extension/reference_scope_extension_audit.json`.
