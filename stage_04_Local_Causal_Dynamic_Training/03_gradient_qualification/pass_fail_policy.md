# Parameter-gradient pass/fail policy

## Required gate classes

A formal Stage 04C arm can pass only if all preregistered hard parameter groups are present; computations are finite; reverse VJP and forward JVP meet their agreement rule; central FD supplies the required stable window from at least three epsilons; the AD/FD rule passes; and deterministic repeat passes. D3 additionally requires verified CPU float64 math-SDPA identity.

Missing groups, silent backend fallback, target leakage, use of nonformal precision, absent raw failures, or post-result threshold/epsilon changes force `NOT_QUALIFIED` for the affected arm. Diagnostic input-gradient failures are reported but do not change the optimizer-variable hard verdict; they also cannot be described as repaired.

## Numerical thresholds

Stage 04A freezes gate structure, not numbers. Stage 04C must prospectively freeze tolerances, direction counts, coverage counts, epsilon values, stable-window definition, zero-derivative handling, and repeat rules before formal execution. D-R3 and Stage 03D-R values are prohibited threshold sources.

## Downstream meaning

A passing Stage 04C verdict establishes only that the preregistered K=1 task-aligned parameter derivatives are qualified under the formal environment. It does not establish optimization success, generalization, rollout stability, or solver performance. Only a passing 04C may contribute to 04D preflight; it does not directly authorize training.
