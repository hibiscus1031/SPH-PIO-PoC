# D3 contract — Causal Temporal Reciprocal Transformer PIO

Identifier: `CAUSAL_TEMPORAL_RECIPROCAL_TRANSFORMER_PIO`.

D3 applies causal temporal attention to the same legal `H=4` accepted-state token interface and uses the common reciprocal antisymmetric pair-force head. Attention must not access future accepted states, reference midpoint data, or target-derived statistics.

D3 is freshly initialized and cannot load Stage 02/03 weights. Its hard-gated optimizer variables are the token encoder, attention Q/K/V/O parameters, feed-forward parameters, and pair head. Formal gradient qualification uses CPU float64 and explicitly fixed PyTorch `SDPBackend.MATH`; flash, memory-efficient, and automatic backend selection are disabled.

D3 uses the same complete-lineage split, `L_state`, optimizer budget, and checkpoint rule as D1/D2. Backend identity is embedded in checkpoints, run manifests, and result hashes. D3 is a hypothesis-bearing arm, not the presumed winner.
