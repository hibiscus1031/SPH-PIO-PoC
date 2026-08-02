# Stage 01F3B MMS-B increasing-neighbor space matrix

The formal path and frozen timestep match the MMS-A space matrix. Independent DOP853 labeled-particle references include tighter sensitivity bounds.

| N | position L2 | velocity L2 | density L2 | pressure L2 | edge count | topology events | peak RSS |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 8.6278e-5 | 6.8254e-3 | 4.1635e-4 | 1.6654e-1 | 12,832 | 432 | 270 MB |
| 24 | 4.8409e-5 | 3.6883e-3 | 2.1190e-4 | 8.4761e-2 | 38,192 | 776 | 327 MB |
| 32 | 3.4626e-5 | 2.5997e-3 | 1.1722e-4 | 4.6888e-2 | 82,912 | 2,848 | 426 MB |
| 48 | 1.8437e-5 | 1.3597e-3 | 6.4220e-5 | 2.5688e-2 | 219,904 | 1,792 | 601 MB |

All four primary errors decrease at every level. Global slopes are position `1.389`, velocity `1.452`, density `1.724`, and pressure `1.724`. B-S1–B-S6: **PASS**. All dynamic topology changes were reciprocal and every structural-defect audit was zero; event count is not required to be monotone and identity count greater than one is not a failure.

Full endpoint norms:

| N | pos L1 | pos L2 | pos Linf | vel L1 | vel L2 | vel Linf | rho L1 | rho L2 | rho Linf | p L1 | p L2 | p Linf |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 8.2757e-5 | 8.6278e-5 | 1.1791e-4 | 6.5465e-3 | 6.8254e-3 | 9.3360e-3 | 3.7727e-4 | 4.1635e-4 | 7.0362e-4 | 1.5091e-1 | 1.6654e-1 | 2.8145e-1 |
| 24 | 4.6396e-5 | 4.8409e-5 | 6.7495e-5 | 3.5348e-3 | 3.6883e-3 | 5.1418e-3 | 1.8366e-4 | 2.1190e-4 | 3.9252e-4 | 7.3466e-2 | 8.4761e-2 | 1.5701e-1 |
| 32 | 3.3179e-5 | 3.4626e-5 | 4.8597e-5 | 2.4910e-3 | 2.5997e-3 | 3.6482e-3 | 9.8158e-5 | 1.1722e-4 | 2.4260e-4 | 3.9263e-2 | 4.6888e-2 | 9.7041e-2 |
| 48 | 1.7665e-5 | 1.8437e-5 | 2.5996e-5 | 1.3027e-3 | 1.3597e-3 | 1.9170e-3 | 5.3703e-5 | 6.4220e-5 | 1.3409e-4 | 2.1481e-2 | 2.5688e-2 | 5.3637e-2 |

N16/24/32/48 runtimes were `6.64/14.92/26.23/56.73 s`. N48 field-at-numerical-position velocity/density/pressure L2 errors were `1.3585e-3`, `6.4148e-5`, and `2.5659e-2`. Reference sensitivity bounds and initial/endpoint density errors are retained per resolution.
