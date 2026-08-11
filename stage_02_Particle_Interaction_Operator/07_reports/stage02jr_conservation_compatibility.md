# Stage 02J-R Conservation Compatibility

Pair-only conservation was audited for all 15 target candidates despite their retained attribution failure.

| family | max normalized total-force residual | max general-pair projection residual | max central diagnostic residual | family result |
|---|---:|---:|---:|---|
| CROSSMODE_A | 5.66e-16 | 5.71e-14 | 2.49e-14 | 5/5 PASS |
| DIAGONAL_B | 1.62e-16 | 5.70e-14 | 6.37e-14 | 5/5 PASS |
| MIXED_C | 5.77e-17 | 2.07e-14 | 4.88e-14 | 5/5 PASS |

All total-force and general antisymmetric incidence residuals are below `1e-10`. Incidence rank, null-space dimension, LSQR residual, and iterations are retained per case. Central-pair results and wrapped-domain torque are diagnostic only.

No target mean subtraction, conservation projection writeback, node head, hybrid architecture, or failed-case deletion was used. Conservation PASS does not override the independent six-component attribution failure.

