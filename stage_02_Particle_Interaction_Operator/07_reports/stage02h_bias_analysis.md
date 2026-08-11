# Stage 02H — Bias and Uncertainty Analysis

## Definitions

Candidate bias is measured against the analytic spatial acceleration at the same state:

\[
b_{ref}=a_{candidate}-a_{analytic}.
\]

The normalization target is \(a_{candidate}-a_{SPH}\). The acceptance threshold for both bias/target and uncertainty/target particle-RMS \(L_2\) ratios is 0.10, frozen before execution. Numerical uncertainty conservatively combines analytic-audit bias, primary-versus-pseudoinverse sensitivity, and a \(10^{-14}\) roundoff floor. No single total GCI is generated; GCI remains not justified.

## Candidate maxima over the frozen suite

| Candidate | Max bias L2 RMS | Max bias/target | Max uncertainty/target | Result |
|---|---:|---:|---:|---|
| QWLS2 incumbent | 5.499905e-2 | 68.4086 | 68.4086 | diagnostic |
| CWLS3 | 1.223251e-2 | 0.2650 | 0.2650 | diagnostic |
| Fourier2 | 3.305882e-14 | 9.9997e-13 | 1.5466e-12 | pass |
| analytic | 0 | 0 | 5.3292e-13 | pass |

The cubic local candidate substantially reduces absolute bias relative to the incumbent, but its maximum normalized bias remains above 0.10. The threshold was not relaxed, so it remains diagnostic.

## Incumbent geometry and disorder audit

For the incumbent, the local matrix rank remains 5. Condition number rises from 5.3105 in the regular case to 5.5460 at jitter-5% and 5.7363 at jitter-10%. Reconstruction residual rises from 0.09353 to 0.09706 and 0.10096, while geometry isotropy decreases from approximately 1.000 to 0.9154 and 0.8211. Bias amplification is limited to 1.0066, but bias magnitude remains disqualifying.

These observations confirm and retain the Stage 02G R2S bias diagnostic; they do not overwrite it.

## Independent-reference uncertainty

Fourier condition numbers range from approximately 1.000 to 1.067 across regular and disordered states. Its field-reconstruction residual remains below \(9.25\times10^{-14}\), and its maximum acceleration bias is \(3.31\times10^{-14}\). Agreement with the analytic candidate provides an independent stability check rather than reliance on the Fourier solver's internal sensitivity alone.

Evidence: `04_target_attribution/bias_analysis/reference_bias_analysis.json`.
