# Stage 04C-S Evidence Matrix

| Category | Evidence | Status | Boundary |
|---|---|---|---|
| Training hypothesis | K=1 local-causal formulation | PASS | Contract definition only. |
| Training hypothesis | Complete start/midpoint/accept RK2 transition | PASS | No rollout or optimizer execution. |
| Training hypothesis | Optimizer-variable gradient boundary | PASS | Input-gradient evidence remains diagnostic. |
| Training hypothesis | CPU float64 + explicit math SDPA | PASS | No MPS formal evidence. |
| Reference family pool | 10 formula lineages; 20/20 analytic; 60/60 trajectories | PASS | TRAIN/VALIDATION/SEALED roles frozen before outcomes. |
| Reference family pool | 20/20 DOP853; 10/10 fixed topology | PASS | Reference evidence, not model performance. |
| Reference family pool | 6/2/2 split; leakage=0; sealed formula/state/target decode=0/0/0 | PASS | Private payload remains unopened. |
| Task-gradient qualification | 864 probes; 2592/2592 reverse/JVP; 17280 FD paths | PASS | Implementation consistency only. |
| Task-gradient qualification | 2592 near-zero components; 864 all-near-zero failures | NOT_QUALIFIED | At least one nonzero stable component per probe was required. |
| Task-gradient qualification | Parameter groups qualified | NOT_QUALIFIED | D1/D2/D3 all remain required baselines. |
| Attribution | Full gradients and nonzero coefficient/force/acceleration sensitivity | DIAGNOSTIC | Rejects dead-network explanation; does not qualify Stage04C. |
| Attribution | Exact residual-Jacobian factorization | PASS | 2592/2592 reconstructed derivatives. |
| Attribution | MSE residual factor 50.8%; direction projection 25.9%; RK2 dt/dt² attenuation | DIAGNOSTIC | Contributions are partial and component dependent. |
| Attribution | 604 unresolved rows; mixed/unresolved verdict | UNRESOLVED | No unique next correction branch. |
| Route | Stage 04D | NOT_AUTHORIZED | Training protocol preregistration may not begin. |
| Route | Training / rollout / performance | NOT_EXECUTED | No claims permitted. |
