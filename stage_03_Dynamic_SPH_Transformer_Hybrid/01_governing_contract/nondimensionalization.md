# Nondimensionalization contract

Frozen reference scales are domain length `L`, sound speed `cs`, reference density `rho0`, pair-force scale `F0_ij=sqrt(m_i m_j)cs^2/L`, time scale `T0=L/cs`, and acceleration scale `A0=cs^2/L`.

Legal dimensionless node quantities include `(rho-rho0)/rho0`, `p/(rho0 cs^2)`, mass divided by a train-only frozen mass scale, smoothing length divided by `L` (or a preregistered train-only scale), neighbor count under a frozen transform, dimensionless invariant kernel moments, and relative-velocity summaries divided by `cs`. Pair geometry uses `||r_ij||/ell_ij^sym`, minimum-image unit direction, and dimensionless relative velocities.

All normalization statistics in learned arms must be fit on training lineages only, frozen before validation/test access, stored with units/scales/dtype, and reused unchanged for D1–D3. D0 has no learned normalization. Reference/validation/test families cannot contribute statistics. Numerical constants such as `epsilon_r` and coefficient bounds must be preregistered before Stage 03 model/data access.
