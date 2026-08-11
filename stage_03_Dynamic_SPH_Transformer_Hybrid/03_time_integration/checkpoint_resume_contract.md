# Checkpoint/resume contract

A dynamic checkpoint is an accepted-step snapshot only. It must contain accepted `S^n`, canonical committed history `H/history`, model/arm identifier and parameter hash, normalization hash, integrator and EOS configuration hashes, step/time/dt, graph-building configuration, trajectory lineage, and deterministic RNG/backend state. It must not contain a provisional midpoint as committed state.

Resume rebuilds `G^n` from the stored accepted state and verifies its hash or an explicitly defined equivalent canonical graph before advancing. A continuous run and resume run must match graph sequence, history hashes, failure flags, and states bitwise or within the same preregistered strict fallback envelope used by zero-equivalence testing.

Stage 02 checkpoints are outside this schema: they remain `historical_static_diagnostic_only`, are never copied into Stage 03, and have `dynamic_initialization_permitted=false`.
