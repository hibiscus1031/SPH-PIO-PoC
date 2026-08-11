# Baseline-arm contract

| Arm | Role | Temporal mechanism | Pair-force head | Initialization |
|---|---|---|---|---|
| D0 `BASELINE_WCSPH` | zero-correction and cost baseline | none | none; correction disabled | not applicable |
| D1 `INSTANTANEOUS_CONSERVATIVE_PAIR_MLP` | test whether memory is needed | none/current token only | same antisymmetric basis | fresh random initialization |
| D2 `CAUSAL_RECURRENT_PAIR_PIO` | non-attention temporal baseline | shared causal recurrent state | same antisymmetric basis | fresh random initialization |
| D3 `CAUSAL_TEMPORAL_RECIPROCAL_TRANSFORMER_PIO` | main temporal-attention candidate | H=4 causal Transformer | same antisymmetric basis | fresh random initialization |

D1–D3 use the same legal input boundary, pair-force basis, trajectory collection and splits, normalization policy, rollout losses, horizon ladder, and training budget. D2 and D3 parameter counts must be of the same order; exact matching rule is deferred to Stage 03F preregistration. No Stage 02 checkpoint or optimizer state may initialize any arm. No hypothesis presumes D3 superiority.

All learned arms share the per-stage conservation threshold `<=1e-10`. D0 supplies the zero-fallback reference and cost floor. Stage 03A freezes roles only and implements/trains none of them.
