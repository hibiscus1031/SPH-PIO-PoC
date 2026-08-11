# Uncertainty Floor and Identifiability Margin

Stage 05B shall construct an uncertainty acceleration field `a_unc` only from the already authorized TRAIN reference/semidiscrete uncertainty comparison, using matched lineages, variants, origins, nodes, and units. Freeze its scalar reduction as

```text
u_a = RMS_bal(a_unc),
```

using exactly the same nested family/variant/origin/node/component operator as `s_a`.

Before target decode, Stage 05B must preregister numeric finite/positivity tolerances, a conservative-coverage gate, and a minimum distinguishability margin expressed through `s_a / u_a` with explicit zero-uncertainty handling. If `s_a` is nonfinite, nonpositive, dominated by the frozen numerical floor, or lacks the frozen margin over `u_a`, Stage 05B is NOT_QUALIFIED.

`u_a` is a qualification comparator, not a replacement for `s_a` and not a dynamic loss denominator. No observed result may be used to revise the gate.
