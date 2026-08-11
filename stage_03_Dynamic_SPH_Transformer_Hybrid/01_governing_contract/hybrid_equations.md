# Hybrid equations

The Stage 03 v0.1 semidiscrete system is

`dx_i/dt = v_i`,

`d rho_i/dt = C_SPH,i(S)`,

`d v_i/dt = a_SPH,i(S) + a_theta,i(S_history,H_history,G_history)`.

The EOS is `p_i = cs^2 (rho_i-rho0)`. Baseline WCSPH uniquely supplies `C_SPH`, `a_SPH`, EOS, smoothing-length policy, graph construction, and time-step selection. The network term is an additive correction, never a replacement for the complete acceleration.

At instant `n`,

`a_theta,i^n = (1/m_i) sum_{j:{i,j} in G^n} f_theta,ij^n`,

`F0_ij = sqrt(m_i m_j) cs^2/L`, `rhat_ij=r_ij/(||r_ij||+epsilon_r)`, `dv_ij=(v_j-v_i)/cs`, and `t_ij=dv_ij-(dv_ij·rhat_ij)rhat_ij`. The minimum-image displacement convention is `r_ij=x_j-x_i`; therefore `rhat_ji=-rhat_ij`, `dv_ji=-dv_ij`, and `t_ji=-t_ij` away from a deterministic minimum-image tie.

The learned pair force is

`f_theta,ij = F0_ij [alpha_ij rhat_ij + beta_ij t_ij]`,

with symmetric bounded scalars `alpha_ij=alpha_ji` and `beta_ij=beta_ji`, giving `f_theta,ji=-f_theta,ij` by construction.
