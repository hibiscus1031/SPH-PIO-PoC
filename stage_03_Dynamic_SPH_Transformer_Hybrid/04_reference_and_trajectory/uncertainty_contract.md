# Dynamic-reference uncertainty contract

Every reference family must report, where applicable, temporal tolerance/refinement uncertainty, spatial/reference uncertainty, analytic/evaluator roundoff, parameter/initial-condition uncertainty, interpolation or particle-to-field comparison uncertainty, and source/manufacturing residual. The reference class controls which components are meaningful.

D-R2 studies must separate same-operator time error from spatial truth. D-R3/D-R4 comparisons must keep reference uncertainty visible in all error and acceptance statements. If reference uncertainty dominates the model/baseline difference, classify `DYN_REFERENCE_UNCERTAINTY_DOMINANT`; do not claim improvement.

Uncertainty estimates, acceptance logic, and stopping rules must be preregistered. No fabricated GCI is allowed: an observed three-level sequence may be reported without a GCI if asymptotic assumptions fail. Cross terms among time, space, support, learned model, and reference uncertainty must be acknowledged rather than silently assigned to one source.
