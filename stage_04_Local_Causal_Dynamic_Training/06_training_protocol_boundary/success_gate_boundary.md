# Success-gate boundary

Stage 04A freezes the categories, not numerical thresholds:

| Gate | Required question |
|---|---|
| A. Numerical safety | Are losses, states, parameters, and solver operations finite and valid? |
| B. Train state-transition fit | Does the arm fit the preregistered K=1 training task? |
| C. Validation family transfer | Does it transfer to disjoint validation formula lineages? |
| D. Sealed-test transfer | Does the frozen checkpoint transfer after legitimate test release? |
| E. Conservation/equivariance | Are structural and numerical invariants satisfied under the evaluation contract? |
| F. Autonomous rollout stability | Does unforced propagation remain stable over preregistered horizons? |
| G. Baseline comparison | How do D1/D2/D3 compare under the same budget and rules? |

Stage 04D must preregister metrics, thresholds, aggregation, uncertainty, multiplicity handling, and failure semantics for the gates relevant to Stage 04E; 04F/04G must preregister later rollout/refinement gates before their execution. No threshold may be derived from validation outcomes, sealed-test values, D-R3, or Stage 03D-R.

Passing training-fit gates is not complete solver success. A full solver claim requires autonomous rollout, independent validation, and refinement evidence. A baseline comparison must not presume D3 superiority and must retain all arm failures.
