# Primary Defect Loss

The sole first-round formal objective is

```text
L_def = BAL_MEAN[
  ||(a_eff^theta - a_cons^star) / s_a||_2^2
],
```

where `BAL_MEAN` uses the same family → variant → origin → node nesting fixed for the scale, except that the vector squared norm is retained as written. All eligible D1/D2/D3 arms, seeds, and TRAIN origins use the same frozen `s_a` and target identities.

The computationally equivalent impulse expression is

```text
||(Delta_v_eff^theta - dt * a_cons^star) / (dt * s_a)||_2^2.
```

It does not create a second loss identity. The acceleration-defect form is canonical in all manifests and reports. No numerical value is evaluated in Stage 05A.
