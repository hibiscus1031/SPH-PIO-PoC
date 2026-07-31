# CPU/MPS backend microbenchmark

Source: `00_environment/benchmark_backend.py`; raw machine-readable results:
`backend_benchmark.csv`. The program ran 3 warm-up iterations and 8 separately
timed iterations per device, operation, and phase. MPS synchronization occurs
before and after each measurement; values are milliseconds and are descriptive,
not a claim based on a single run.

| Device | Operation | Phase | Mean ms | Median ms | Min–max ms |
|---|---|---:|---:|---:|---:|
| CPU | 1024×1024 matmul | forward | 2.205 | 2.183 | 2.072–2.410 |
| CPU | 1024×1024 matmul | backward | 6.497 | 6.469 | 6.223–6.817 |
| CPU | N=1024, K=32, C=32 neighbor aggregate | forward | 0.340 | 0.350 | 0.292–0.389 |
| CPU | N=1024, K=32, C=32 neighbor aggregate | backward | 0.989 | 0.967 | 0.926–1.074 |
| CPU | MultiheadAttention (B=8, L=64, E=64, H=4) | forward | 0.303 | 0.294 | 0.241–0.404 |
| CPU | MultiheadAttention (B=8, L=64, E=64, H=4) | backward | 0.690 | 0.681 | 0.646–0.759 |
| MPS | 1024×1024 matmul | forward | 1.285 | 1.204 | 1.141–1.849 |
| MPS | 1024×1024 matmul | backward | 3.601 | 3.380 | 3.262–4.486 |
| MPS | N=1024, K=32, C=32 neighbor aggregate | forward | 1.343 | 1.251 | 1.188–2.026 |
| MPS | N=1024, K=32, C=32 neighbor aggregate | backward | 1.391 | 1.279 | 1.232–1.821 |
| MPS | MultiheadAttention (B=8, L=64, E=64, H=4) | forward | 0.916 | 0.901 | 0.869–1.004 |
| MPS | MultiheadAttention (B=8, L=64, E=64, H=4) | backward | 1.558 | 1.379 | 1.349–2.826 |

At this small workload MPS was faster for matrix multiplication and its backward
pass, while CPU was faster for the simple gather/mean neighborhood aggregate and
the small attention workload. These are workload-specific results, so a later
solver phase should benchmark its real particle count and neighbor representation.
