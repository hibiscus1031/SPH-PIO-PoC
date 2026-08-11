# History commit contract

History mutation is transactional. Start and midpoint evaluations read a snapshot of the committed cache. They may create temporary tokens/hidden values but may not append, evict, or overwrite accepted history.

After `S^{n+1}` passes all safety checks, the solver constructs exactly one accepted token at physical time `t_{n+1}` and commits it atomically; the cache then retains the newest four accepted instants. If a step fails or is rejected, both state and cache remain at `n`. The midpoint token never survives the step and never counts as a second physical time.

Warm-start entries are three preceding reference states and are explicitly labeled. After rollout origin, committed entries are derived only from self-fed predicted accepted states. Checkpoint/resume must reproduce cache content/order/hashes exactly. Tests must detect double commits, midpoint contamination, missing commits, off-by-one relative-time offsets, and rollback failure.
