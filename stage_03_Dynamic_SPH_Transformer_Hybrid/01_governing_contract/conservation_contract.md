# Conservation contract

Every undirected edge is evaluated once and scattered as `+f_ij` to `i` and `-f_ij` to `j`. Consequently `sum_i m_i a_theta,i=0` algebraically, subject only to floating-point reduction. The normalized residual is

`R_P = ||sum_i m_i a_theta,i|| / (sum_edges ||f_theta,ij|| + epsilon_F)`

and must be `<=1e-10` at every RK2 stage and accepted step for D1, D2, and D3. Zero-force cases are additionally checked with an absolute residual tolerance specified before execution.

Reports must distinguish learned correction-force conservation, baseline SPH conservation, and total hybrid conservation. Total correction impulse accumulated across steps must remain at roundoff scale. No penalty, mean removal, or projection may enforce the gate.

For a central-only arm (`beta=0`), angular momentum is a hard audit. For the general radial-plus-transverse force basis, torque, energy, and power remain diagnostics and cannot be described as conserved by this contract.
