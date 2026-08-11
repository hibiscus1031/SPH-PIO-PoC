# Stage 04C Central Finite Difference

Each of 864 probes used the frozen epsilon ladder `[1e-2, 3e-3, 1e-3, 3e-4, 1e-4]` with `epsilon_actual = epsilon × max(1, group_RMS)`. Every plus/minus path was repeated twice from fresh state/history, for 17280 paths.

- Topology-changing epsilon rows: 0
- Deterministic-probe failures: 0
- Parameter mutations: 0
- Density/finite safety completion: PASS

All central-FD estimates were absolutely stable for near-zero classification; none can substitute for the contract's required nonzero component window.
