# Stage 01B operator verification

Date: 2026-07-31
Scope: V1 code verification only
Pinned diffSPH commit:
`fff180c81d57a51035de9f4d358dbcaccf973928`
Final V1 decision: **V1_FAIL**

## 1. Executive decision

The V1 work produced quantitative, reproducible diagnostics for the kernel,
periodic neighborhood, manufactured gradient/divergence/Laplacian, pressure
and viscosity conservation structure, and the current diffSPH integrator
interface. The resulting decision is nevertheless **V1_FAIL**.

The decisive evidence is:

1. The upstream default `verletScale=1.4` produced thousands of duplicate
   periodic neighbor edges. On the regular \(16\times16\) layout it returned
   18,096 edges but only 12,544 unique edges, i.e. 5,552 duplicates. The
   duplicate accumulation raised the zeroth-moment L2 error to 0.252574 and
   the manufactured-Laplacian L2 error to 20.019825.
2. A documented `verletScale=1.0` neighborhood path eliminated duplicate,
   nonreciprocal, out-of-bounds, strict-interior-omission, and unexpected
   edges for all nine tested layouts. This correction was made before any V2
   fixed-Re TGV result was generated. It qualifies the neighborhood structure,
   not the complete physical operator.
3. On that structurally qualified path, the 10% jittered zeroth kernel moment
   did not improve with refinement: \(S_0\) L2 was
   0.017911, 0.017625, and 0.019146 at 16, 24, and 32 particles per axis.
   The endpoint is about 6.9% worse than the coarsest result, and its Linf
   error increases from 0.050717 to 0.078214.
4. The 10% jittered manufactured Laplacian was nonmonotone:
   L2 \(=4.307394,\ 3.017805,\ 3.276686\), with observed orders
   \(0.878\) and \(-0.286\). The finest refinement therefore made the error
   larger.
5. The explicit-physical-\(\nu\) generic Laplacian is dissipative for the
   tested velocity field, but it is not mass-weighted pair conservative when
   density varies. With a 5% density perturbation, the characteristic-
   normalized total internal-force residual remains
   \(5.75\times10^{-3}\) to \(1.10\times10^{-2}\).
6. The configured Antuono pressure branch is pairwise conservative to
   float32 rounding when pressure is everywhere positive, but its
   sign-dependent mixed-pressure branch is not pair antisymmetric. On
   jittered layouts, the normalized total internal-force residual reaches
   \(5.24\times10^{-3}\).
7. All six requested 3/5/8-step automatic-differentiation cases failed in the
   pinned upstream custom Laplacian backward because `h_i` was `None`.
   Central finite differences remained finite and nonzero in all six cases,
   proving value sensitivity but not a usable AD path. No upstream package
   source was patched, and no valid 3/5/8-step AD-gradient series can be
   claimed from this path.

These are measured operator limitations, not theoretical concerns. Under the
Stage 01B stopping rule, the failed/noncredible refinement and conservation/AD
gates close the V2 fixed-physics TGV branch. No V2/TGV execution result is
reported here.

## 2. Evidence, implementation, and reproducibility

The V1 generator is
`01_solver/verification/run_operator_verification.py`. Shared deterministic
layout and operator functions are in
`01_solver/verification/operator_tools.py`; the exact manufactured fields are
in `01_solver/manufactured_fields/periodic.py`. The fixed-physics
configuration and the project-owned physical-viscosity adapter are in:

- `01_solver/verification/fixed_physics_tgv.py`;
- `01_solver/viscosity_audit/physical_nu_adapter.py`.

The adapter does not modify installed diffSPH source. It verifies source
hashes, clones the official `deltaPlusSPHScheme` function with a private
globals dictionary, and changes only the private velocity-diffusion callable.
The callable evaluates diffSPH's public `SPHOperation` with
`Operation.Laplacian`, `SupportScheme.Symmetric`,
`GradientMode.Difference`, and `LaplacianMode.default`, then returns the
explicit product \(\nu L_h(\mathbf v)\). The detailed parameter-path
qualification is in `07_reports/stage_01b_viscosity_parameter_audit.md`.

The static V1 layouts use CPU float32, domain length \(L=2\), support
\(H=4\,dx\), and:

| Layout | Jitter relative to \(dx\) | Seed |
|---|---:|---:|
| regular | 0 | 20260801 |
| jitter_05 | 5% | 20260806 |
| jitter_10 | 10% | 20260811 |

For each layout, \(N=16,24,32\) particles per axis were used
(\(256,576,1024\) particles). The actual position-tensor SHA-256 hashes,
spacing, support, and `verlet_scale=1.0` are recorded in
`06_experiments/stage_01b_operator_verification/results/layout_hashes.csv`.
Thus the jittered particle states are reproducible independently of the
reported scalar metrics.

Machine-readable evidence:

- `06_experiments/stage_01b_operator_verification/results/upstream_default_neighbor_diagnostic.csv`;
- `06_experiments/stage_01b_operator_verification/results/neighborhood_audit.csv`;
- `06_experiments/stage_01b_operator_verification/results/kernel_moment_metrics.csv`;
- `06_experiments/stage_01b_operator_verification/results/manufactured_operator_metrics.csv`;
- `06_experiments/stage_01b_operator_verification/results/conservation_audit.csv`;
- `06_experiments/stage_01b_operator_verification/results/integrator_order.csv`;
- `06_experiments/stage_01b_operator_verification/results/autograd_scope.csv`.

Figures:

- `06_experiments/stage_01b_operator_verification/figures/kernel_moment_errors.png`;
- `06_experiments/stage_01b_operator_verification/figures/manufactured_operator_errors.png`;
- `06_experiments/stage_01b_operator_verification/figures/conservation_residuals.png`;
- `06_experiments/stage_01b_operator_verification/figures/integrator_order.png`.

## 3. Upstream default-neighborhood failure and qualified path

The upstream default `verletScale=1.4` was evaluated at \(16\times16\) using
the same states and audit code as the final path. Although `verletScale` is a
neighborhood-list parameter and should not multiply a physical contribution,
the observed lists contained repeated directed \((i,j)\) edges. Those
repeated edges were accumulated more than once by the kernel and Laplacian
reductions.

| Layout | `verletScale` | Edges | Unique edges | Duplicate edges | \(S_0\) L2 | Laplacian L2 |
|---|---:|---:|---:|---:|---:|---:|
| regular | 1.4 | 18,096 | 12,544 | 5,552 | 0.252574 | 20.019825 |
| regular | 1.0 | 11,520 | 11,520 | 0 | 0.000416 | 3.807647 |
| jitter_05 | 1.4 | 17,318 | 12,040 | 5,278 | 0.253225 | 20.024097 |
| jitter_05 | 1.0 | 12,040 | 12,040 | 0 | 0.009243 | 3.874646 |
| jitter_10 | 1.4 | 17,562 | 12,182 | 5,380 | 0.254911 | 20.068666 |
| jitter_10 | 1.0 | 12,182 | 12,182 | 0 | 0.017911 | 4.307394 |

This evidence is preserved rather than replacing the failed default result.
The V1 datasets below use `verletScale=1.0`. This setting is explicit in
`FixedPhysicsTGVConfig` and is the only neighborhood path assessed further.
It is called the **qualified 1.0 neighborhood path** solely because its
topology passed the explicit structural audit. It does not imply that the
kernel, differential operators, conservation properties, or complete solver
passed V1.

For all nine qualified layouts:

- duplicate edges: 0;
- missing self edges: 0;
- nonreciprocal nonself edges: 0;
- out-of-bounds edges: 0;
- minimum-image displacement Linf discrepancy: 0;
- omitted strict-interior edges: 0;
- unexpected edges: 0.

The regular layouts omit 1,024, 1,056, and 4,096 *inclusive-cutoff* pairs at
\(N=16,24,32\), respectively. They are located on the exact support boundary;
the strict-interior omission count is zero and the compact-support kernel is
zero at that boundary. These counts are retained in
`neighborhood_audit.csv` and are not silently relabeled as present.

Qualified-path directed edge counts are:

| Layout | \(N=16\) | \(N=24\) | \(N=32\) |
|---|---:|---:|---:|
| regular | 11,520 | 27,168 | 46,080 |
| jitter_05 | 12,040 | 27,052 | 48,092 |
| jitter_10 | 12,182 | 27,402 | 48,700 |

Neighborhood structural result for `verletScale=1.0`: **PASS**.
Upstream default `verletScale=1.4`: **FAIL**.

## 4. Kernel moments

The audited moments are

\[
S_{0,i}=\sum_j \frac{m_j}{\rho_j}W_{ij},
\qquad
\mathbf S_{1,i}=\sum_j \frac{m_j}{\rho_j}
(\mathbf x_j-\mathbf x_i)W_{ij}.
\]

All requested error quantities are shown below; no Boolean result substitutes
for the values.

| Layout | \(N\) | mean \(\lvert S_0-1\rvert\) | \(S_0\) L2 | \(S_0\) Linf | \(S_1\) L2 | \(S_1\) Linf |
|---|---:|---:|---:|---:|---:|---:|
| regular | 16 | 4.15749e-4 | 4.15749e-4 | 4.15921e-4 | 2.73823e-9 | 1.25947e-8 |
| regular | 24 | 4.15832e-4 | 4.15832e-4 | 4.16756e-4 | 1.36057e-8 | 2.74927e-8 |
| regular | 32 | 4.15750e-4 | 4.15750e-4 | 4.15921e-4 | 1.30300e-9 | 6.17001e-9 |
| jitter_05 | 16 | 7.48716e-3 | 9.24326e-3 | 2.71655e-2 | 1.17624e-3 | 3.78096e-3 |
| jitter_05 | 24 | 7.00583e-3 | 8.71703e-3 | 2.50148e-2 | 7.46978e-4 | 2.30976e-3 |
| jitter_05 | 32 | 7.33357e-3 | 9.10358e-3 | 2.72955e-2 | 5.36610e-4 | 1.72124e-3 |
| jitter_10 | 16 | 1.45470e-2 | 1.79112e-2 | 5.07174e-2 | 2.10723e-3 | 5.59617e-3 |
| jitter_10 | 24 | 1.40278e-2 | 1.76247e-2 | 6.21027e-2 | 1.45280e-3 | 5.55449e-3 |
| jitter_10 | 32 | 1.52302e-2 | 1.91465e-2 | 7.82136e-2 | 1.10934e-3 | 4.20712e-3 |

Interpretation:

- The regular \(S_0\) error is small but essentially resolution-independent,
  approximately \(4.16\times10^{-4}\); \(S_1\) is at float32/accumulation
  roundoff scale.
- At 5% jitter, \(S_1\) improves with refinement, but \(S_0\) L2 reaches its
  minimum at \(N=24\) and then increases by about 4.4% at \(N=32\). The finest
  value remains only about 1.5% below the coarsest value, so this is not a
  robust monotone consistency trend.
- At 10% jitter, \(S_1\) again improves, but \(S_0\) fails the refinement
  check. Its finest L2 is about 6.9% above its coarsest value, while Linf
  worsens monotonically by about 54%.

Kernel-moment completion: **PASS** as a measurement task.
Kernel consistency qualification under particle disorder: **FAIL**.

## 5. Manufactured differential operators

The periodic scalar field and exact derivatives are:

\[
f(x,y)=\sin(2\pi x)+\frac12\cos(2\pi y),
\]

\[
\nabla f=
\left(
2\pi\cos(2\pi x),
-\pi\sin(2\pi y)
\right),
\]

\[
\nabla^2 f=
-4\pi^2\left[
\sin(2\pi x)+\frac12\cos(2\pi y)
\right].
\]

The periodic vector field and exact divergence are:

\[
\mathbf v(x,y)=
\left(\sin(2\pi x),\ \cos(2\pi y)\right),
\qquad
\nabla\cdot\mathbf v=
2\pi\cos(2\pi x)-2\pi\sin(2\pi y).
\]

The gradient and divergence results below are for the generic diffSPH
difference operators. The CSV label
`physical_nu_generic_laplacian` denotes the unscaled \(L_h\) selected for the
physical-\(\nu\) adapter: the reported manufactured error compares
\(L_h(f)\) directly with \(\nabla^2 f\), before multiplication by \(\nu\).
It is not the Antuono pressure-gradient operator and it is not the original
DeltaSPH artificial-viscosity operator.

The complete L1/L2/Linf values are in
`manufactured_operator_metrics.csv`. The principal L2 results and the
orders computed using the actual resolution ratios are:

| Operator | Layout | L2 \(N=16\) | L2 \(N=24\) | L2 \(N=32\) | \(p_{16\to24}\) | \(p_{24\to32}\) |
|---|---|---:|---:|---:|---:|---:|
| gradient | regular | 0.819139 | 0.391369 | 0.227317 | 1.822 | 1.889 |
| gradient | jitter_05 | 0.822071 | 0.394994 | 0.232188 | 1.808 | 1.847 |
| gradient | jitter_10 | 0.823953 | 0.406847 | 0.245013 | 1.740 | 1.763 |
| divergence | regular | 1.465320 | 0.700101 | 0.406637 | 1.822 | 1.889 |
| divergence | jitter_05 | 1.466700 | 0.702353 | 0.410977 | 1.816 | 1.863 |
| divergence | jitter_10 | 1.462943 | 0.716647 | 0.423404 | 1.760 | 1.829 |
| Laplacian | regular | 3.807647 | 1.790382 | 1.040489 | 1.861 | 1.887 |
| Laplacian | jitter_05 | 3.874646 | 2.180014 | 1.809808 | 1.418 | 0.647 |
| Laplacian | jitter_10 | 4.307394 | 3.017805 | 3.276686 | 0.878 | -0.286 |

Additional findings:

- A constant scalar field produced exactly zero stored entries for the
  generic gradient on the 10% jittered \(24\times24\) layout.
- The same constant field produced exactly zero stored entries for the
  selected generic Laplacian on that layout.
- Gradient L1, L2, and Linf decrease from \(N=16\) through \(N=32\) for all
  three layouts. Divergence L1, L2, and Linf do likewise.
- The regular Laplacian has a credible near-second-order trend over these
  three resolutions.
- The 5% jittered Laplacian remains decreasing in L1 and L2, but its L2 order
  degrades from 1.418 to 0.647; Linf actually rises from 5.350983 at \(N=24\)
  to 5.714979 at \(N=32\), giving order \(-0.229\).
- The 10% jittered Laplacian fails at the finest refinement in every norm:
  L1 order \(-0.123\), L2 order \(-0.286\), and Linf order \(-1.843\).
  The Linf error grows from 8.134393 to 13.826294.

Manufactured gradient: **PASS**.
Manufactured divergence: **PASS**.
Manufactured Laplacian on regular particles: **PASS**.
Manufactured Laplacian under the required 10% disorder: **FAIL**.

The 10% layout is a required case, so it cannot be deleted or excluded to
claim operator consistency.

## 6. Pair and global conservation structure

The conservation audit separates the project physical-\(\nu\) generic
Laplacian from the configured Antuono pressure force. The static force
diagnostic reports:

- unordered-pair residuals
  \(\lVert\mathbf f_{ij}+\mathbf f_{ji}\rVert\);
- absolute total internal force
  \(\lVert\sum_i m_i\mathbf a_i\rVert\);
- total internal force normalized by a characteristic sum of edge-force or
  acceleration magnitudes;
- viscous power;
- total torque for viscosity.

### 6.1 Explicit-physical-\(\nu\) generic Laplacian

At uniform density, pair residual Linf is between 0 and
\(5.12\times10^{-9}\), and normalized total internal-force residual is between
\(2.97\times10^{-9}\) and \(3.15\times10^{-8}\) over all layouts and
resolutions. This is consistent with pair/global conservation to float32
rounding for this restricted state. Viscous power is negative in every row
(approximately \(-2.76\) to \(-3.06\)), so the tested field is dissipative.

With the required 5% density perturbation, the \(m_j/\rho_j\) weighting makes
the mass-weighted opposite edge force unequal. The nonconservation does not
vanish at the tested resolutions:

| Layout | Normalized total force, \(N=16\) | \(N=24\) | \(N=32\) |
|---|---:|---:|---:|
| regular | 0.0110340 | 0.0075918 | 0.0057610 |
| jitter_05 | 0.0110084 | 0.0075721 | 0.0057483 |
| jitter_10 | 0.0109647 | 0.0075301 | 0.0057509 |

Across these rows, pair-force residual L2 is
\(5.62\times10^{-6}\) to \(2.14\times10^{-5}\), and pair-force residual Linf
is \(3.40\times10^{-5}\) to \(1.43\times10^{-4}\). Refinement reduces the
residual but does not establish exact discrete momentum conservation.

The viscous edge force is generally not parallel to the interparticle
displacement; it is therefore not a central-force construction, and angular
momentum conservation is not guaranteed theoretically. This is visible on
jittered uniform-density layouts, where measured total torque includes
\(-9.23\times10^{-4}\) at \(N=16\), 5% jitter, and
\(-2.29\times10^{-3}\) at \(N=24\), 10% jitter. Finite torque is reported as a
property, not accepted as an angular-momentum pass.

### 6.2 Antuono pressure force

The pressure audit uses two density/EOS branches:

- `all_positive_pressure`: density offset 1.01, amplitude 0.005;
- `mixed_sign_pressure`: density offset 1.00, amplitude 0.005.

For the all-positive branch, pair residual Linf is
\(1.86\times10^{-9}\) to \(3.17\times10^{-8}\), and the normalized total
internal-force residual is \(1.55\times10^{-8}\) to \(2.87\times10^{-7}\).
These values are consistent with float32 accumulation rounding. A provisional
\(2.0\times10^{-8}\) pair threshold initially failed at the exact measured
value \(2.3283064\times10^{-8}\); the diagnostic threshold was then set to
\(5.0\times10^{-8}\). The exact value remains in the CSV and was not rounded
to zero.

When pressure crosses zero, the Antuono sign-dependent edge expression is not
pair antisymmetric. Regular layouts retain small global residuals through
symmetry cancellation even though their pair residuals are nonzero. Jitter
breaks that cancellation:

| Layout | Normalized total force, \(N=16\) | \(N=24\) | \(N=32\) |
|---|---:|---:|---:|
| regular | 3.2748e-8 | 1.4253e-7 | 4.7620e-8 |
| jitter_05 | 0.0052425 | 0.0004920 | 0.0003352 |
| jitter_10 | 0.0038753 | 0.0016830 | 0.0010189 |

The mixed-pressure pair residual Linf ranges from \(2.52\times10^{-3}\) to
\(8.41\times10^{-3}\). The first strict global-conservation test exposed the
5% jittered \(N=24\) value 0.0004920 against a \(2\times10^{-6}\) criterion;
the failure is retained in
`06_experiments/stage_01b_operator_verification/logs/v1_first_pytest_failure.txt`.
The later test asserts that the limitation is *detected*; it does not convert
the force into a conservative operator.

### 6.3 Conservation decision and unmeasured rollout drift

Uniform-density viscous pair balance: **PASS for the tested state**.
Variable-density viscous pair/global balance: **FAIL**.
All-positive Antuono pressure balance: **PASS to float32 rounding**.
Mixed-sign Antuono pressure pair/global balance on disorder: **FAIL**.
Angular-momentum conservation for the noncentral viscous force: **not
theoretically guaranteed and not qualified**.

`conservation_audit.csv` is an instantaneous force audit. It is not a
fixed-physics rollout, so it does not provide
\(\lVert P(t)-P(0)\rVert\) or its characteristic-velocity normalization over
time. Because V1 failed before the V2 rollout branch, those dynamic quantities
remain **not measured** here and must not be inferred from the static residual.

## 7. Integrator-interface order verification

`01_solver/verification/integrator_ode.py` uses diffSPH's actual
`getIntegrationEnum`/`getIntegrator` interface and a minimal compatible state
adapter to solve

\[
\frac{dy}{dt}=-1.3y,\qquad y(0)=1,\qquad t_\mathrm{final}=1.
\]

It does not substitute a project-written time integrator. The observed data
are:

| \(\Delta t\) | Numerical \(y(1)\) | Exact \(y(1)\) | Absolute error | Observed order |
|---:|---:|---:|---:|---:|
| 0.1000 | 0.2736342600 | 0.2725317930 | 1.102467e-3 | — |
| 0.0500 | 0.2727938770 | 0.2725317930 | 2.620840e-4 | 2.0726 |
| 0.0250 | 0.2725957106 | 0.2725317930 | 6.391756e-5 | 2.0357 |
| 0.0125 | 0.2725475773 | 0.2725317930 | 1.578423e-5 | 2.0177 |

The current pinned source registers `symplecticEuler` with metadata order 2,
and the tested interface behaves at approximately second order for this
decay ODE. It would be incorrect to relabel the measured result as first order
merely because the scheme name contains “Euler.”

Integrator-interface result: **PASS, observed order approximately 2**.

This test qualifies the interface on one smooth scalar ODE. It does not by
itself establish the temporal order of the full WCSPH solution with neighbor,
density, shifting, and pressure updates.

## 8. Automatic-differentiation qualification

The fixed-neighbor value-path diagnostic is implemented in
`01_solver/verification/autograd_scope.py`. It attempts gradients with respect
to:

1. the explicit physical viscosity \(\nu\); and
2. one local continuous velocity-state component,

for 3, 5, and 8 steps, with central finite-difference sanity checks.

The initial run stopped at the first three-step backward failure; that
historical stack remains in
`06_experiments/stage_01b_operator_verification/logs/autograd_multistep_failure.txt`.
The diagnostic was then changed only to isolate each case, retain each full
exception, and continue with the finite-difference side. It did not patch or
bypass the upstream backward. The resulting six-row matrix is in
`06_experiments/stage_01b_operator_verification/results/autograd_scope.csv`,
and all six sanitized full stacks are in
`06_experiments/stage_01b_operator_verification/logs/autograd_scope_failures.txt`.

Every AD case reaches the pinned upstream
`diffSPH/sphOperations/laplacian.py:1062` custom backward and fails in
`laplacian.py:925` while evaluating a term containing `1e-8 * h_i`, because
`h_i=None`:

```text
TypeError: unsupported operand type(s) for *: 'float' and 'NoneType'
```

The complete matrix is:

| Parameter | Steps | Loss | AD status | AD gradient/norm | FD status | Central-FD gradient |
|---|---:|---:|---|---|---|---:|
| physical viscosity \(\nu\) | 3 | 0.2497230470 | FAIL | NaN / NaN | PASS | -0.013858080 |
| physical viscosity \(\nu\) | 5 | 0.2495385408 | FAIL | NaN / NaN | PASS | -0.023096800 |
| physical viscosity \(\nu\) | 8 | 0.2492619455 | FAIL | NaN / NaN | PASS | -0.037029386 |
| local \(v_x\), particle 0 | 3 | 0.2497230470 | FAIL | NaN / NaN | PASS | -0.000745058 |
| local \(v_x\), particle 0 | 5 | 0.2495385408 | FAIL | NaN / NaN | PASS | -0.000745058 |
| local \(v_x\), particle 0 | 8 | 0.2492619455 | FAIL | NaN / NaN | PASS | -0.000745058 |

The finite-difference epsilon is \(10^{-4}\) for every row. Its nonzero values
show that the rollout loss responds to both continuous inputs, and the
physical-\(\nu\) sensitivity magnitude grows across 3/5/8 steps. Because the
AD values are NaN, no AD/FD relative difference or gradient-norm evolution can
be reported. Finite-difference success must not be relabeled as automatic
differentiation success.

The explicit-\(\nu\) forward propagation is also independently established:
\(\nu=0\) yields zero viscous acceleration, and the \(\nu=0.04\) increment is
twice the \(\nu=0.02\) increment within the recorded float32 tolerances.
That forward linearity does not prove the upstream custom backward.

No package patch was applied. Consequently:

- 3/5/8-step physical-\(\nu\) AD gradients: **FAIL / NaN**;
- 3/5/8-step local-state AD gradients through this rollout: **FAIL / NaN**;
- central finite-difference sensitivities: **PASS / finite and nonzero**;
- AD-versus-finite-difference agreement for this path: **not computable**;
- fixed-neighbor value-path differentiability of the complete B-path:
  **FAIL**;
- differentiability of neighbor-topology changes: **outside scope and not
  claimed**.

This finding does not rewrite the earlier Stage 01 three-step initial-amplitude
value-path result. It specifically shows that introducing the generic
Laplacian into a multistep graph exposes an additional upstream backward
failure.

## 9. Tests, warning policy, and interpretation

The final complete project suite was executed with warnings promoted to
errors:

```text
/opt/miniconda3/envs/sph-pio-poc/bin/python -m pytest -q -W error
```

Final result after adding the machine-readable preregistration check:
**69 passed in 7.23 s**, with no unfiltered warning emitted. The JUnit record
is `06_experiments/stage_01b_operator_verification/logs/pytest_werror.xml`.

The requested classification of the 430-warning Stage 01 baseline is taken
from the preserved, unchanged
`06_experiments/stage_01_tgv/logs/final_pytest.txt`:

| Warning source | Type | Count | Classification |
|---|---|---:|---|
| `torch.jit._script:1488` | `DeprecationWarning` | 423 | PyTorch upstream deprecation reached while importing diffSPH JIT code |
| `diffSPH.regions:179` | `UserWarning` | 4 | diffSPH default-support configuration warning |
| `torch.utils.checkpoint:238` | `UserWarning` | 3 | PyTorch upstream no-gradient-input checkpoint warning |
| Project source | any | 0 | no project-originated warning in the preserved baseline |

The counts sum exactly to 430. No separate direct diffSPH deprecation warning
was present in that preserved run; the deprecation source was PyTorch.

`pytest.ini` first declares `error`, then permits only three exact
upstream-source/message filters:

1. the `torch.jit.script` deprecation from `torch.jit._script`;
2. the checkpoint “inputs have requires_grad=False” warning from
   `torch.utils.checkpoint`;
3. the default-support warning from `diffSPH.regions`.

There is no global warning ignore. Root `conftest.py` reapplies the same three
exact filters as per-test markers so the literal command-line `-W error`
check cannot override them; `tests/conftest.py` contains only the project
import-path setup. Thus project-originated or previously unseen warnings
remain errors.

Before the known-limit tests were separated, the preserved V1-only runs were:

- 43 passed, 1 failed: mixed-sign Antuono pressure global residual
  \(4.92038\times10^{-4}\);
- 44 passed, 1 failed: all-positive pressure pair residual
  \(2.3283064\times10^{-8}\), narrowly above the provisional pure-float32
  threshold.

The final 69-test green count must not be read as `V1_PASS`. In particular:

- `test_variable_density_nonconservation_is_detected_not_hidden` passes only
  when a nonzero variable-density viscous conservation defect is detected;
- `test_antuono_mixed_pressure_nonconservation_is_detected` passes only when
  the mixed-pressure nonconservation is exposed;
- manufactured-operator tests preserve and quantify trends but cannot turn
  the finest 10% jittered Laplacian rebound into convergence;
- `test_stage01b_short_rollout_exposes_upstream_backward_failure` passes only
  when all six upstream AD failures, NaN AD gradients, and nonzero finite-
  difference sensitivities are retained.

Therefore, test green status establishes reproducibility of the observations,
not acceptability of every observed operator property.

## 10. V1 gate matrix

| V1 item | Evidence status | Qualification |
|---|---|---|
| Fixed physical-\(\nu\) forward parameter propagation | Completed | PASS for forward value propagation |
| Upstream default periodic neighborhood (`verletScale=1.4`) | Completed | FAIL: thousands of duplicate edges |
| Qualified periodic neighborhood (`verletScale=1.0`) | Completed | PASS for topology/reciprocity/bounds |
| Kernel zeroth and first moments | Completed quantitatively | FAIL under required 10% disorder |
| Manufactured gradient | Completed, all norms | PASS |
| Manufactured divergence | Completed, all norms | PASS |
| Manufactured Laplacian | Completed, all norms | FAIL at finest 10% jitter refinement |
| Viscous pair/global force | Completed | FAIL for variable density |
| Antuono pressure pair/global force | Completed | FAIL for mixed-sign pressure on disorder |
| Viscous torque | Quantified | Not theoretically conserved |
| Dynamic momentum drift | Not run | Not established |
| diffSPH integrator ODE order | Completed at four time steps | PASS; observed \(p\approx2\) |
| 3/5/8-step explicit-\(\nu\) and local-state AD | Six rows and six stacks preserved; FD finite | FAIL / AD gradients NaN |

## 11. Final V1 status and stopping action

The required layouts and operators were not removed, and the failed values
were not replaced by Boolean passes. The finest 10% jittered kernel and
Laplacian results violate the required refinement behavior; the selected
physical-\(\nu\) and pressure operators also expose state-dependent
conservation defects, and the multistep Laplacian backward is not usable in
the pinned upstream version.

**Final status: V1_FAIL**

As a direct consequence:

- no fixed-Re V2 time-convergence experiment is authorized;
- no fixed-Re V2 space-convergence experiment is authorized;
- no TGV result may be presented as fixed-physics V2 evidence;
- no Stage 02 design or neural-network work is authorized by this report.
