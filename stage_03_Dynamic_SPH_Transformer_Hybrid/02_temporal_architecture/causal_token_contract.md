# Causal token contract

For particle `i` at evaluation time `n`, `z_i^n` contains only legal current-state scalars, invariant local graph summaries, and relative-time encoding. Allowed channels are normalized density deviation, normalized EOS pressure, normalized mass, normalized smoothing length, neighbor count, kernel-weighted invariant neighborhood moments, relative-velocity invariant summaries, and other quantities proven to derive only from the current SPH state without exposing `a_SPH` or a target.

Absolute position is used solely to form deterministic periodic minimum-image relative geometry. Absolute velocity is forbidden as a node feature; only relative-velocity invariants are legal. Reference acceleration, correction labels, future state, target-derived channels, family/split/test role, absolute step index, particle-ID embedding, family embedding, and absolute-time embedding are forbidden.

The temporal window uses accepted relative offsets `0,-1,-2,-3` and a causal mask. At a provisional RK2 midpoint, the current slot is replaced by an ephemeral midpoint token while older slots remain the accepted history; the midpoint token cannot be committed. Warm-start padding/masking semantics and relative physical time offsets must be frozen before trajectory construction.

Every materialized token schema must carry feature name, source expression, units, normalization key, temporal offset, legality decision, and provenance hash. A feature absent from the frozen schema is forbidden by default.
