# Stage 03A final report — Dynamic Hybrid Solver Specification and V&V Contract

## 1. New-hypothesis declaration

Stage 03 is a new dynamic hybrid-solver route. It asks whether a local Transformer with four-step causal memory, supplying an additive hard-antisymmetric pair-force correction at each SPH step, may represent dynamic closure better than an instantaneous static correction. This is a preregistered hypothesis, not a performance claim.

## 2. Stage 02 static-route boundary and historical freeze

The immutable record is: Stage 01 `V2_QUALIFICATION_FAIL`; Stage 01H `FINITE_RESOLUTION_DOMINANT`; viscosity operator form `NOT_CONFIRMED`; Stage 02J-W `BLIND_MULTIFAMILY_DATASET_READY`; Stage 02K `PAIR_FORCE_PIO_ARCHITECTURE_QUALIFIED`; Stage 02M `STATIC_PAIR_FORCE_FITTING_NOT_QUALIFIED`; Stage 02M-R `STATIC_FITTING_FAILURE_ATTRIBUTED_OPTIMIZATION_CONDITIONING`; Stage 02M-Q `STATIC_PAIR_FORCE_FITTING_V02_NOT_QUALIFIED`; static learning route `TERMINATED`; regularity `diagnostic_only`.

Stage 03 is not static protocol v0.3, continued training of a failed checkpoint, direct K2 embedding, rollout-based concealment of static failure, or a rewrite of Stage 01. Required reports, architecture/dataset artifacts, status ledger, and nine selected v0.2 checkpoints are SHA-256 frozen in the input manifest. All checkpoints have role `historical_static_diagnostic_only`; `dynamic_initialization_permitted=false`. Stage 02 test status is `consumed_confirmatory_test` and cannot be a Stage 03 blind test or threshold source. Historical files were not modified.

## 3. Governing dynamic equations and correction-only scope

Canonical accepted state is `S^n={x_i,v_i,rho_i,p_i,m_i,ell_i,G^n}`; the separate temporal state is `H^n={q_i^n}`. `ell_i/smoothing_length` and `q_i/temporal_hidden` resolve the source symbol collision. Forbidden inputs include references, future states, correction targets, family role, and split label.

The frozen equations are `dx_i/dt=v_i`, `d rho_i/dt=C_SPH,i(S)`, and `dv_i/dt=a_SPH,i(S)+a_theta,i(history)`, with `p_i=cs^2(rho_i-rho0)`. The learned term is additive and corrects momentum acceleration only. Density, pressure/EOS, continuity, position, smoothing length, dt, integrator coefficients, mass, and neighbor topology remain baseline-controlled.

## 4. Reciprocal pair-force conservation

`a_theta,i=(1/m_i) sum_j f_theta,ij`, with `F0_ij=sqrt(m_i m_j)cs^2/L`, minimum-image `rhat_ij`, normalized `dv_ij`, transverse `t_ij`, and `f_theta,ij=F0_ij(alpha_ij rhat_ij+beta_ij t_ij)`. Exchange-symmetric bounded coefficients give `f_theta,ji=-f_theta,ij`. Node correction heads, directed softmax, conservation penalties, mean subtraction, and projection are forbidden. Each learned arm must satisfy per-stage normalized correction residual `<=1e-10`; correction, baseline, and total conservation are reported separately.

## 5. Temporal token and causal Transformer contracts

Tokens use legal normalized node scalars, invariant local graph/relative-velocity summaries, and relative offsets `0,-1,-2,-3`. Absolute position is used only for minimum-image geometry. Absolute velocity as a node feature, `a_SPH`, reference/target quantities, future states, absolute step/time, particle/family embeddings, and validation/test roles are forbidden.

D3 is `CAUSAL_TEMPORAL_RECIPROCAL_TRANSFORMER_PIO`: H=4, scalar width `<=32`, two temporal blocks, heads `<=4`, causal mask required, parameters `<=150000`. Hidden channels are O(2) scalars. Dense global `N x N` attention and arbitrary vector output are forbidden. The pair head uses hidden sums, absolute differences, products, and legal symmetric pair features, ending in bounded tanh coefficients.

## 6. D0/D1/D2/D3 arms

D0 is baseline WCSPH without correction. D1 is a freshly initialized instantaneous conservative pair MLP. D2 is a freshly initialized causal recurrent pair PIO. D3 is the freshly initialized causal temporal reciprocal Transformer PIO. D1–D3 share legal inputs, antisymmetric head, trajectories, loss, and training budget; D2/D3 are same-order parameter scale. No arm reads Stage 02 weights, and D3 is not presumed superior.

## 7. RK2 start, midpoint, graph, and commit semantics

Explicit midpoint/RK2 is frozen. Start state rebuilds `G^n`, builds the token, evaluates baseline/correction, and forms k1. The provisional midpoint is built from k1, recomputes EOS, independently rebuilds its graph, and evaluates with accepted history plus one ephemeral midpoint token to form k2. The accepted state uses k2, recomputes EOS, passes safety, then commits exactly one accepted token. Midpoint state/token is never a physical step or permanent history. Failed steps commit nothing. Whole-step fixed topology is forbidden.

## 8. Topology differentiability and checkpoint/resume

Neighbor index, sorting, and edge existence are discrete. Derivatives pass within fixed realized topology through continuous geometry/state/hidden/parameters. Edge birth/death, cutoff jumps, boundedness, reciprocity, and repeat determinism are separate audits; no fully differentiable neighbor-search claim is allowed. Checkpoints contain accepted state/history and complete configuration/provenance only, and continuous versus resumed runs must reproduce state/graph/history sequences.

## 9. Zero-correction equivalence

Both `correction_enabled=false` and zero final heads must yield `a_theta=0` and reproduce D0 under identical graph, RK2, EOS, update, and safety semantics. One-step, multistep, graph sequence, topology, and resume evidence target bitwise equality; any strict floating-point alternative must be frozen before results and cannot allow topology/branch differences. Temporal history cannot affect baseline state. This is the first implementation hard gate.

## 10. Dynamic reference hierarchy and isolation

D-R1 analytic/MMS is verification and possible controlled training only with family isolation; MMS is not physical validation. D-R2 high-accuracy same-semidscrete time reference isolates time error but is not spatial truth. D-R3 source-free analytic/independent validation is excluded from training, normalization, and thresholds; candidates include shear decay, acoustic wave, and periodic vortex decay. D-R4 is a V&V-qualified external source and is `NOT_AVAILABLE`; higher-resolution SPH alone is not D-R4.

Stage 01 shear/acoustic remains historical independent evidence, not Stage 03 training or fresh blind data. Stage 03 later needs new disjoint training, validation, sealed-test, and independent source-free families. Reference uncertainty stays explicit; dominance triggers `DYN_REFERENCE_UNCERTAINTY_DOMINANT`.

## 11. Trajectory family, lineage, leakage, normalization, and test seal

The sample and split atom is a complete trajectory-family lineage component. Particles, edges, frames, overlapping windows, resolutions, dt/support variants, restarts, resamples, and views are dependent and stay in one component. A common formula at changed resolution, dt, or start time is not automatically independent. No random frame/window split is allowed.

Normalization is train-lineage-only, family-balanced, frozen before validation/test access, and identical for D1–D3. A new Stage 03 test seal is mandatory. Opening it consumes it; Stage 02's consumed test is historical only. No role label enters dynamic input.

## 12. Rollout, loss, and teacher-forcing boundary

Up to three reference states strictly before the origin may warm-start H=4. Thereafter `teacher_forcing_after_start=false`; every accepted state/history entry is self-fed. Horizon order is fixed K=1→2→4→8 with a gate before advancement; failures remain, and short success cannot substitute for long validation.

Future `L_roll` combines horizon-weighted graph-balanced velocity and density errors with periodic minimum-image position error. Pressure is EOS-derived. Acceleration, energy, torque, and power are diagnostics. Conservation/antisymmetry penalties are forbidden. Numerical weights await Stage 03F preregistration and cannot be changed after results.

## 13. V&V D0–D8 and multistep AD/FD

D0 specification precedes D1 zero equivalence, D2 dynamic component verification, D3 multistep differentiability, D4 K=1/2/4/8 fitting, D5 autonomous validation, D6 time/space/support solution verification, D7 independent physical validation, and D8 equal-error cost/utility. Levels cannot be skipped.

At 1/2/4/8 steps, AD/FD covers a generic network parameter, D3 attention-logit parameter, pair-head parameter, initial velocity, initial density, and hidden token, with at least three epsilons and a stable window. Fixed-topology cases set the gradient gate; cutoff-crossing cases are reported separately.

## 14. Stability, failure, and refinement

Frozen failures are `DYN_NAN_INF`, `DYN_NEGATIVE_DENSITY`, `DYN_PARTICLE_CLUSTERING`, `DYN_VOID_FORMATION`, `DYN_GRAPH_DISCONNECTION`, `DYN_FORCE_EXPLOSION`, `DYN_HIDDEN_STATE_EXPLOSION`, `DYN_ROLLOUT_ERROR_DIVERGENCE`, `DYN_CONSERVATION_FAILURE`, `DYN_TOPOLOGY_NONDETERMINISM`, and `DYN_REFERENCE_UNCERTAINTY_DOMINANT`. Records retain first failure step, state/graph/checkpoint hashes, lineage, dt, resolution, support, and preceding metrics; failures cannot be deleted.

Verification paths are dt/dt/2/dt/4, at least three N, at least three H/dx, and 1/2/4/8 plus long autonomous horizon. Baseline, hybrid, reference, time, spatial, support, learned-model, and cross-term errors remain distinct. No fabricated GCI, restored-convergence inference, or unequal-error speedup claim is allowed.

## 15. Resource boundary and roadmap

M2/16 GB PoC is 2D, CPU float64 verification, optional MPS float32 smoke, N<=1024, H=4, K<=8, local-edge operations, truncated BPTT, and small-family preflight. It excludes broad search, large long-rollout/3D training, and full publication matrix. Full 2D work recommends NVIDIA >=24 GB; long rollout/3D recommends >=48 GB or multi-GPU. Activation memory scales `O(K E d)` plus graph, node/history, parameters, allocator overhead, with checkpointing exchanging memory for recompute.

The immutable route is 03A specification; 03B reference qualification; 03C differentiable RK2/zero verification; 03D AD/FD/topology; 03E dataset/split/seal; 03F training preregistration; 03G controlled horizons; 03H autonomous/independent validation; 03I refinement/equal-error cost; 03J publication qualification and Stage 01 relation assessment. 03B–03E cannot be skipped before training.

## 16. Authorization, exclusions, and terminal decision

Limited authorization is granted only for Stage 03B — Dynamic Reference Trajectory Qualification. It does not authorize solver/model implementation, trajectory dataset generation, optimizer, training, rollout fitting/execution, solver-in-the-loop, or a performance claim.

Stage 03A produced no dynamic implementation, no trajectory, no optimizer/training, and no rollout. Stage 01/02 histories are unchanged. All completion predicates and provenance checks pass.

**DYNAMIC_HYBRID_SOLVER_SPECIFICATION_COMPLETE**
