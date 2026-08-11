# Stage 02G — Smoothness Criterion Audit

## Stage 02F rule retained

Stage 02F used graph total-variation RMS divided by the graph total variation of `roll(delta_a_space, 7)`, with a frozen upper threshold of 0.9. Its five diagnostic records and failed smoothness decision are not changed. Stage 02G did not lower the threshold.

On the new 12×12, 16×16, and 20×20 path, the same ratios are 0.9842, 0.9982, and 0.9876, so they also exceed 0.9.

## Mathematical audit

### Criterion meaning

Graph total variation is the RMS norm of neighboring vector differences. It is a useful local-variation statistic, but its ratio is interpretable only if the denominator is a genuine null that destroys spatial association while preserving the vector-value distribution.

### Null-field suitability

A seven-index cyclic roll is not such a null on a periodic structured lattice. It acts partly as a spatial translation, can preserve low Fourier modes, and has an N-dependent geometric meaning. Observed original-versus-roll vector correlations vary from −0.7793 to 0.6331 rather than representing a stable decorrelated baseline. The cyclic null is therefore unsuitable as a standalone attribution gate.

### Boundary effect

The physical neighbor graph is periodic and has no boundary. Flattened-index wrapping nevertheless introduces an artificial index seam whose physical mapping changes with N. This effect is classified diagnostic rather than interpreted as physical roughness.

### Vector cancellation

The implemented graph-TV statistic squares componentwise neighbor differences before averaging. Signed cancellation across particles or vector components does not explain the Stage 02F failure.

### Resolution dependence

For a smooth field, unscaled neighbor differences vary with particle spacing. A fixed index roll additionally corresponds to different physical offsets at different N. The original ratio is therefore not resolution-comparable without a better null and explicit scaling.

## Frozen refined diagnostics

Before the extension was run, Stage 02G froze a PCG64-permuted null with seed 20260207, relative neighbor variation, physical-gradient scaling, and Fourier direction consistency. The permuted-null ratios pass and the gradient-scale coefficient of variation passes. Direction consistency and strictly decreasing relative variation fail.

## Conclusion

The Stage 02F threshold and failure remain intact, but the cyclic-roll criterion is classified `NOT_SUITABLE_AS_STANDALONE_ATTRIBUTION_GATE`. This mathematical finding does not turn the resolution component into PASS: the independent refined checks still leave it diagnostic.

Evidence: `04_target_attribution/smoothness_audit/smoothness_criterion_audit.json`.
