# Dynamic state and graph

Stage 03B `DYNAMIC_REFERENCE_TRAJECTORY_QUALIFICATION_COMPLETE` is the sole authorization. CPU float64 was used; optimizer steps and training runs are both zero.

`x_unwrapped` is integrated and checkpointed; `x_wrapped=wrap(x_unwrapped)` is used only for graph/geometry/output. Pressure is recomputed from EOS at every stage. The graph uses deterministic reciprocal minimum-image edges, reverse maps, active-kernel and zero-weight-exterior flags, and hashes wrapped positions, smoothing lengths, edge list, and convention. Required independent graph sequences passed 48/48.
