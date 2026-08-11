# Prohibited Scaling

The following are prohibited throughout the first Stage 05 route:

- per-model, per-arm, per-seed, per-family, per-origin, per-node, or per-axis training scales;
- validation-, sealed-test-, D-R3-, model-output-, gradient-, or training-result-derived scale selection;
- changing `s_a` after model prediction, model instantiation, or training starts;
- batchwise, epochwise, moving-average, curriculum-dependent, or dynamic loss normalization;
- target rescaling chosen after inspecting predictions;
- replacing a failed lineage or family to obtain a more favorable scale;
- using `u_a` as a hidden adaptive denominator.

Any violation invalidates comparability and blocks authorization rather than triggering a repair within the same contract.
