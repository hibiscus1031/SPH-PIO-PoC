# Stage 04C-R Resource Audit

| Metric | Value |
|---|---|
| Wall seconds | 134.853 |
| Peak RSS bytes | 526827520 |
| Peak RSS delta GiB | 0.187 |
| New TRAIN array decodes | 24 |
| Parameter mutations | 0 |
| Full-gradient repeat failures | 0 |

Resource verdict: PASS. Peak RSS delta is below 1.5 GiB; no retained-autograd monotonic growth, dense particle N×N allocation, mutation, or non-finite completion was observed. START/END allowlist denials passed; validation/sealed decode counts remain 0/0/0/0.
