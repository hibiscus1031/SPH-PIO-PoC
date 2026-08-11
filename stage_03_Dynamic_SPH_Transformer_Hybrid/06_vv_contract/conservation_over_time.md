# Conservation over time

For D1–D3, report `sum_i m_i a_theta,i` and normalized residual at both RK2 RHS stages and each accepted step. The universal hard threshold is `<=1e-10`. Store numerator, denominator, absolute residual for zero-force cases, edge count, state/graph hash, arm, dtype, and deterministic reduction policy.

Accumulate the hybrid correction impulse with the RK2 quadrature actually used and verify that it remains at roundoff scale over 1/2/4/8 and autonomous horizons. Separately report correction-force, baseline-SPH, and total-hybrid momentum balances; one cannot compensate for another in the correction gate.

Central-only force arms receive a hard angular-momentum audit. General transverse-force arms report torque, energy, and power diagnostically only. No conservation penalty or projection is authorized.
