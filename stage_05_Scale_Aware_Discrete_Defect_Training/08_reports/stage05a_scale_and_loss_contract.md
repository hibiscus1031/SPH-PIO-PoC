# Stage 05A Scale and Loss Contract Report

The single scale `s_a` is the square root of the nested family-, variant-, origin-, node-, and component-balanced mean square of TRAIN `a_cons^star`. It is scalar and orthogonally invariant. Only the six TRAIN lineages may contribute. Stage 05B freezes its numerical value, positivity/finite checks, uncertainty scale `u_a`, and distinguishability gate before any model exists.

The unique first-round objective is

```text
L_def = BAL_MEAN[||(a_eff^theta - a_cons^star)/s_a||_2^2].
```

The impulse implementation divided by `dt*s_a` is algebraically equivalent, not a second objective. Position, density, pressure, energy, and torque quantities are diagnostic only. Conservation, antisymmetry, and center projection receive no penalties because the common architecture hard-codes the representability boundary.

Per-arm/seed scale, validation/test-derived scale, prediction-dependent rescaling, and dynamic normalization are prohibited.
