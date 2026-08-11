# Reverse/JVP/FD comparison contract

Each formal Stage 04C parameter-group probe must evaluate the identical directional derivative of `L_state` by:

1. reverse VJP/backpropagation;
2. forward JVP;
3. central finite difference `(L(theta + epsilon p) - L(theta - epsilon p)) / (2 epsilon)`;
4. at least three prospectively registered positive epsilon values;
5. a preregistered stable-window rule across adjacent or otherwise declared epsilon values;
6. an independent deterministic repeat.

The parameter direction must be normalized by a prospectively declared convention and hashed. Plus/minus evaluations must rebuild all model-dependent RK2 state and midpoint graphs under the same deterministic rules; no reference midpoint injection is allowed. Parameters must be restored exactly between evaluations.

Stage 04C must preregister absolute/relative comparison metrics, structural-zero handling, stable-window criteria, nonfinite policy, and aggregation before decoding formal outcomes. At least one qualifying stable window is required for each hard-gated group, but the numerical tolerances themselves are intentionally not fixed in Stage 04A.

Reverse–JVP agreement alone is insufficient because both can share an implementation error; finite differences are required. A finite-difference match without deterministic repeat is also insufficient. Raw results, including failed epsilon values, must be retained.
