# Temporal Transformer contract

The main candidate is `D3 — CAUSAL_TEMPORAL_RECIPROCAL_TRANSFORMER_PIO`. Shared parameters process each persistent particle's four-token causal sequence. Frozen initial bounds are history length 4, scalar hidden width at most 32, exactly two temporal blocks, at most four attention heads, required causal mask, and total parameter count at most 150,000.

All hidden channels transform as O(2) scalars. The temporal module emits the canonical scalar hidden vector `q_i^n`; it cannot directly emit an arbitrary world-coordinate vector. Relative-time encodings are functions only of offsets from the evaluation time, not absolute time or step index.

Spatial interaction remains local to reciprocal graph edges. Global dense `N x N` temporal-spatial attention is forbidden. Temporal attention is along the length-four history for each particle; any graph aggregation used in token construction or a later frozen spatial block must scale locally with edges.

The causal mask must be structurally audited by perturbing forbidden future slots and obtaining exact invariance of current outputs. D3 is a candidate, not a presumed winner; all performance comparisons await later stages.
