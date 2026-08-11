# Coordinate/Block Finite-Difference Contract

For every optimizer parameter group, Stage 05C must preregister:

- hash-selected scalar coordinates;
- hash-selected compact contiguous or structurally defined blocks;
- a symmetric perturbation convention;
- an epsilon ladder in parameter-native units;
- the rule for identifying stable finite-difference windows;
- reverse/FD agreement tolerances and minimum coverage.

The central estimate is

```text
D_FD(epsilon; d) = [L_def(theta + epsilon d) - L_def(theta - epsilon d)] / (2 epsilon).
```

All perturbed evaluations are temporary and must pass finite, structure, topology, and safety checks. Coordinate/block selections and epsilon ladders may not change after results are seen. Failure to find the preregistered stable-window coverage is NOT_QUALIFIED, not grounds for cherry-picking.
