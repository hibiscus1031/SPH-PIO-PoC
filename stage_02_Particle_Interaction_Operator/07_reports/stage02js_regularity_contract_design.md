# Stage 02J-S Regularity Contract Design

## Version relationship

`attribution_contract_v0_1` remains a historical single-null diagnostic. `attribution_contract_v0_2` is a new prospective contract; it does not use the old 0.8 threshold.

## Dimensionless graph-Sobolev statistic

For active, nonzero-kernel, reciprocal undirected edges,

\[
S_h=\frac{\sqrt{\operatorname{mean}_{(i,j)}\left[\lVert\Delta a_i-\Delta a_j\rVert^2/((r_{ij}/h)^2+\epsilon_r)\right]}}{\operatorname{RMS}(\Delta a)+\epsilon_a}.
\]

The contract freezes `epsilon_r = 3.5527136788005009e-15` (16 binary64 epsilons) and `epsilon_a = 0`; a zero target is rejected separately. Computation uses CPU float64, one graph-balanced contribution per undirected edge, minimum-image distance, and deterministic canonical ordering.

Each case uses 256 unscreened PCG64 permutations with root seed `20260207`; case seeds are the first eight big-endian bytes of `SHA256(root_seed|case_id|index)`. The prospective gate is `p_smooth=(1+count(S_perm<=S_observed))/257 <= 0.01`. Resolution behavior additionally requires high-resolution `S_h` no greater than low-resolution `S_h`, nonpositive OLS slope against the three frozen levels, and continued PASS of the four historical non-PCG64 checks. No convergence order is inferred.

The immutable contract hash is `sha256:9f62279ed4061b88688a187365a523923c6898b969f6ecd77f2785ca0e55ae5f`.
