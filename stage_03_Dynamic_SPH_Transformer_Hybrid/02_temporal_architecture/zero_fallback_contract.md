# Zero-fallback contract

The future solver must expose `correction_enabled=false` and must also support an independently tested zero final-head configuration. Both imply `a_theta=0` without invoking temporal outputs in the baseline state update.

For every step, the hybrid-zero and baseline executions must use the same starting state, reciprocal graph construction and edge ordering, RK2 stage states, EOS, time step, safety checks, and accepted-state update. The target is bitwise equality of state and graph sequence. If the execution backend prevents bitwise equality, Stage 03C must preregister a componentwise strict floating-point envelope before examining results and record the precise cause.

Required checks cover one step, multiple steps, graph sequence, topology events, and checkpoint/resume. History evaluation or cache bookkeeping may occur only if it cannot affect D0 state, branching, graph, or arithmetic order; the preferred disabled path bypasses it. This is the first implementation hard gate and must pass before other hybrid evidence is interpreted.
