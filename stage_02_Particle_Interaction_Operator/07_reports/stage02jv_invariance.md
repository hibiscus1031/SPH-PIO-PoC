# Stage 02J-V Invariance

The audit executed 192 transformations across six real targets and 18 learnable positive-control fields. Nine checks failed:

| Case | Population | Transformation | Failed quantity |
|---|---|---|---|
| i_res_n12_h26_regular | DIRECTION_ONLY_SMOOTH | amplitude_10 | p_mag only |
| i_anchor_n16_h26_regular | DIRECTION_ONLY_SMOOTH | amplitude_0.1 | p_mag only |
| i_anchor_n16_h26_regular | DIRECTION_ONLY_SMOOTH | amplitude_10 | p_mag only |
| i_res_n20_h26_regular | DIRECTION_ONLY_SMOOTH | amplitude_0.1 | p_mag only |
| i_res_n20_h26_regular | DIRECTION_ONLY_SMOOTH | amplitude_10 | p_mag only |
| crossmode_a_n12_h26 | DIRECTION_ONLY_SMOOTH | amplitude_0.1 | p_mag only |
| crossmode_a_n12_h26 | DIRECTION_ONLY_SMOOTH | amplitude_10 | p_mag only |
| crossmode_a_n20_h26 | DIRECTION_ONLY_SMOOTH | amplitude_0.1 | p_mag only |
| crossmode_a_n20_h26 | DIRECTION_ONLY_SMOOTH | amplitude_10 | p_mag only |

Every failure is confined to exact `p_mag` equality for DIRECTION_ONLY_SMOOTH under amplitude scaling. The theoretical magnitude component is zero, but float64 magnitude spans of order `1e-19`–`1e-16` changed permutation tie ranks. `M_h` remained within the frozen metric tolerance, while `D_h`, `p_dir`, and the decision statistic `p_any` remained invariant.

The contract nevertheless requires all five quantities to remain invariant. No unregistered zero threshold or tie rule was introduced, so the invariance gate is `FAIL` and is retained as a scientific qualification failure.
