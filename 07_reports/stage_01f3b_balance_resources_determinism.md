# Stage 01F3B balance, resources and determinism

Across 46 isolated child trajectories, every worker hard gate passed and every child was fully reclaimed. Parent summaries were scalar-only trees plus relative paths; all run IDs were new `f3b_` identifiers.

| Diagnostic | observed maximum | gate |
|---|---:|---:|
| pair-force residual | 3.561e-16 | 1e-12 |
| normalized internal-force residual | 2.284e-17 | 1e-10 |
| force assembly defect | 5.529e-16 | 1e-10 |
| momentum update defect | 2.084e-17 | 1e-10 |
| viscous power | -1.010e-11 | <=1e-12 positive tolerance |
| kinetic-energy update diagnostic | 1.036e-8 | reported, no preregistered hard gate |
| current/peak RSS | 607/607 MB | 2/4 GB |
| RSS Q4-Q1 absolute | 38.5 MB | 250 MB |
| RSS Q4/Q1 relative | 9.96% | 50% |
| step-time Q4/Q1 | 1.071 | 1.30 |

Minimum separation, source-call, finite state/RHS and topology structural gates also passed for every trajectory. Total momentum constancy was not imposed on these forced problems; internal/external/total-force assembly and midpoint momentum updates were audited instead.

Four required deterministic pairs passed bitwise identity for positions, unwrapped positions, velocities, densities, pressures, masses and edge hashes. Deterministic scalar summaries and topology event-sequence hashes were also identical; all repeat children were reclaimed.
