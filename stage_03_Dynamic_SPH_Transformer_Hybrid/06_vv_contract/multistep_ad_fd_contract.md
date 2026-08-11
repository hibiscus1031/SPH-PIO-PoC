# Multistep AD/FD contract

At horizons 1, 2, 4, and 8 accepted steps, compare automatic differentiation with centered finite differences for at least: one generic network parameter, one temporal attention-logit parameter (D3), one pair-head parameter, one initial velocity component, one initial density value, and one hidden-token component.

Each case uses at least three finite-difference epsilons and searches for a stable truncation/roundoff window. The objective, scalar projection, dtype, topology hashes, tolerances, and aggregation are frozen before execution. Parameter, initial-state, and hidden-state gradients are reported separately.

Fixed-topology samples determine the gradient gate. Perturbations causing edge birth/death are labeled topology events, report one-/two-sided behavior and finite jumps separately, and are not mislabeled network-gradient failures. Non-finite, unbounded, or missing stable windows remain failures/evidence gaps rather than being removed.
