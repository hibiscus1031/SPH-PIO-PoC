# Execution-budget policy

Stage 03A authorizes no numerical execution. Later stages must preregister per-arm family count, seeds, optimizer steps (when authorized), wall-clock/VRAM ceilings, precision, retry policy, early stopping, checkpoint cadence, and failure retention before outcomes.

D1–D3 receive the same training-data access, horizon schedule, loss, selection rule, and compute budget; D2/D3 parameter scale matching is frozen in Stage 03F. Budget exhaustion is a terminal recorded outcome, not permission for selective retries. Debug/preflight runs and formal runs use separate IDs and cannot be promoted retrospectively.

Cost claims occur only at D8 using equal-error comparisons and include graph building, temporal inference, RK2 stages, memory, I/O, and reference uncertainty. Raw speedup at unequal error is not a utility claim.
