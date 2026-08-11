# Stage 02J-S Invariance Audit

The development audit covered amplitude scales 0.1/1/10, periodic translation, x/y exchange, 90-degree vector rotation, reverse-then-recanonicalize particle order, and reversed edge direction.

- Development cases: 10.
- Transformation checks: 80.
- Failures: 0.
- Frozen tolerance: `1e-14 + 1e-12*abs(S_h)`; p-values required exact equality.
- Result: `PASS`.

This confirms the implemented statistic's requested invariances on the development scope only. It does not override the negative-control failure.
