# Normalization contract

All learned-input and loss scaling statistics are computed from training lineage components only, after the split is frozen and before validation/test access. Statistics are family-balanced so long trajectories, dense graphs, particles, or overlapping windows do not dominate implicitly.

The frozen normalization artifact records feature schema, estimator, weighting, units, center/scale, epsilon/clipping policy, training component IDs and hashes, dtype, and code/config provenance. D1–D3 reuse the identical artifact. Validation, sealed test, independent validation, Stage 01/02 data, and reference targets contribute no statistics.

Degenerate or non-finite scales are qualification failures requiring a preregistered handling rule; they cannot be patched after outcome inspection. Stage 03A selects no numerical statistics.
