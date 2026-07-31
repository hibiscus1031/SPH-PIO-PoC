# Stage 01C failure taxonomy and minimal reproductions

Date: 2026-07-31

Scope: classification and minimal reproduction of the seven Stage 01B
failures; no TGV execution

## 1. Frozen baseline and evidence policy

This report is a new Stage 01C artifact. It does not modify, replace, copy, or
reinterpret any Stage 01B report, CSV, log, result, source file, or failure
record. Numerical excerpts below identify the relevant frozen rows; the
authoritative values remain in the referenced Stage 01B artifacts.

The frozen baseline is:

- project commit:
  `6f26750fea615c79b08a11fddfd832105b985235`;
- annotated tag: `stage-01b-v1-fail`;
- pinned diffSPH commit:
  `fff180c81d57a51035de9f4d358dbcaccf973928`;
- diffSPH version: `0.2.1`;
- Stage 01B result: quantitative V1 diagnostics completed, V1 qualification
  failed, and V2 was not run.

No command in this report writes to a Stage 01B path. Commands that reproduce
failure observations either print to standard output or execute a test that
passes only when the known failure is detected. No TGV case was run while
preparing this taxonomy.

The principal frozen evidence is:

- `07_reports/stage_01b_operator_verification.md`;
- `07_reports/stage_01b_viscosity_parameter_audit.md`;
- `06_experiments/stage_01b_operator_verification/results/`
  `upstream_default_neighbor_diagnostic.csv`;
- `06_experiments/stage_01b_operator_verification/results/`
  `kernel_moment_metrics.csv`;
- `06_experiments/stage_01b_operator_verification/results/`
  `manufactured_operator_metrics.csv`;
- `06_experiments/stage_01b_operator_verification/results/`
  `conservation_audit.csv`;
- `06_experiments/stage_01b_operator_verification/results/`
  `autograd_scope.csv`;
- `06_experiments/stage_01b_operator_verification/logs/`
  `viscosity_parameter_probe.json`;
- `06_experiments/stage_01b_operator_verification/logs/`
  `autograd_multistep_failure.txt`;
- `06_experiments/stage_01b_operator_verification/logs/`
  `autograd_scope_failures.txt`;
- `06_experiments/stage_01b_operator_verification/logs/`
  `v1_first_pytest_failure.txt`.

## 2. Classification system

The five allowed classifications are used as follows.

### 2.1 `upstream implementation defect`

The executed upstream code violates an interface contract or a structural
invariant even though the input is valid. Examples include a valid
neighborhood search producing duplicate directed edges, a configuration value
being bypassed by a hard-coded literal, and a backward implementation
reconstructing its arguments in the wrong order.

### 2.2 `discretization limitation`

The code evaluates its stated discrete formula, but that formula does not
possess a required mathematical property for the state under test. Lack of
pair antisymmetry caused by one-sided density weighting or a sign-dependent
pressure coefficient is a discretization limitation, not an implementation
crash.

### 2.3 `statistical evidence limitation`

The measured realization is valid, but the sampling design is insufficient
to support a population-level or ensemble-level conclusion. A single random
seed at three resolutions can disqualify that exact tested path, but it cannot
establish that every realization or the ensemble mean systematically rebounds.

### 2.4 `configuration issue`

A parameter value or operator selection triggers or exposes the problem.
This label is secondary when a valid/default setting exposes an upstream
invariant violation, or when a working but structurally unsuitable operator is
selected for a conservation-qualified use.

### 2.5 `unresolved`

The available evidence cannot yet distinguish competing causes. This label is
used as a secondary qualification for the ensemble-level cause of the two
single-seed disorder observations. It is not used to weaken source-level
defects whose mechanisms are already identified.

Multiple labels are permitted, but the primary classification identifies the
failure mechanism that the current evidence most directly supports.

## 3. Executive taxonomy

| ID | Stage 01B observation | Primary classification | Secondary labels | Confidence |
|---|---|---|---|---|
| F01 | `verletScale=1.4` produces duplicate periodic edges | `upstream implementation defect` | `configuration issue`; exact upstream component ownership remains secondary | High |
| F02 | reachable viscosity hard-codes alpha and the configuration read is unreachable | `upstream implementation defect` | `configuration issue` | High |
| F03 | generic Laplacian backward receives `h_i=None` | `upstream implementation defect` | none | High |
| F04 | 10% jitter zeroth kernel moment rebounds at the finest grid | `statistical evidence limitation` | `discretization limitation` candidate; ensemble cause `unresolved` | High for the observed realization; insufficient for a universal claim |
| F05 | 10% jitter manufactured Laplacian rebounds at the finest grid | `statistical evidence limitation` | `discretization limitation` candidate; ensemble cause `unresolved` | High for the observed realization; insufficient for a universal claim |
| F06 | generic-Laplacian viscosity is not pair conservative at variable density | `discretization limitation` | candidate/operator-selection `configuration issue` | High |
| F07 | mixed-sign Antuono pressure is not pair conservative | `discretization limitation` | operator-selection `configuration issue` | High |

This separation is essential. F01--F03 are implementation-level failures in
the upstream execution stack. F06--F07 follow from the algebraic structure of
the selected discrete forces even when their code executes normally. F04--F05
are exact observations from one preregistered realization, but their
ensemble-level interpretation is statistically underdetermined.

## 4. Reproduction conventions

All commands are run from the project root in the existing isolated
`sph-pio-poc` environment. `PYTHONDONTWRITEBYTECODE=1` prevents new bytecode
cache files. The commands do not specify a Stage 01B output path.

The Stage 01B static layouts use CPU float32, domain length \(L=2\),
\(H/dx=4\), and the qualified `verletScale=1.0` path except where F01
explicitly compares 1.4 with 1.0. The 10% jitter layout uses seed `20260811`.
The exact position hashes are retained in:

`06_experiments/stage_01b_operator_verification/results/layout_hashes.csv`.

## 5. F01 — duplicate periodic edges at `verletScale=1.4`

### 5.1 Minimal reproduction entry

The existing in-memory diagnostic is:

- `01_solver/verification/run_operator_verification.py:256`,
  `collect_upstream_default_diagnostic`;
- `01_solver/verification/operator_tools.py:205`,
  `neighborhood_audit`.

A non-overwriting reproduction command is:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=01_solver \
conda run -n sph-pio-poc python -c \
"from verification.run_operator_verification import collect_upstream_default_diagnostic as f; print(f().to_string(index=False))"
```

### 5.2 Frozen numerical signature

The frozen source is:

`06_experiments/stage_01b_operator_verification/results/`
`upstream_default_neighbor_diagnostic.csv`.

| Layout, 16 particles/axis | `verletScale` | Edges | Unique edges | Duplicate edges | \(S_0\) L2 | Laplacian L2 |
|---|---:|---:|---:|---:|---:|---:|
| regular | 1.4 | 18,096 | 12,544 | 5,552 | 0.252573639 | 20.019824982 |
| regular | 1.0 | 11,520 | 11,520 | 0 | 0.000415749 | 3.807647467 |
| 5% jitter | 1.4 | 17,318 | 12,040 | 5,278 | 0.253224611 | 20.024097443 |
| 5% jitter | 1.0 | 12,040 | 12,040 | 0 | 0.009243255 | 3.874646425 |
| 10% jitter | 1.4 | 17,562 | 12,182 | 5,380 | 0.254911423 | 20.068666458 |
| 10% jitter | 1.0 | 12,182 | 12,182 | 0 | 0.017911166 | 4.307393551 |

The repeated \((i,j)\) keys are accumulated repeatedly by kernel and
Laplacian reductions. Search padding therefore changes the physical operator,
which is not a valid Verlet-list behavior.

### 5.3 Source mechanism and classification

At the pinned diffSPH commit:

- `src/diffSPH/schema.py:38` declares `verletScale=1.4` as the default;
- `src/diffSPH/neighborhood.py:416-418` multiplies the particle supports by
  `verletScale` and delegates the search to `torchCompactRadius.radiusSearch`;
- `src/diffSPH/neighborhood.py:560-571` filters the resulting list back to
  physical support but does not make directed keys unique.

A read-only source trace of the installed `torchCompactRadius 0.5.5` path
shows that periodic cell offsets are individually wrapped modulo the number
of cells and are then queried without deduplicating wrapped cell indices. In
the representative 16-by-16 regular case, the 1.4 path formed a two-by-two
periodic cell grid; negative and positive adjacent offsets can therefore map
to the same cell. The corresponding 1.0 path formed a four-by-four cell grid
and did not exhibit this alias.

The primary classification is **`upstream implementation defect`**. A
neighbor list must contain each directed physical pair at most once for a
valid default search setting. `verletScale=1.4` is the trigger and
`verletScale=1.0` is a project-level avoidance, so
**`configuration issue`** is only a secondary label. Whether the permanent
fix is owned by diffSPH, torchCompactRadius, or both is a component-ownership
question; it does not make the observed invariant violation unresolved.

### 5.4 Evidence boundary

The data prove duplicate directed edges and their numerical effect for the
tested upstream stack. They do not prove that every torchCompactRadius
algorithm or every domain decomposition has the same defect. Stage 01C must
still audit uniqueness, reciprocity, strict-interior completeness, and
minimum-image displacement on every new layout.

## 6. F02 — hard-coded alpha and unreachable configuration

### 6.1 Minimal reproduction entry

The probe is:

- `01_solver/viscosity_audit/audit_viscosity_paths.py:38`, `run_probe`.

It prints JSON without writing a project file when `--output` is omitted:

```bash
PYTHONDONTWRITEBYTECODE=1 \
conda run -n sph-pio-poc python \
01_solver/viscosity_audit/audit_viscosity_paths.py --resolution 16
```

### 6.2 Frozen source and numerical signature

The authoritative machine-readable record is:

`06_experiments/stage_01b_operator_verification/logs/`
`viscosity_parameter_probe.json`.

It records the installed source SHA-256:

`e5e40801372a7ce6712c518046fb7b479a91f026958e04efbc9f7d875d528b16`.

At `src/diffSPH/modules/velocityDiffusion.py`:

- line 94 sets
  `alpha = alphaOverride if alphaOverride is not None else 0.01`;
- lines 106--116 return the acceleration unconditionally;
- line 122 attempts to read `config["diffusion"]["alpha"]`, but is after the
  unconditional return and is unreachable.

For configured alpha values 0, 0.01, and 1:

- all three outputs are bitwise equal;
- the maximum absolute difference from the 0.01 result is exactly 0 for all
  three values.

The explicit `alphaOverride` control produces:

| `alphaOverride` | Output L2 | Output Linf |
|---:|---:|---:|
| 0 | 4.283078671 | 0.650535166 |
| 0.01 | 12.370584488 | 1.737327814 |
| 1 | 822.122192383 | 109.329826355 |

The override comparison proves that the callable can respond to an explicit
argument while the configuration path cannot. `alphaOverride=0` remaining
nonzero is a separate artificial-viscosity fact: the wrapper overrides the
linear coefficient \(C_l\), while the quadratic coefficient remains
\(C_q=2\). It must not be used as the proof of the unreachable configuration
read.

### 6.3 Classification

The primary classification is **`upstream implementation defect`**. The
reachable function contradicts the apparent configuration contract, and
executable statements after an unconditional return cannot propagate the
value. **`configuration issue`** is secondary because downstream code can
record or set alpha while the force ignores it.

This is not a discretization-error finding. It is also not repaired by
calibrating an alpha-to-physical-viscosity formula: calibration cannot make an
unreachable input control the executed operator.

## 7. F03 — generic Laplacian backward receives `h_i=None`

### 7.1 Minimal reproduction entry

The smallest existing value-path trigger uses the three-step viscosity loss:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=01_solver \
conda run -n sph-pio-poc python -c \
"import torch; from verification.autograd_scope import viscosity_loss; x=torch.tensor(0.02,dtype=torch.float32,requires_grad=True); viscosity_loss(x,3).backward()"
```

This command is expected to return nonzero with the preserved `TypeError`. The
six-case diagnostic entry is:

- `01_solver/verification/autograd_scope.py:157`,
  `run_autograd_scope_with_failures`.

The regression test is:

```bash
PYTHONDONTWRITEBYTECODE=1 \
conda run -n sph-pio-poc python -m pytest -q -p no:cacheprovider \
tests/test_stage01b_autograd_scope.py::test_stage01b_short_rollout_exposes_upstream_backward_failure
```

That test passes only when all known upstream failures and the successful
finite-difference controls are exposed.

### 7.2 Frozen numerical and exception signature

Evidence:

- `06_experiments/stage_01b_operator_verification/results/`
  `autograd_scope.csv`;
- `06_experiments/stage_01b_operator_verification/logs/`
  `autograd_multistep_failure.txt`;
- `06_experiments/stage_01b_operator_verification/logs/`
  `autograd_scope_failures.txt`.

All six physical-viscosity and local-velocity cases at 3, 5, and 8 steps have:

- AD status `FAIL`;
- AD gradient and gradient norm `NaN`;
- centered finite-difference status `PASS`;
- exception:
  `TypeError: unsupported operand type(s) for *: 'float' and 'NoneType'`;
- origin:
  `diffSPH/sphOperations/laplacian.py:1062 -> laplacian.py:925`.

The finite-difference gradients are:

| Parameter | 3 steps | 5 steps | 8 steps |
|---|---:|---:|---:|
| physical viscosity | -0.013858080 | -0.023096800 | -0.037029386 |
| local \(v_x\), particle 0 | -0.000745058 | -0.000745058 | -0.000745058 |

The finite, nonzero finite differences prove value sensitivity but do not
convert the failed AD path into a differentiable implementation.

### 7.3 Exact source mechanism and classification

In the pinned `src/diffSPH/sphOperations/laplacian.py`:

- forward line 1032 constructs the particle-i inputs in the order
  `quantity, densities, omega, supports, ...`;
- backward line 1057 reconstructs them in the different order
  `quantity, densities, supports, omega, ...`;
- `laplacian_fn` lines 808--827 expect
  `q_i, rho_i, omega_i, h_i, ...`.

Consequently, backward supplies the optional omega value in the `h_i`
position. In this path omega is `None`, and line 925 evaluates
`1e-8 * h_i`.

The primary and sole classification is
**`upstream implementation defect`**. The forward discrete Laplacian
evaluates and centered finite differences are finite; the observed failure is
an argument-order defect in the custom backward. It must not be described as
a general impossibility of differentiating SPH.

## 8. F04 — 10% jitter zeroth kernel-moment rebound

### 8.1 Minimal reproduction entry

The in-memory entry points are:

- `01_solver/verification/run_operator_verification.py:89`,
  `collect_operator_data`;
- `01_solver/verification/operator_tools.py:171`, `kernel_moments`.

A non-overwriting command is:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=01_solver \
conda run -n sph-pio-poc python -c \
"from verification.run_operator_verification import collect_operator_data as f; d=f()[1]; print(d[d.layout.eq('jitter_10')].to_string(index=False))"
```

### 8.2 Frozen numerical signature

Evidence:

- `06_experiments/stage_01b_operator_verification/results/`
  `kernel_moment_metrics.csv`;
- `06_experiments/stage_01b_operator_verification/results/`
  `layout_hashes.csv`.

For the single 10% jitter realization, seed `20260811`,
`verletScale=1.0`, and \(H/dx=4\):

| Particles/axis | \(S_0\) mean absolute | \(S_0\) L2 | \(S_0\) Linf |
|---:|---:|---:|---:|
| 16 | 0.014547030 | 0.017911166 | 0.050717354 |
| 24 | 0.014027791 | 0.017624710 | 0.062102675 |
| 32 | 0.015230207 | 0.019146495 | 0.078213632 |

The finest L2 is approximately 6.9% larger than the coarsest value. Linf
increases by approximately 54% from 16 to 32 particles per axis. This
rebound is a real property of the frozen realization and is not a rounding
or reporting artifact.

### 8.3 Classification and evidence boundary

The primary classification is **`statistical evidence limitation`**. Stage
01B used one preregistered seed and one realization at each resolution.
Those three samples do not estimate an ensemble mean, standard deviation,
median, confidence interval, or ensemble slope. They cannot establish the
universal claim that the 10% jitter family always rebounds.

The observation remains a **`discretization limitation` candidate** for the
raw kernel with a constant-neighbor family. Holding \(H/dx=4\) does not
increase the nominal neighbor population during refinement, so disorder
sampling error need not decrease in the same way as truncation error on a
regular lattice. Whether the rebound persists in an ensemble or disappears
with an increasing-neighbor consistency family is **`unresolved`** by Stage
01B evidence.

This classification does not reverse the Stage 01B decision: the exact
required realization failed its refinement qualification. It only prevents
that one failure from being overstated as a population-level convergence law.

## 9. F05 — 10% jitter manufactured-Laplacian rebound

### 9.1 Minimal reproduction entry

The relevant entry points are:

- `01_solver/verification/run_operator_verification.py:89`,
  `collect_operator_data`;
- `01_solver/verification/operator_tools.py:148`, `apply_laplacian`;
- `01_solver/manufactured_fields/periodic.py`, `scalar_field` and
  `scalar_laplacian`.

A non-overwriting command is:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=01_solver \
conda run -n sph-pio-poc python -c \
"from verification.run_operator_verification import collect_operator_data as f; d=f()[3]; q=d[(d.layout.eq('jitter_10')) & (d.operator.eq('physical_nu_generic_laplacian'))]; print(q.to_string(index=False))"
```

### 9.2 Frozen numerical signature

The evidence is:

`06_experiments/stage_01b_operator_verification/results/`
`manufactured_operator_metrics.csv`.

| Norm | 16 particles/axis | 24 particles/axis | 32 particles/axis | \(p_{16\to24}\) | \(p_{24\to32}\) |
|---|---:|---:|---:|---:|---:|
| L1 | 3.755604982 | 2.484923840 | 2.574597359 | 1.018602 | -0.123230 |
| L2 | 4.307393551 | 3.017804861 | 3.276685715 | 0.877519 | -0.286089 |
| Linf | 8.237064362 | 8.134393692 | 13.826293945 | 0.030934 | -1.843949 |

All three norms rebound at the finest refinement. The L2 error rises by
approximately 8.6% from 24 to 32 particles per axis.

### 9.3 Classification and evidence boundary

The primary classification is **`statistical evidence limitation`** for the
claim of systematic family-wide nonconvergence. The same single-seed,
three-resolution limitation as F04 applies.

The stronger norm-wise rebound and the use of an uncorrected generic
Laplacian make **`discretization limitation`** a material secondary
candidate. Particle disorder affects both kernel quadrature and the
differential approximation, while the fixed \(H/dx\) family does not increase
neighbor sampling. Stage 01B did not isolate those effects from float32
accumulation or random-realization variability. Their relative contributions
and the ensemble-level trend are therefore **`unresolved`**.

The result proves that this exact generic-Laplacian path did not qualify at
10% jitter. It does not prove that every consistent support-scaling family or
every corrected Laplacian must fail.

## 10. F06 — variable-density viscosity is not pair conservative

### 10.1 Minimal reproduction entry

The audit is:

- `01_solver/verification/operator_tools.py:278`,
  `viscous_conservation_audit`;
- regression test:
  `tests/test_pairwise_force_antisymmetry.py:32`.

```bash
PYTHONDONTWRITEBYTECODE=1 \
conda run -n sph-pio-poc python -m pytest -q -p no:cacheprovider \
tests/test_pairwise_force_antisymmetry.py::test_variable_density_nonconservation_is_detected_not_hidden
```

The test passes only when a nonzero variable-density defect is measured. It
is not a conservation-pass test.

### 10.2 Frozen numerical signature

Evidence:

`06_experiments/stage_01b_operator_verification/results/`
`conservation_audit.csv`.

Representative 24-by-24, 5% jitter results are:

| Density state | Pair-force residual L2 | Pair-force residual Linf | Total internal force | Normalized total force | Viscous power |
|---|---:|---:|---:|---:|---:|
| uniform | \(2.8780\times10^{-10}\) | \(3.9581\times10^{-9}\) | \(4.5742\times10^{-8}\) | \(4.6525\times10^{-9}\) | -2.975682259 |
| 5% perturbation | \(9.8356\times10^{-6}\) | \(6.3758\times10^{-5}\) | 0.074532926 | 0.007572107 | -2.977264166 |

Across all tested layouts, the variable-density normalized residual remains
approximately \(5.75\times10^{-3}\) to \(1.10\times10^{-2}\). Negative power
for the tested field establishes dissipation in that state, but dissipation
does not imply linear-momentum conservation.

### 10.3 Formula mechanism and classification

The Stage 01B generic-Laplacian edge acceleration has the structure

\[
\mathbf a_{ij}^{\nu}
\propto
\frac{m_j}{\rho_j}
(\mathbf v_j-\mathbf v_i)K_{ij},
\qquad
\mathbf f_{ij}^{\nu}=m_i\mathbf a_{ij}^{\nu}.
\]

For the reverse edge,

\[
\mathbf f_{ji}^{\nu}
\propto
\frac{m_im_j}{\rho_i}
(\mathbf v_i-\mathbf v_j)K_{ji}.
\]

Even with a symmetric radial kernel factor, unequal \(\rho_i\) and
\(\rho_j\) give unequal force magnitudes. The generic difference Laplacian
therefore does not imply mass-weighted pair antisymmetry under variable
density.

The primary classification is **`discretization limitation`**. The generic
Laplacian executes its intended one-sided volume weighting; it was not an API
whose contract guaranteed a conservative molecular-viscosity force.
Selecting it as the Stage 01B physical-viscosity candidate is a secondary
operator-selection **`configuration issue`**, not an upstream implementation
defect.

The project-side replacement must obtain pair antisymmetry from its forward
formula. Post hoc antisymmetric projection would not reclassify or explain
the original operator.

## 11. F07 — mixed-sign Antuono pressure is not pair conservative

### 11.1 Minimal reproduction entry

The audit is:

- `01_solver/verification/operator_tools.py:383`,
  `pressure_conservation_audit`;
- regression test:
  `tests/test_pairwise_force_antisymmetry.py:61`.

```bash
PYTHONDONTWRITEBYTECODE=1 \
conda run -n sph-pio-poc python -m pytest -q -p no:cacheprovider \
tests/test_pairwise_force_antisymmetry.py::test_antuono_mixed_pressure_nonconservation_is_detected
```

This test passes by exposing the known nonconservation.

### 11.2 Frozen numerical signature

Evidence:

- `06_experiments/stage_01b_operator_verification/results/`
  `conservation_audit.csv`;
- `06_experiments/stage_01b_operator_verification/logs/`
  `v1_first_pytest_failure.txt`.

Representative 24-by-24, 5% jitter results are:

| Pressure state | Pressure range | Pair residual L2 | Pair residual Linf | Total internal force | Normalized total force |
|---|---|---:|---:|---:|---:|
| all positive | 0.513947 to 1.486182 | \(2.6665\times10^{-9}\) | \(2.3283\times10^{-8}\) | \(3.2859\times10^{-7}\) | \(4.6896\times10^{-8}\) |
| mixed sign | -0.486058 to 0.486183 | \(6.1641\times10^{-4}\) | 0.004471893 | 0.003536242 | 0.000492038 |

The original strict test exposed
\(4.9203808885\times10^{-4} > 2\times10^{-6}\). Across jittered Stage 01B
rows, mixed-sign normalized residuals reach \(5.2425\times10^{-3}\), while
pair Linf residuals range from approximately \(2.52\times10^{-3}\) to
\(8.41\times10^{-3}\).

### 11.3 Formula mechanism and classification

At `src/diffSPH/modules/pressureForce.py:50-56`, the Antuono branch uses

```python
switch = p_i >= 0.0
p_ij = torch.where(switch, p_j + p_i, p_j - p_i)
```

For an edge with one negative and one positive endpoint, reversing the edge
changes which pressure controls the switch. The two directions therefore use
different scalar coefficients. The symmetric kernel gradient reverses sign,
but the unequal coefficients prevent
\(\mathbf f_{ij}^{p}=-\mathbf f_{ji}^{p}\).

Regular particle symmetry can make the summed global force small even while
individual pair residuals remain nonzero. The pair metric, not global
cancellation on a regular lattice, identifies the structural defect.

The primary classification is **`discretization limitation`**. The code
implements the stated sign-dependent branch and executes without an
implementation exception; the branch itself lacks pair antisymmetry for
mixed-sign pressure. Selecting Antuono for a mixed-sign,
conservation-qualified state is a secondary operator-selection
**`configuration issue`**.

## 12. Cross-category remediation boundary

The taxonomy determines what kind of response can legitimately requalify each
failure.

| IDs | Required response | Response that is insufficient |
|---|---|---|
| F01 | project-owned unique directed-pair construction plus complete topology audit | accepting duplicate accumulation or merely loosening a numerical threshold |
| F02 | bypass the unusable alpha path and expose explicit physical viscosity in project code | calibrating the hard-coded alpha as if configuration reached the force |
| F03 | native PyTorch value path whose backward is formed by ordinary tensor operations | catching the upstream exception or replacing missing AD values with FD |
| F04--F05 | preregistered multi-seed ensemble, both support-scaling families, confidence intervals, slope, and float32/float64 isolation | inferring a universal trend from the single frozen seed |
| F06 | symmetric nonnegative pair coefficient that makes the raw forward force antisymmetric at variable density | post hoc antisymmetric projection |
| F07 | explicitly symmetric pair-pressure coefficient valid for positive, negative, and mixed-sign states | relying on global cancellation on a regular layout |

An implementation fix for F01--F03 does not by itself improve kernel or
operator consistency. Conversely, a consistency correction for F04--F05 does
not prove force conservation unless its pair structure satisfies F06--F07.
The categories are therefore complementary, not interchangeable.

## 13. Evidence index and current non-claims

| ID | Frozen machine evidence | Preserved failure/log evidence | Existing test or function entry |
|---|---|---|---|
| F01 | `upstream_default_neighbor_diagnostic.csv` | Section 3 of `stage_01b_operator_verification.md` | `collect_upstream_default_diagnostic` |
| F02 | `viscosity_parameter_probe.json` | `viscosity_parameter_probe_import_failure.txt` retains earlier API/import failures separately | `run_probe` |
| F03 | `autograd_scope.csv` | `autograd_multistep_failure.txt`; `autograd_scope_failures.txt` | `run_autograd_scope_with_failures`; Stage 01B AD regression test |
| F04 | `kernel_moment_metrics.csv`; `layout_hashes.csv` | Section 4 of `stage_01b_operator_verification.md` | `kernel_moments`; `collect_operator_data` |
| F05 | `manufactured_operator_metrics.csv`; `layout_hashes.csv` | Section 5 of `stage_01b_operator_verification.md` | `apply_laplacian`; `collect_operator_data` |
| F06 | `conservation_audit.csv` | Section 6.1 of `stage_01b_operator_verification.md` | variable-density detection test |
| F07 | `conservation_audit.csv` | `v1_first_pytest_failure.txt`; Section 6.2 of `stage_01b_operator_verification.md` | mixed-sign Antuono detection test |

This report completes classification and reproduction mapping only. It does
not claim that a Stage 01C candidate has passed neighborhood, statistical
consistency, conservation, or automatic-differentiation qualification. It
does not replace the required multi-seed, support-scaling,
structure-preserving-operator, or native-autograd evidence. This taxonomy
alone does not reopen V2; that decision depends on the separately evaluated
Stage 01C gates and the final requalification report.
