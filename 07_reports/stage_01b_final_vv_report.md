# Stage 01B — Fixed-physics SPH code, solution and physical V&V

Date: 2026-07-31
Audited diffSPH commit:
`fff180c81d57a51035de9f4d358dbcaccf973928`

## Final decision

**`V1_FAIL`**

This decision is a gate result, not an inference from hardware specifications
or an absent run. Quantitative V1 diagnostics were completed, and they exposed
three independent stop conditions:

1. the zeroth kernel-moment error on the 10% jittered layout worsens at the
   finest resolution;
2. the manufactured physical-\(\nu\) Laplacian error on the 10% jittered
   layout rebounds from \(24^2\) to \(32^2\), giving a negative last-step
   observed order;
3. the pinned upstream generic Laplacian custom backward fails on the first
   requested three-step Stage 01B rollout.

The variable-density viscous force and the mixed-sign Antuono pressure branch
also fail strict pairwise/internal-force conservation on disordered layouts.
Under the preregistered stopping rules, the fixed-physics TGV time- and
space-convergence branches were therefore not run. No V2 result is claimed,
and Stage 02 is not authorized.

## 1. Stage 01 reclassification

Stage 01 remains unchanged and is reclassified as **V0 `CONDITIONAL PASS`**:

- the complete official diffSPH execution chain ran;
- the CPU canonical path passed;
- MPS was a hybrid path because compact neighborhood search was bridged
  through CPU;
- a three-step initial-velocity-amplitude value-path derivative passed;
- V1 was only partial, V2 was incomplete, and V3 had not started.

The controlling evidence is
`07_reports/stage_01_scope_reclassification.md`; the preserved original is
`07_reports/stage_01_solver_validation.md`, with the unchanged SHA-256 recorded
in the reclassification report. The freeze commit is
`d3b2a340cef9eb39cb53ca2fa1fbcf28602b771a`, and annotated tag
`stage-01-v0-pass` points to that commit. Stage 01 did not qualify a
fixed-physics reference solver or training-data generator.

## 2. Viscosity, sound-speed and Reynolds-number parameter audit

The source and dynamic audit in
`07_reports/stage_01b_viscosity_parameter_audit.md` established:

- the reachable Stage 01 DeltaSPH velocity-diffusion wrapper hard-codes
  \(\alpha=0.01\) at
  `src/diffSPH/modules/velocityDiffusion.py:94`;
- its unconditional return at lines 106–116 makes the later configuration
  read at line 122 unreachable;
- changing `config["diffusion"]["alpha"]` among 0, 0.01 and 1 produced
  bitwise-identical outputs;
- `alphaOverride=0` still left a nonzero operator because the quadratic
  \(C_q=2\) contribution remained;
- the notebook \(\alpha\)-to-\(\nu\) relation is a setting-specific
  theoretical/empirical estimate, not an exact physical-viscosity identity;
- no wired official velocity operator directly accepts physical kinematic
  viscosity;
- fixed \(c_s\), and hence a fixed nominal initial Mach number, is directly
  controllable.

The original alpha-mapping branch therefore failed. The project-owned B-path
adapter in `01_solver/viscosity_audit/physical_nu_adapter.py` calls the pinned
public diffSPH generic Laplacian and returns the exact explicit product
\(\nu L_h(\mathbf v)\). It clones the official scheme with a private callable
binding and does not patch the installed package. Its forward parameter tests
verify \(\nu=0\Rightarrow\mathbf a_\nu=0\) and
\(\mathbf a(2\nu)=2\mathbf a(\nu)\). This proves parameter propagation, but
does not by itself prove consistency, conservation or multi-step
differentiability.

The preregistered candidate physics in
`06_experiments/stage_01b_fixed_physics_tgv/configs/preregistered_fixed_physics.yml`
and `01_solver/verification/fixed_physics_tgv.py` is

| Quantity | Frozen value |
|---|---:|
| \(U_0\) | 1 |
| domain length \(L\) | 2 |
| \(\rho_0\) | 1 |
| physical \(\nu\) | 0.02 |
| \(Re=U_0L/\nu\) | 100 |
| \(c_s\) | 10 |
| nominal \(Ma_0=U_0/c_s\) | 0.1 |
| EOS | `isoThermal` |
| pressure term | `Antuono` |
| density diffusion | `deltaSPH` |
| integrator | `symplecticEuler` |
| neighborhood `verletScale` | 1.0 |

For \(16^2,24^2,32^2\), the audited initial acoustic limits are
\(6.91\times10^{-3}\), \(4.61\times10^{-3}\), and
\(3.45\times10^{-3}\); the source `maxDt=10^{-3}` is initially stricter.
These are source-derived initial bounds, not a completed stability or
fixed-Re convergence study.

Machine evidence is
`06_experiments/stage_01b_operator_verification/logs/viscosity_parameter_probe.json`.
The import/API failures preceding the successful probe remain in
`06_experiments/stage_01b_operator_verification/logs/viscosity_parameter_probe_import_failure.txt`.

## 3. Kernel moments and periodic neighborhoods

The audit used \(16^2\), \(24^2\), and \(32^2\) particles on regular, 5%
jittered, and 10% jittered periodic layouts. Seeds and realized-position
SHA-256 values are retained in
`06_experiments/stage_01b_operator_verification/results/layout_hashes.csv`.

The zeroth-moment \(L_2\) errors were:

| Layout | \(16^2\) | \(24^2\) | \(32^2\) | Interpretation |
|---|---:|---:|---:|---|
| regular | 0.00041575 | 0.00041583 | 0.00041575 | essentially resolution-independent |
| 5% jitter | 0.0092433 | 0.0087170 | 0.0091036 | nonmonotonic |
| 10% jitter | 0.0179112 | 0.0176247 | 0.0191465 | finest-grid error worsens |

The 10% jittered first-moment \(L_2\) error did decrease from
0.0021072 to 0.0014528 to 0.0011093, but that does not cure the failed
zeroth-moment trend. Full mean-absolute, \(L_2\), and \(L_\infty\) values are
in
`06_experiments/stage_01b_operator_verification/results/kernel_moment_metrics.csv`
and are plotted in
`06_experiments/stage_01b_operator_verification/figures/kernel_moment_errors.png`.

With the explicitly qualified public setting `verletScale=1.0`, all nine
layouts had zero duplicate edges, zero nonreciprocal non-self edges, zero
out-of-range indices, zero missing self edges, zero strict-interior omissions,
zero unexpected edges, and exact recorded minimum-image displacement. On
regular layouts, inclusive-cutoff neighbors whose kernel value is exactly zero
can be absent; they are counted separately and are not strict-interior
omissions.

The upstream default `verletScale=1.4` was not silently accepted: at \(16^2\)
it produced 5,552 duplicate edges on the regular layout, 5,278 at 5% jitter,
and 5,380 at 10% jitter. On the regular layout, its zeroth-moment \(L_2\)
error was 0.25257 and its manufactured Laplacian \(L_2\) error was 20.0198,
compared with 0.00041575 and 3.80765 at `verletScale=1.0`. The evidence is
`06_experiments/stage_01b_operator_verification/results/upstream_default_neighbor_diagnostic.csv`.

Tests:
`tests/test_kernel_moments.py` and
`tests/test_periodic_neighbor_reciprocity.py`.

## 4. Manufactured differential operators

The periodic manufactured fields in
`01_solver/manufactured_fields/periodic.py` are

\[
f(x,y)=\sin(2\pi x)+\tfrac12\cos(2\pi y),
\]
\[
\nabla f=(2\pi\cos(2\pi x),-\pi\sin(2\pi y)),
\]
\[
\nabla^2 f=-4\pi^2\sin(2\pi x)-2\pi^2\cos(2\pi y),
\]

and

\[
\mathbf v=(\sin(2\pi x),\cos(2\pi y)),\qquad
\nabla\cdot\mathbf v
=2\pi\cos(2\pi x)-2\pi\sin(2\pi y).
\]

The constant-field gradient and Laplacian checks returned exact zeros in the
tested float32 path. Manufactured gradient and divergence \(L_2\) errors
decreased from \(16^2\) to \(32^2\) on all three layouts. Representative
sequences are:

| Operator/layout | \(16^2\) | \(24^2\) | \(32^2\) |
|---|---:|---:|---:|
| gradient, regular | 0.81914 | 0.39137 | 0.22732 |
| gradient, 10% jitter | 0.82395 | 0.40685 | 0.24501 |
| divergence, regular | 1.46532 | 0.70010 | 0.40664 |
| divergence, 10% jitter | 1.46294 | 0.71665 | 0.42340 |

The B-path physical-\(\nu\) generic Laplacian behaved differently:

| Layout | \(16^2\) | \(24^2\) | \(32^2\) | Last observed order |
|---|---:|---:|---:|---:|
| regular | 3.80765 | 1.79038 | 1.04049 | 1.887 |
| 5% jitter | 3.87465 | 2.18001 | 1.80981 | 0.647 |
| 10% jitter | 4.30739 | 3.01780 | 3.27669 | **-0.286** |

Thus the Laplacian has a regular-layout convergence trend but fails the
preregistered “error decreases with refinement” gate on the 10% jittered
layout. The data are not filtered or relabeled as a pass.

All \(L_1\), \(L_2\), \(L_\infty\), and observed-order rows are in
`06_experiments/stage_01b_operator_verification/results/manufactured_operator_metrics.csv`;
the comparison is plotted in
`06_experiments/stage_01b_operator_verification/figures/manufactured_operator_errors.png`.
The generic interpolation operators, the physical-\(\nu\) viscous Laplacian,
and the configured pressure force are treated as distinct operators.

Tests:
`tests/test_manufactured_gradient.py`,
`tests/test_manufactured_divergence.py`, and
`tests/test_manufactured_laplacian.py`.

## 5. Conservation structure

The instantaneous force audit in
`06_experiments/stage_01b_operator_verification/results/conservation_audit.csv`
shows:

- for uniform density, physical-\(\nu\) viscosity was pairwise antisymmetric
  to float32 resolution, its characteristic-normalized total internal-force
  residual was \(O(10^{-8})\), and viscous power was negative;
- with a 5% density perturbation, the same operator was not pairwise
  antisymmetric. On regular layouts, the normalized internal-force residual
  was 0.01103, 0.007592 and 0.005761 for \(16^2,24^2,32^2\); comparable
  10%-jitter values were 0.01096, 0.007530 and 0.005751;
- the all-positive-pressure Antuono branch was pairwise/global conservative to
  the documented float32 tolerance;
- when the test pressure crossed zero, Antuono's sign-dependent branch was
  not pairwise antisymmetric. Its normalized global residual on 5% jitter was
  0.005243, 0.0004920 and 0.0003352; on 10% jitter it was 0.003875,
  0.001683 and 0.001019.

The generic viscous force is not generally central, so angular-momentum
conservation does not follow theoretically; measured torque is retained in
the CSV rather than interpreted as an invariant. Viscous power remained
negative for the audited manufactured velocity.

These are force-structure diagnostics, not a substitute for trajectory
momentum drift. Absolute and characteristic-normalized rollout momentum drift
were not generated because V2 was stopped before TGV execution.

The first strict test failure—mixed-sign Antuono pressure on a 5% jittered
layout—and the later float32 threshold-edge observation are preserved in
`06_experiments/stage_01b_operator_verification/logs/v1_first_pytest_failure.txt`.
The final tests explicitly assert that the known nonconservation is detected;
they do not redefine it as conservation:
`tests/test_pairwise_force_antisymmetry.py`.
The plotted residuals are in
`06_experiments/stage_01b_operator_verification/figures/conservation_residuals.png`.

## 6. Time-integrator order

The actual diffSPH integrator interface, with only a minimal state adapter, was
applied to

\[
\frac{dy}{dt}=-1.3y,\qquad y(0)=1,\qquad t_f=1.
\]

For `symplecticEuler`, the absolute errors at
\(\Delta t=0.1,0.05,0.025,0.0125\) were
0.00110247, 0.000262084, \(6.39176\times10^{-5}\), and
\(1.57842\times10^{-5}\). The observed orders were 2.073, 2.036 and 2.018.
Therefore this actual interface behaves as a second-order method on the
audited decay ODE, despite the generic expectation associated with the scheme
name; the measured order is reported without relabeling the implementation.

Evidence:
`06_experiments/stage_01b_operator_verification/results/integrator_order.csv`,
`06_experiments/stage_01b_operator_verification/figures/integrator_order.png`,
`01_solver/verification/integrator_ode.py`, and
`tests/test_integrator_order.py`.

## 7. Fixed-physics TGV time convergence

**NOT RUN.**

The candidate values \(U_0=1\), \(L=2\), \(\nu=0.02\), \(Re=100\),
\(c_s=10\), and nominal \(Ma_0=0.1\), together with the candidate
\(10^{-3},5\times10^{-4},2.5\times10^{-4}\) time-step sequence, were
preregistered before any TGV result was viewed. Execution was prohibited when
V1 exposed the 10%-jittered kernel/Laplacian failures, force-structure
limitations, and multi-step autograd failure. Consequently:

- no fixed-physics TGV trajectory was produced;
- no velocity, kinetic-energy, density-fluctuation or momentum-drift time
  series exists for Stage 01B;
- no monotonic time-error trend or empirical TGV time order is claimed.

The branch disposition is documented in
`07_reports/stage_01b_time_convergence.md`.

## 8. Fixed-physics TGV space convergence

**NOT RUN.**

The spatial branch depended on both V1 qualification and selection of a
uniform time step from a successful time-convergence study. Neither gate was
satisfied. No \(16^2/24^2/32^2\) fixed-physics TGV space series, shuffled-layout
comparison or observed TGV spatial order was generated. The manufactured
operator study in Section 4 must not be presented as TGV solution
convergence.

The branch disposition is documented in
`07_reports/stage_01b_space_convergence.md`.

## 9. Numerical uncertainty

The uncertainty components can only be bounded qualitatively at this gate:

1. **time discretization:** not estimated for TGV because the time branch was
   not run;
2. **space discretization:** not estimated for TGV because the space branch
   was not run, and the 10%-jitter Laplacian is nonmonotonic;
3. **CPU repeatability:** no new Stage 01B TGV repeatability ensemble exists;
   Stage 01 repeatability belongs to V0 and cannot substitute for V2;
4. **float32/backend effects:** pair residuals near \(10^{-8}\) demonstrate a
   float32 floor in some symmetric cases; no Stage 01B CPU/MPS fixed-physics
   backend comparison was performed;
5. **model form:** the weakly compressible formulation is not identical to
   the incompressible Taylor–Green analytic model;
6. **particle disorder:** the kernel, Laplacian and conservation CSVs show
   material sensitivity, including the finest-grid 10%-jitter rebound.

The monotonic/asymptotic prerequisites for Richardson extrapolation and a GCI
are absent. **GCI not justified.** No numerical uncertainty percentage is
reported. See `07_reports/stage_01b_uncertainty_assessment.md`.

## 10. Automatic-differentiation scope

The original Stage 01 initial-velocity-amplitude, three-step value-path check
remains a V0 result in `07_reports/stage_01_gradient_check.md`.

Stage 01B separately requested gradients with respect to explicit physical
viscosity and one local velocity component over 3, 5 and 8 steps. All six
backward cases failed before a valid automatic-differentiation gradient norm
could be produced. In the pinned upstream
`diffSPH/sphOperations/laplacian.py:1062` custom backward,
`laplacian_fn` at line 925 receives `h_i=None`, leading to:

```text
TypeError: unsupported operand type(s) for *: 'float' and 'NoneType'
```

The complete sanitized stack from the first failure is preserved in
`06_experiments/stage_01b_operator_verification/logs/autograd_multistep_failure.txt`;
all six sanitized stacks are preserved in
`06_experiments/stage_01b_operator_verification/logs/autograd_scope_failures.txt`.
The per-case diagnostics in
`06_experiments/stage_01b_operator_verification/results/autograd_scope.csv`
record `status=FAIL`, `autograd_status=FAIL`, `gradient_norm=NaN`, and
`finite_difference_status=PASS` for every case. The independently evaluated
finite-difference sensitivities were:

| Parameter | 3 steps | 5 steps | 8 steps |
|---|---:|---:|---:|
| physical \(\nu\) | -0.0138581 | -0.0230968 | -0.0370294 |
| local \(v_x\), particle 0 | -0.000745058 | -0.000745058 | -0.000745058 |

Thus the losses are observably sensitive to both inputs, but no AD/finite-
difference agreement can be calculated because the AD values are invalid.
The failed gradients must not be read as zero gradients. No upstream package
patch was applied.

The only differentiability statement retained is narrow: where backward
succeeds, it concerns the value path for fixed neighbor indices. Neighbor
creation and topology changes with position are discrete/non-smooth and have
not been shown differentiable. Full particle-topology differentiability is
not claimed.

Source and test:
`01_solver/verification/autograd_scope.py` and
`tests/test_stage01b_autograd_scope.py`.

## 11. Known failures and limitations

1. The original reachable DeltaSPH artificial-viscosity alpha is hard-coded;
   its later configuration read is unreachable.
2. The official notebook alpha-to-\(\nu\) mapping is not an exact fixed
   physical-viscosity control law.
3. Upstream neighborhood `verletScale=1.4` produced thousands of duplicate
   edges in the audited \(16^2\) layouts.
4. Zeroth kernel consistency is nonmonotonic under disorder and worsens at
   \(32^2\) for 10% jitter.
5. The physical-\(\nu\) manufactured Laplacian rebounds at \(32^2\) for 10%
   jitter; its last observed order is -0.286.
6. The physical-\(\nu\) generic Laplacian is not strictly force-conservative
   under variable density.
7. The mixed-sign Antuono pressure branch is not pairwise conservative on
   disordered layouts.
8. The generic viscous force is not generally central, so angular momentum is
   not theoretically guaranteed.
9. All requested 3/5/8-step explicit-\(\nu\) and local-state value-path
   backward cases fail in the pinned upstream custom Laplacian backward
   because `h_i` is `None`; finite differences remain finite and nonzero.
10. Fixed-physics TGV time/space convergence, trajectory momentum drift,
    backend comparison, and V2 uncertainty bounds were not run after the V1
    gate failed.

The final full test command was:

```text
python -m pytest -q -W error
```

It completed with **69 passed in 7.23 s**. The machine-readable JUnit record
is `06_experiments/stage_01b_operator_verification/logs/pytest_werror.xml`.
Green tests mean the measurements
and known-failure assertions are reproducible; they do not change the
physical V1 verdict. In particular, the conservation tests pass by detecting
the recorded nonconservation, and the AD test passes by verifying that all
six upstream-backward failures and the independently finite finite-difference
sensitivities are retained.

The 430 warnings in the preserved Stage 01 baseline
`06_experiments/stage_01_tgv/logs/final_pytest.txt` classify exactly as 423
PyTorch `torch.jit.script` deprecations, four diffSPH default-support
configuration warnings, and three PyTorch checkpoint no-gradient-input
warnings. Project-originated warnings in that baseline were zero.

`pytest.ini` first promotes all warnings to errors, then applies only three
exact source/type filters for confirmed upstream behavior:

- `DeprecationWarning` from `torch.jit._script` for the
  `torch.jit.script` deprecation;
- `UserWarning` from `torch.utils.checkpoint` when none of that upstream
  call's inputs require gradients;
- `UserWarning` from `diffSPH.regions` for its default support
  configuration.

No global warning suppression is used. Root `conftest.py` reapplies the same
three exact filters as per-test markers so the literal command-line
`-W error` check cannot override them; `tests/conftest.py` only adds the
project solver source directory to the test import path.

## 12. Current V0/V1/V2/V3 status

| Level | Status | Evidence-based meaning |
|---|---|---|
| V0 | **CONDITIONAL PASS** | Official chain executable; CPU canonical; hybrid MPS/CPU neighborhood path; narrow three-step value-path AD |
| V1 | **FAIL** | Quantitative diagnostics completed, but preregistered consistency and multi-step AD stop rules failed; conservation limitations also remain |
| V2 | **NOT RUN / NOT QUALIFIED** | Time and space TGV branches were closed by V1; no solution/physical convergence claim |
| V3 | **NOT STARTED** | No independent reference qualification or benchmark hierarchy |

The only permitted Stage 01B terminal label is:

**`V1_FAIL`**

## 13. Stage 02 decision

**Stage 02 may not be designed or started.**

This prohibition includes neural-network training, MLP/Transformer
implementation, training-label generation, and designation of teacher or
student solvers. Work stops at Stage 01B. A later continuation would require
an explicit new authorization and a reviewed response to the V1 failures; it
cannot reinterpret the current artifacts as a V2 pass.

## 14. Evidence and artifact index

### Reports

- `07_reports/stage_01_scope_reclassification.md`
- `07_reports/stage_01_solver_validation.md` (preserved Stage 01)
- `07_reports/stage_01_gradient_check.md` (preserved Stage 01 AD scope)
- `07_reports/stage_01b_viscosity_parameter_audit.md`
- `07_reports/stage_01b_operator_verification.md`
- `07_reports/stage_01b_time_convergence.md`
- `07_reports/stage_01b_space_convergence.md`
- `07_reports/stage_01b_uncertainty_assessment.md`
- `07_reports/stage_01b_final_vv_report.md`

### Machine-readable results

- `06_experiments/stage_01b_operator_verification/results/layout_hashes.csv`
- `06_experiments/stage_01b_operator_verification/results/kernel_moment_metrics.csv`
- `06_experiments/stage_01b_operator_verification/results/neighborhood_audit.csv`
- `06_experiments/stage_01b_operator_verification/results/upstream_default_neighbor_diagnostic.csv`
- `06_experiments/stage_01b_operator_verification/results/manufactured_operator_metrics.csv`
- `06_experiments/stage_01b_operator_verification/results/conservation_audit.csv`
- `06_experiments/stage_01b_operator_verification/results/integrator_order.csv`
- `06_experiments/stage_01b_operator_verification/results/autograd_scope.csv`

There are deliberately no Stage 01B fixed-physics TGV time- or
space-convergence result CSVs.

### Figures

- `06_experiments/stage_01b_operator_verification/figures/kernel_moment_errors.png`
- `06_experiments/stage_01b_operator_verification/figures/manufactured_operator_errors.png`
- `06_experiments/stage_01b_operator_verification/figures/conservation_residuals.png`
- `06_experiments/stage_01b_operator_verification/figures/integrator_order.png`

There are deliberately no Stage 01B TGV time/space-convergence figures.

### Configuration and source

- `01_solver/verification/fixed_physics_tgv.py`
- `06_experiments/stage_01b_fixed_physics_tgv/configs/preregistered_fixed_physics.yml`
- `01_solver/viscosity_audit/audit_viscosity_paths.py`
- `01_solver/viscosity_audit/physical_nu_adapter.py`
- `01_solver/manufactured_fields/periodic.py`
- `01_solver/verification/operator_tools.py`
- `01_solver/verification/run_operator_verification.py`
- `01_solver/verification/integrator_ode.py`
- `01_solver/verification/autograd_scope.py`
- `pytest.ini`
- `conftest.py`

The YAML is explicitly marked `PREREGISTERED_NOT_EXECUTED` with
`v2_authorized: false`; it records the frozen proposal and is not evidence of
a run. No V2/TGV execution was authorized after the V1 stop.

### Tests

- `tests/test_kernel_moments.py`
- `tests/test_periodic_neighbor_reciprocity.py`
- `tests/test_manufactured_gradient.py`
- `tests/test_manufactured_divergence.py`
- `tests/test_manufactured_laplacian.py`
- `tests/test_pairwise_force_antisymmetry.py`
- `tests/test_integrator_order.py`
- `tests/test_fixed_physics_configuration.py`
- `tests/test_stage01b_autograd_scope.py`
- `tests/conftest.py`

### Preserved logs and dynamic probes

- `06_experiments/stage_01b_operator_verification/logs/viscosity_parameter_probe.json`
- `06_experiments/stage_01b_operator_verification/logs/viscosity_parameter_probe_import_failure.txt`
- `06_experiments/stage_01b_operator_verification/logs/v1_first_pytest_failure.txt`
- `06_experiments/stage_01b_operator_verification/logs/autograd_multistep_failure.txt`
- `06_experiments/stage_01b_operator_verification/logs/autograd_scope_failures.txt`
- `06_experiments/stage_01b_operator_verification/logs/pytest_werror.xml`

No Stage 00 or Stage 01 report, raw result, log or failure record was changed
by this report.
