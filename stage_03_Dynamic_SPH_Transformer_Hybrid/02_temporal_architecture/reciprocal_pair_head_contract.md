# Reciprocal pair-head contract

For every undirected reciprocal edge `{i,j}`, the coefficient head may consume only exchange-symmetric combinations: `q_i+q_j`, `abs(q_i-q_j)`, `q_i*q_j`, and legal symmetric pair scalars such as distance over symmetric smoothing length and even/invariant relative-velocity summaries.

Asymmetric concatenations such as `[q_i,q_j]` are forbidden. One coefficient evaluation is shared by both directions. Final coefficients are bounded outputs, e.g. `alpha_ij=alpha_max*tanh(u_alpha,ij)` and `beta_ij=beta_max*tanh(u_beta,ij)`, with positive finite bounds preregistered before training. Thus `alpha_ij=alpha_ji` and `beta_ij=beta_ji`.

The head combines coefficients only with the frozen radial/transverse geometric basis and `F0_ij`. It may not create node corrections, directed-normalized weights, unbounded coefficients, post hoc force projections, or target-conditioned features. Edge ordering and scatter order must be deterministic for equality/repeatability audits.
