# Stage 01H support sensitivity

| run_id | N | H_over_dx | decay_rate_relative_error | velocity_relative_l2 | nu_eff | relative_viscosity_bias |
|---|---|---|---|---|---|---|
| g_shear_n24 | 24 | 4.5 | 0.0716759129739 | 0.0113824473478 | 0.0185664817405 | -0.0716759129739 |
| g_shear_n32 | 32 | 5.0495097568 | 0.0516005938778 | 0.0081815111865 | 0.0189679881224 | -0.0516005938778 |
| g_shear_n48 | 48 | 5.5 | 0.0279495032685 | 0.00442336596449 | 0.0194410099346 | -0.0279495032685 |

Decay, velocity, position, and effective-viscosity errors all improve along N24/N32/N48. However, N and `H/dx` change together, so the frozen evidence cannot isolate resolution from support quadrature at fixed N. This prevents a claim of `SUPPORT_PATH_DOMINANT`; the evidence supports a finite-resolution spatial path with support confounding.
