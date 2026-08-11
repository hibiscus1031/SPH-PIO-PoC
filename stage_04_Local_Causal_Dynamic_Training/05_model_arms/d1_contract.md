# D1 contract — Instantaneous Conservative Pair MLP

Identifier: `INSTANTANEOUS_CONSERVATIVE_PAIR_MLP`.

D1 is the instantaneous conservative baseline. It uses the common legal token schema at the current accepted state, a token encoder, an MLP-style pair coefficient mapping, and the common reciprocal antisymmetric pair-force head. It has no recurrent or attention-based temporal mechanism and must not be supplemented with privileged history summaries unavailable to the other arms.

D1 is freshly initialized and cannot load Stage 02/03 weights. Its hard-gated optimizer variables are the token encoder and pair coefficient-head parameters. It uses the same trajectory split, `L_state`, optimizer budget, and checkpoint rule as D2/D3.

D1 tests whether instantaneous local information is sufficient under the new task. It is not a deliberately weakened straw baseline and no ranking relative to D2/D3 is assumed.
