# Stage 03A dynamic solver specification

## New route and historical boundary

Stage 03 tests a new hypothesis: short causal local memory coupled to a hard-antisymmetric pair-force correction may express dynamic closure better than an instantaneous static operator. It is not Stage 02 v0.3, continuation of a failed checkpoint, K2 embedding, a rollout-based reinterpretation of static failure, or a rewrite of Stage 01 `V2_QUALIFICATION_FAIL`.

Stage 01H remains `FINITE_RESOLUTION_DOMINANT`; viscosity operator form remains `NOT_CONFIRMED`. Stage 02J-W, K, M, M-R, and M-Q statuses remain respectively `BLIND_MULTIFAMILY_DATASET_READY`, `PAIR_FORCE_PIO_ARCHITECTURE_QUALIFIED`, `STATIC_PAIR_FORCE_FITTING_NOT_QUALIFIED`, `STATIC_FITTING_FAILURE_ATTRIBUTED_OPTIMIZATION_CONDITIONING`, and `STATIC_PAIR_FORCE_FITTING_V02_NOT_QUALIFIED`. The static learning route is `TERMINATED`; regularity is `diagnostic_only`.

Stage 02 checkpoints are hash-frozen as `historical_static_diagnostic_only`, with dynamic initialization forbidden. Its test is consumed historical evidence, never a new Stage 03 blind test.

## Equations and scope

The state is accepted `x,v,rho`, EOS pressure, fixed mass, smoothing length, and a stage-specific reciprocal graph; temporal hidden state is separate. Canonical names `smoothing_length/ell_i` and `temporal_hidden/q_i` resolve symbol ambiguity. The system evolves `dx/dt=v`, baseline SPH continuity, and `dv/dt=a_SPH+a_theta`, with `p=cs^2(rho-rho0)`. Only momentum acceleration may be corrected.

The correction is the mass-normalized sum of pair forces `F0[alpha rhat+beta t]`. Symmetric bounded coefficients and antisymmetric geometric bases guarantee equal/opposite forces. Node heads, directed softmax, penalties, mean removal, and conservation projection are forbidden. Per-stage normalized correction residual is `<=1e-10`.

## Outcome boundary

This report specifies no executable model, trajectory, optimizer, training, rollout, or performance result. Full details are in `01_governing_contract`; provenance is in `10_manifests`.
