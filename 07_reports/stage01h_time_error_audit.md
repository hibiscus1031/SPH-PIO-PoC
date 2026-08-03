# Stage 01H time-error audit

| comparison | metric | absolute_difference | relative_change | status |
|---|---|---|---|---|
| N32_main_vs_dt_half | velocity_relative_l2 | 4.14076967159e-11 | 5.06113063731e-09 | SMALL |
| N48_vs_repeat | velocity_relative_l2 | 0 | 0 | BITWISE_IDENTICAL |
| N32_main_vs_dt_half | position_relative_l2 | 2.5485925783e-10 | 6.40746195792e-08 | SMALL |
| N48_vs_repeat | position_relative_l2 | 0 | 0 | BITWISE_IDENTICAL |
| N32_main_vs_dt_half | decay_rate_relative_error | 2.59700372318e-10 | 5.03289505234e-09 | SMALL |
| N48_vs_repeat | decay_rate_relative_error | 0 | 0 | BITWISE_IDENTICAL |
| N32_main_vs_dt_half | amplitude_bias | 4.13564738011e-11 | 5.0548760475e-09 | SMALL |
| N48_vs_repeat | amplitude_bias | 0 | 0 | BITWISE_IDENTICAL |

The maximum N32 dt-halving relative change is `6.40746195792e-08`, far below `0.10`. N48 and its registered repeat are identical for all audited metrics. Time integration contribution is therefore small, and determinism uncertainty is zero at the stored evidence precision.
