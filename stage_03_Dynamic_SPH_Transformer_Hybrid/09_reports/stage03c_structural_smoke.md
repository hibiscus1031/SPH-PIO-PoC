# Fixed-weight structural smoke

Stage 03B `DYNAMIC_REFERENCE_TRAJECTORY_QUALIFICATION_COMPLETE` is the sole authorization. CPU float64 was used; optimizer steps and training runs are both zero.

With seeds 20300301/2/3 and no training, D1/D2/D3 were checked at start and midpoint of one RK2 step for all 12 cases. Pair exchange, force antisymmetry, normalized force residual <=1e-10, permutation, edge reorder, translation, Galilean boost, SO(2), reflection, periodic representative shift, finiteness and repeatability passed 72/72 stage audits. No prediction error or reference improvement was evaluated.
