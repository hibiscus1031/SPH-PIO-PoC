# Deterministic execution contract

Formal Stage 04C probes must be reproducible under fixed CPU float64 execution. Each run must record random seeds, model initialization identifier, sample/origin identifier, parameter-group direction, graph/tie-breaking policy, thread settings, framework/version, and math-SDPA backend identity.

The same base state, accepted history, graph construction rules, parameter vector, probe direction, and loss aggregation must be reused across reverse VJP, forward JVP, and all finite-difference epsilons. Stochastic layers must be disabled or have their randomness frozen identically. No data shuffle, augmentation, dropout mask change, or parameter mutation may occur inside a derivative comparison.

Every formal probe requires a deterministic repeat performed as an independent re-execution. Repeat equality/tolerance rules must be preregistered in Stage 04C before results are examined. Nonrepeatability invalidates the affected hard evidence; it cannot be averaged away.

Formal artifacts must include an input hash, environment/backend identity, ordered parameter-group specification, direction hash, epsilon list, raw scalar loss/derivative values, and result hash. Checkpoints and manifests must bind the same backend identity. Stage 04A creates none of these run artifacts.
