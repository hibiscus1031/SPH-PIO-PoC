# Stage 02K — Architecture design

The authoritative architecture-design file is `06_model/pair_force_pio_architecture_v0_1/contracts/architecture_contract_v0_1.json`; it and the implementation source were frozen and hashed before any canonical target array was decoded. This Markdown file is a read-only report rendering of that prefrozen design, not a post-result design revision.

`K0` is a central pair-MLP diagnostic (`beta=0`). `K1` is the mandatory non-attention symmetric pair-MLP baseline. `K2` uses two scalar reciprocal-attention blocks, hidden dimension 32 and four heads; logits and normalization are symmetric and edge-local. `KNEG` is an ineligible directed-softmax control.

All eligible outputs use `F0=sqrt(m_i m_j) cs^2/L`, bounded dimensionless `alpha=tanh(alpha_raw)` and `beta=tanh(beta_raw)`, and `f_ij=F0(alpha rhat + beta transverse)`. One unordered-pair evaluation and signed incidence aggregation hard-enforce antisymmetry.
