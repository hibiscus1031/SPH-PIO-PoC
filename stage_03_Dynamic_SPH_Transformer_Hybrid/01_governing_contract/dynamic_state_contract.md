# Dynamic state contract

At accepted physical instant `n`, the particle state is

`S^n = {x_i^n, v_i^n, rho_i^n, p_i^n, m_i, ell_i, G^n}_{i=1}^N`,

where `x` is periodic position, `v` velocity, `rho` density, `p` EOS-derived pressure, `m` fixed mass, `ell` smoothing length, and `G^n` the reciprocal minimum-image graph rebuilt from the current state. The prompt's smoothing-length symbol `h_i` is serialized as `smoothing_length` and denoted `ell_i` here to prevent collision with temporal hidden state.

The separate temporal state is `H^n={q_i^n}_{i=1}^N`, serialized as `temporal_hidden`. This is the unique canonical meaning of network hidden state; the prompt alias `{h_i^n}` is non-canonical notation only. A history cache contains accepted tokens/states at relative offsets `0,-1,-2,-3` with lineage and time metadata but no target content.

Forbidden state inputs are reference or future state, target correction, family role, split label, and any derived proxy for them. Pressure is never an independent evolved degree of freedom: `p_i=cs^2(rho_i-rho0)` is recomputed by the frozen EOS.

Particle persistence must be explicit. Because Stage 03 v0.1 does not permit particle birth/death, `N`, mass ordering, and persistent particle identity are invariant within a trajectory. Identity is used only to align a particle's own causal history; it is not an embedding or learnable feature.
