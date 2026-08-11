# Rollout-horizon plan

The only authorized future progression is K=1, then K=2, then K=4, then K=8. Each transition requires the prior level to satisfy frozen numerical safety, train-family fitting, family-isolated validation, conservation, causal/self-feed, and evidence-completeness gates defined in Stage 03F. No horizon may be chosen adaptively from observed success.

All horizons share the same split/seal, normalization, model class, pair head, integrator, and training-budget policy. A longer horizon may use a preregistered continuation rule only if Stage 03F freezes it before K=1 results; failed checkpoints cannot be silently replaced or excluded.

K=8 success remains short-rollout fitting, not autonomous validation. Long autonomous rollout belongs to Stage 03H/D5 after sealed short-horizon qualification. Stage 03A freezes this order and runs none of it.
