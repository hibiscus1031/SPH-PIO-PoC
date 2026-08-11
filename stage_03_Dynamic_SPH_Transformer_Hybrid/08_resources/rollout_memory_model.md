# Rollout memory model

Let `K` be unrolled accepted steps, `E_s` the edge count at RK stage `s`, `d<=32` hidden width, `H=4` history, `N` particles, `B` bytes/scalar, and `c_a` an implementation-dependent saved-activation factor. Two RHS evaluations per RK2 step give a leading saved-activation estimate

`M_act ~= c_a B sum_{k=1}^K sum_{s in {start,mid}} E_{k,s} d = O(K E d)`.

Graph storage is approximately `M_graph ~= sum_{k,s}[2 E_{k,s} B_index + E_{k,s} c_g B]` for endpoints plus saved geometric scalars; node/history state is `O(KNd + HNd)` if fully saved. Backpropagation time is `O(K E d)` times block/head constants and normally several forward costs. Parameter/gradient/optimizer storage is `O(P)` but optimizer multipliers must be stated; Stage 03A has no optimizer.

Truncated BPTT bounds retained `K`; activation checkpointing trades activation memory for recomputation and must not alter graph/history semantics. Before execution, calibrate `c_a,c_g,E/N`, allocator overhead, peak RSS/VRAM, and safety margin on a preflight; do not infer capacity from tensor payload alone.
