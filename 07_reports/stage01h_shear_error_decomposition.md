# Stage 01H shear error decomposition

The operational additive identity uses N32 main-step error as `E_total`, the signed N32 main-minus-half difference as `E_time`, the signed N32-half-minus-N48 difference as `E_space`, and the unresolved N48 residual as `E_operator`.

| metric | E_total | E_time | E_space | E_operator | closure_defect | time_fraction_absolute |
|---|---|---|---|---|---|---|
| velocity_relative_l2 | 0.0081815111865 | 4.14076967159e-11 | 0.0037581451806 | 0.00442336596449 | 0 | 5.06113061169e-09 |
| position_relative_l2 | 0.00397753811374 | -2.5485925783e-10 | 0.00182581559601 | 0.00215172277259 | 0 | 6.40746236848e-08 |
| decay_rate_relative_error | 0.0516005938778 | 2.59700372318e-10 | 0.0236510903496 | 0.0279495032685 | 0 | 5.03289502701e-09 |
| amplitude_bias | 0.00818150111329 | 4.13564738011e-11 | 0.00375814107316 | 0.00442335999877 | 0 | 5.05487602195e-09 |

`E_operator` is an upper-bound residual label required by the decomposition; it is not evidence that operator form is defective. Closure is exact to floating-point precision. Time fractions are negligible, while the decrease from N32 to N48 dominates the observable improvement.
