# D2 contract — Causal Recurrent Pair PIO

Identifier: `CAUSAL_RECURRENT_PAIR_PIO`.

D2 is the recurrent temporal comparator. It uses the same legal accepted-state token fields as D1/D3 and processes the causal `H=4` history with a GRU-based temporal mechanism before the common reciprocal antisymmetric pair-force head. No future or reference-midpoint token is accessible.

D2 is freshly initialized and cannot load Stage 02/03 weights. Its hard-gated optimizer variables are the token encoder, GRU parameters, and pair head. Hidden-state initialization/reset semantics must be prospectively fixed in Stage 04D and shared across every trajectory origin according to one deterministic rule.

D2 uses the same split, state loss, optimizer budget, and checkpoint rule as D1/D3. It represents a causal-memory baseline; no superiority or inferiority relative to the Transformer arm is assumed.
