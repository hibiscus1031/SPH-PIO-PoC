# Stage 01H effective viscosity

The fitted law is `u_num=A exp(-lambda_num t)`, with `nu_eff=lambda_num/k_s^2` and `k_s=2*pi`.

| run_id | N | H_over_dx | lambda_num | nu_eff | relative_viscosity_bias | lambda_fit_standard_error | r_squared |
|---|---|---|---|---|---|---|---|
| g_shear_n24 | 24 | 4.5 | 0.732975319596 | 0.0185664817405 | -0.0716759129739 | 6.36302938021e-06 | 0.999999999699 |
| g_shear_n32 | 32 | 5.0495097568 | 0.748826156212 | 0.0189679881224 | -0.0516005938778 | 8.98417798977e-07 | 0.999999999994 |
| g_shear_n48 | 48 | 5.5 | 0.76750030885 | 0.0194410099346 | -0.0279495032685 | 6.1642684561e-07 | 0.999999999997 |

All three effective viscosities are biased low: numerical decay is too slow. The bias magnitude decreases monotonically from `7.167591%` at N24 to `2.794950%` at N48. Thus `nu_eff` converges toward `0.02` along the registered N/H support path.
