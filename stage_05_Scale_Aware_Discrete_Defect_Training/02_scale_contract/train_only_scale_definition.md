# TRAIN-Only Scale Definition

Let `F_train` be the six immutable TRAIN lineages. For family `f`, let `V_f` be its retained variants, `O_fv` its eligible origins, `N_fvo` the nodes at an origin, and `d` the spatial dimension. Freeze

```text
RMS_bal(a)^2 =
  (1 / |F_train|) sum_f
  (1 / |V_f|)     sum_v
  (1 / |O_fv|)    sum_o
  (1 / N_fvo)     sum_i
  (1 / d) ||a_fvoi||_2^2

s_a = sqrt(RMS_bal(a_cons^star)^2).
```

This nested mean gives every TRAIN family, then variant, then origin equal weight, while nodes are equally weighted within an origin. Empty levels are inadmissible, not silently skipped. `s_a` must be finite, strictly positive, scalar, and computed once from qualified TRAIN targets. Its numerical value is frozen after Stage 05B and before any model instantiation.

No validation, sealed test, D-R3, model output, gradient, or training result may enter the definition.
