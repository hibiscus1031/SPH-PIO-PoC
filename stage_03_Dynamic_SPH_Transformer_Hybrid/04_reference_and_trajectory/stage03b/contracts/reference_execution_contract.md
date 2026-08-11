# Stage 03B reference execution contract

Stage 03B is authorized only by Stage 03A status `DYNAMIC_HYBRID_SOLVER_SPECIFICATION_COMPLETE`. Formal qualification uses deterministic CPU float64 on the periodic square `[-1,1)^2`, so `L=2`, `rho0=1`, `cs=20`, `nu=0.02`, regular equal-mass material layouts, reciprocal minimum-image graphs, and `H/dx=2.6`. The shared output grid is `tau=n/256`, `n=0,...,16`, with physical time `t=tau L/cs`.

D-R1 exact trajectories are material-map references. D-R2 integrates the same frozen semidiscrete WCSPH continuity, pressure, viscosity and EOS operators with the exact MMS external source and a graph rebuild at every RHS evaluation. D-R2 is a time reference only. D-R3 oblique shear is a new source-free independent-validation family. Acoustic and vortex cases are boundary audits, not presumed exact references.

Each resolution/time/support descendant belongs to its formula lineage and is not an IID sample. All generated records have `audit_reference_trajectory_records` role and no train/validation/test split, normalization, neural target, learned correction, optimizer state, or model feature payload.
