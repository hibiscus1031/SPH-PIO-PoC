# Reverse/JVP Contract

Stage 05C shall run in deterministic CPU `float64` with `SDPBackend.MATH`. For preregistered compact parameter blocks and deterministic hash-derived directions `d`, compare

```text
D_reverse = <grad_theta L_def, d>
D_jvp     = JVP_theta[L_def](d).
```

Each direction, block, seed string, normalization rule, comparison tolerance, and required coverage must be frozen before execution. Both values must be finite and agree under the preregistered absolute-plus-relative rule. Directions may not be replaced, resampled, or renormalized after observing a result.

Reverse/JVP agreement supports derivative consistency; it is not alone sufficient for trainability and must be combined with full-gradient, coordinate/block FD, and local-descent evidence.
