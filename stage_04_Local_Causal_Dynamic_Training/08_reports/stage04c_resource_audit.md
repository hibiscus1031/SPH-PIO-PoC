# Stage 04C Resource Audit

| Metric | Value |
|---|---|
| Wall time (s) | 938.652 |
| Reverse time (s) | 87.820 |
| JVP time (s) | 87.008 |
| FD time (s) | 684.224 |
| FD paths | 17280 |
| Graph rebuild lower bound | 57024 |
| Peak RSS (bytes) | 527745024 |
| Peak RSS delta (GiB) | 0.233 |

Resource verdict: PASS. Peak RSS delta was below 1.5 GiB; no monotonic retained-autograd growth, parameter mutation, or dense particle N×N allocation was observed. Completion and required hashes were finite/complete.
