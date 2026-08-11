# Optimizer boundary

Stage 04A instantiates no optimizer and performs zero optimizer steps. Formal optimizer family, hyperparameters, schedule, batch/origin sampling, gradient accumulation/clipping, stopping behavior, seed count, and failure recovery must be prospectively frozen in Stage 04D after 04B/04C and before any Stage 04E training outcome.

Only the hard-gated network parameter groups listed for D1/D2/D3 may be updated. Initial velocity, initial density, reference prehistory/current states, graphs, targets, normalization constants, and solver constants are not optimizer variables. Frozen variables must be programmatically excluded and audited.

The optimizer budget and its accounting unit must be identical across arms. No arm receives extra steps, reseeds, or hyperparameter search because of observed performance. Resource-smoke activity is separate, cannot update a formal checkpoint, and cannot count as training qualification.

Loss weights and normalization are not optimizer-adjustable quantities unless explicitly preregistered as fixed before training; validation-, test-, and D-R3-derived adaptation is prohibited.
