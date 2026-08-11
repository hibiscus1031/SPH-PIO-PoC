# External-Source Cancellation

The D0 and hybrid transitions use the identical accepted origin, external source, graph convention, EOS, time step, boundary convention, and RK2 semantics. Baseline centering subtracts two complete accepted-state transitions:

```text
Delta_v_eff^theta = v_theta^(n+1) - v_0^(n+1).
```

Thus common prescribed external-source contributions are intended to cancel at the discrete-transition level; the learned term is not asked to rediscover them. This is a contract identity, not a measured cancellation claim. Stage 05B must audit equality of the paired metadata and treat any mismatch as NOT_QUALIFIED rather than correcting it post hoc.
