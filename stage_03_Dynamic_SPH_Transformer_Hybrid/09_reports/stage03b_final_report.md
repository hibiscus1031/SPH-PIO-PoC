# Stage 03B final report — Dynamic Reference Trajectory Qualification

## 1. Authorization and historical freeze

Stage 03B was authorized solely by Stage 03A `DYNAMIC_HYBRID_SOLVER_SPECIFICATION_COMPLETE`. The 23/23 frozen inputs bind the Stage 03A governing/RK2/graph/topology/reference/lineage/V&V contracts, Stage 01F/F2 MMS evidence, Stage 01G/H evidence, and baseline SPH/EOS/kernel/graph implementation.

Historical verdicts remain unchanged: Stage 01 `V2_QUALIFICATION_FAIL`, Stage 01H `FINITE_RESOLUTION_DOMINANT`, viscosity operator form `NOT_CONFIRMED`, and Stage 02 static route `TERMINATED`. Stage 01 shear/acoustic retains role `historical_independent_evidence_only`; no historical formula/record was relabeled as new blind evidence or used as a training trajectory.

## 2. Common reference environment

Formal execution is deterministic CPU float64 on `[-1,1)^2`, with `L=2`, `rho0=1`, `cs=20`, `nu=0.02`, equal-mass regular material layouts, reciprocal minimum-image graphs, `H/dx=2.6`, N=8²/12²/16², and `tau=n/256` for n=0,…,16. The 17 frames are one trajectory, not IID samples.

## 3. D-R1 material maps, Jacobian, and closures

For `k=2pi/L`, D-R1-A `DR1_LAGRANGIAN_COMPRESSION` uses `Ac=0.02/k`, `x=X+Ac sin(kX)sin(pi tau), y=Y`. D-R1-B `DR1_COUPLED_DEFORMATION` uses `Ax=0.012/k, Ay=0.010/k`, `x=X+Ax sin(kX)cos(kY)sin(2pi tau)`, `y=Y-Ay cos(kX)sin(kY)sin(2pi tau)`.

Both independently compute `F`, `J`, `rho=rho0/J`, physical velocity/material acceleration, EOS pressure, `grad_x p`, `laplacian_x u`, and `f_MMS=D_tu+grad_x(p)/rho-nu laplacian_x(u)`. Continuity source is zero; the momentum source is verification-only and is not a learned-correction target.

Route 1 is frozen SymPy closed form; Route 2 is PyTorch float64 autodiff from the primitive map. On 8192 preregistered points covering all output times/seams/extrema, compression/coupled maximum route disagreement is 7.37e-14/1.85e-13, continuity residual 2.86e-16/4.16e-16, momentum residual 0/0, and EOS/path residual 0. Observed minimum J is 0.996098/0.999228; analytic global lower bounds are 0.98/0.978. Minimum rho is 0.996113/0.999253 and maximum Mach 0.0099999/0.0119912. Both D-R1 families PASS without formula or amplitude retry.

Six D-R1 exact trajectories store complete state/source arrays, material labels, state/graph hashes, reciprocal edge maps and safety/event metrics.

## 4. D-R2 DOP853 identity and sensitivity

D-R2 evolves unwrapped position, velocity and independent density with frozen SPH continuity, pressure, viscosity and EOS. Every RHS rebuilds the reciprocal graph and adds the exact D-R1 external source evaluated at fixed material label/time. Primary is DOP853 `1e-11/1e-13`; sensitivity is `1e-12/1e-14`; max step is one output interval. A second primary establishes deterministic repeat.

All six family/N cases have bitwise primary repeats, identical primary/sensitivity fields, reciprocal identical output graph/event sequences, and PASS the `1e-9/1e-8` L2/Linf gates. Across all paths there were 4302 RHS evaluations and exactly 4302 graph rebuilds.

DOP853-versus-exact differences remain `semidiscrete_spatial_model_form_diagnostic_only`: velocity normalized L2 spans 4.80e-6–4.17e-5 and maximum field normalized Linf is 4.30e-4. They do not enter the time gate and do not make D-R2 spatial, continuum, or V&V-qualified truth.

## 5. D-R3 new oblique shear exact references

The new source-free family uses `kappa=(2pi/L)(m,n)`, `e_perp=(-n,m)/sqrt(m²+n²)`, constant `rho0`, `p=0`, and `u=U_b+A e_perp sin(kappa·(x-U_b t)+phi)exp(-nu|kappa|²t)`. Its exact particle trajectory is the frozen integral along persistent phase `s0`.

Case A `(1,2), phi=.17, U_b/cs=(.011,-.007), A/cs=.015` and case B `(2,-1), .31, (-.006,.009), .012` have momentum residual 1.24e-16/1.40e-16, zero continuity/path/density/pressure drift, maximum Mach 0.0280011/0.0197422, invariance roundoff, and deterministic reciprocal graphs. Both PASS and yield six exact trajectories. Their role is only `independent_source_free_validation_only`; training, normalization, thresholds, and architecture selection are forbidden.

## 6. Acoustic and vortex boundaries

The acoustic viscous linear eigenmode has linearized residual at roundoff and full nonlinear residual proportional to epsilon² (slopes 2.0000 and 2.0055). It is classified `DR3_ACOUSTIC_LINEAR_REGIME_CONDITIONAL`, never `FULL_NONLINEAR_EXACT_REFERENCE`.

The periodic vortex has correct continuity and unsteady-viscous balance, but full momentum residual 0.355073 and EOS/incompressible-pressure mismatch 0.08. It is classified `DR3_PERIODIC_VORTEX_REJECTED_AS_EXACT_SOURCE_FREE_REFERENCE`; only a separately sourced `DR1_PERIODIC_VORTEX_MMS_ONLY` role could be considered later. Stage 01E mismatch is preserved.

## 7. Topology-event registry

D-R1-B was scanned at 1025 exact times for each N and repeated. No edge birth/death, cutoff touch, reciprocal event, or graph-relevant minimum-image switch occurs on `[0,0.0625]`; cutoff margins are 0.05694, 0.03792 and 0.02843. The registry therefore truthfully records zero events and full fixed-topology intervals. No gradient audit occurred. Event count was not manipulated by changing amplitude.

## 8. Uncertainty, lineage, provenance, and resources

D-R1 derivative/roundoff/chain-rule, D-R2 tolerance/summation/topology/output interpolation, and D-R3 closure/path/periodic uncertainty are retained in separate buckets. No total GCI is constructed; D-R2 tolerance is not spatial uncertainty and MMS exactness is not physical validation.

All N/dt/support/time descendants remain within formula lineage. The canonical inventory is 18 NPZ trajectories plus sidecars (6 D-R1, 6 D-R2, 6 D-R3) with formula/derivative/state/graph/artifact SHA-256 provenance. There is no split assignment or normalization.

Formal execution used 53.49 s wall time, 348,471,296-byte peak RSS, 3,244,294-byte trajectory-record storage, CPU float64, 4302 RHS calls/rebuilds and zero topology events. These are qualification resource records, not performance claims.

## 9. Exclusions and Stage 03C authorization

Stage 03B implemented no D1/D2/D3 model, Transformer, temporal hidden network, optimizer, training, neural rollout, solver-in-the-loop, dataset split, normalization, or performance comparison. Stage 01/02 histories are unchanged.

All required D-R1, D-R2, D-R3, boundary, topology, uncertainty and provenance gates pass. Limited authorization is granted only for **Stage 03C — Differentiable RK2 Hybrid Solver Implementation and Zero-Correction Verification**.

**DYNAMIC_REFERENCE_TRAJECTORY_QUALIFICATION_COMPLETE**
