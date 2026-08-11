# Stage 03D-S — Gradient failure boundary

## Layered verdict

1. Implementation: **verified** (Stage 03C).
2. One-step autograd plumbing: **verified**, 6/6.
3. Multistep evidence: **partial**, 216/360 probes with stable windows.
4. Complete multistep gradient qualification: **failed**, 144/360 failures and history gate 0/6.
5. Failure attribution: **mixed or unresolved**, not a verdict replacement.
6. Dynamic training: **not authorized / not executed**.
7. Rollout performance: **not tested**.

| Primary failure reason | Count |
|---|---:|
| `AD_FD_DIRECTION_OR_SIGN_MISMATCH` | 5 |
| `DERIVATIVE_NEAR_STRUCTURAL_ZERO` | 29 |
| `FD_NONMONOTONE_NO_ADJACENT_WINDOW` | 69 |
| `FD_ROUNDOFF_DOMINATED` | 3 |
| `FD_TRUNCATION_DOMINATED` | 3 |
| `NUMERICAL_NONSMOOTHNESS_WITH_FIXED_GRAPH` | 16 |
| `UNRESOLVED` | 19 |

Same-math reverse/JVP passed 60/60. Extended FD produced 30/60 stable selected paths across 2640 evaluations. History traces separated stable temporal-module paths from rollout attenuation: one path was FD-conditioning-limited and five fell below FD resolution. All 90 horizon diagnostics were bounded or nonmonotone, so systematic vanishing/exploding was not detected; this does not qualify trainability.
