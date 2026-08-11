# Stage 02G — R2S Bias Audit

## Audit scope

The audited reference is `r2s_quadratic_kernel_weighted_wls_v1`. All evaluations use the same timestamp, state sample, EOS, cubic-spline kernel family, physical pressure-plus-viscosity model, and neighbor graph as the corresponding SPH evaluation. The analytic periodic-vortex spatial derivatives are used only to quantify R2S reconstruction bias; they are not substituted as a target source. No temporal derivative is used.

## Local reconstruction diagnostics

Across the three regular resolution-extension cases and the regular/jitter-5%/jitter-10% sensitivity cases:

- minimum local matrix rank is 5;
- maximum condition number is 5.7363;
- maximum polynomial reproduction error is \(1.19\times10^{-14}\);
- maximum local relative reconstruction residual ranges from 0.0336 at 20×20 to 0.1010 for jitter-10%;
- active kernel-neighbor counts are 20–21.

Regular geometry has a minimum weighted-moment isotropy ratio numerically equal to 1.000. It falls to 0.9154 at jitter-5% and 0.8211 at jitter-10%; the maximum angular gap increases from 0.4636 rad to 0.5190 and 0.5813 rad, respectively. Thus rank, conditioning, and polynomial reproduction remain qualified, while the field reconstruction residual and geometry degradation are measurable.

## Analytic bias audit

| Resolution | R2S bias L2 RMS | Target L2 RMS | Bias / target |
|---:|---:|---:|---:|
| 12×12 | 5.464031e-2 | 3.075490e-3 | 17.7664 |
| 16×16 | 3.152940e-2 | 4.608980e-4 | 68.4086 |
| 20×20 | 2.041957e-2 | 1.732677e-3 | 11.7850 |

The absolute R2S bias decreases with resolution, but it is much larger than the R2S–SPH difference. The particularly large 16×16 ratio results from near-cancellation between R2S and SPH biases, not from an absolute R2S-bias increase. The target therefore contains measurable R2S reconstruction bias and does not meet the predeclared 0.25 bias-to-target bound.

## Disorder sensitivity

At fixed 12×12 resolution and `H/dx=2.6`, R2S-bias amplification relative to the regular case is 1.00169 for jitter-5% and 1.00657 for jitter-10%. This passes the predeclared maximum amplification of 2.0. Disorder sensitivity is bounded in this controlled matrix, but that result does not repair the failed bias-to-target qualification.

## Verdict

The R2S bias audit is `DIAGNOSTIC`. Local algebraic quality passes, and disorder amplification is bounded, but the reference reconstruction bias is not small relative to `delta_a_space`. This does not confirm the historical viscosity operator form or continuum model-form alignment.

Evidence: `04_target_attribution/r2s_bias_audit/r2s_bias_audit.json`.
