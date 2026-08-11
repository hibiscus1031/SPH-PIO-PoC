# Stage 03A temporal architecture report

Tokens contain legal current-state scalar features, invariant local graph summaries, relative-velocity invariants, and only relative time offsets `0,-1,-2,-3`. Absolute position is restricted to minimum-image geometry; absolute velocity, `a_SPH`, targets/references, future states, absolute step/time, identities/lineage/split roles, and target proxies are forbidden.

D3 is `CAUSAL_TEMPORAL_RECIPROCAL_TRANSFORMER_PIO`: H=4, scalar width `<=32`, two temporal blocks, heads `<=4`, causal mask required, parameters `<=150000`. Each particle's temporal sequence uses shared parameters; hidden channels are O(2) scalars. Dense global `N x N` attention and arbitrary vector output are forbidden.

The pair head consumes exchange-symmetric hidden combinations (`sum`, absolute difference, product) and legal symmetric pair features. Bounded tanh coefficients multiply the radial/transverse basis, enforcing `f_ji=-f_ij`.

The comparison matrix is D0 baseline WCSPH, D1 instantaneous conservative pair MLP, D2 causal recurrent pair PIO, and D3 causal Transformer. D1–D3 are freshly initialized, share input/head/data/loss/budget boundaries, and receive no Stage 02 weights. D2 and D3 are parameter-scale matched later. D3 superiority is not assumed. Stage 03A implements none of these arms.
