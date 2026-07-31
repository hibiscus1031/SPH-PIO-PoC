# Stage 01C conservative pressure and viscosity operator qualification

## 1. Scope and evidence

This report qualifies only the project-owned, static pressure and viscosity
operators implemented under `01_solver/structure_preserving/`. It does not
modify the installed diffSPH package. No TGV calculation was run for this
report.

The numerical evidence is:

- `06_experiments/stage_01c_operator_candidates/results/conservation_metrics.csv`;
- `06_experiments/stage_01c_operator_candidates/results/operator_candidate_metrics.csv`;
- `06_experiments/stage_01c_operator_candidates/results/precision_comparison.csv`;
- `06_experiments/stage_01c_operator_candidates/results/stage01c_gate_evidence.csv`;
- `tests/test_stage01c_pressure_antisymmetry.py`;
- `tests/test_stage01c_viscosity_antisymmetry.py`;
- `tests/test_stage01c_viscous_dissipation.py`;
- `tests/test_stage01c_operator_consistency.py`.

`conservation_metrics.csv` contains 2,496 rows. The preregistered primary
float64 matrix contributes 1,800 pressure rows and 600 viscosity rows. The
precision supplement contributes a further 36 pressure and 12 viscosity rows
for each of float64 and float32. The primary matrix covers both support
families, five resolutions, regular/5% jitter/10% jitter layouts, and ten
preregistered seeds.

The six Stage 01C test files were rerun without the pytest cache:

```text
18 passed in 2.67s
```

All residuals below are maxima over the stated CSV subset, not selected
single-run examples. The relative force measures used by the implementation
are

\[
R_{\mathrm{pair}}
=
\frac{\max_{i<j}\lVert\mathbf f_{ij}+\mathbf f_{ji}\rVert}
{\max_{i<j}\lVert\mathbf f_{ij}\rVert+\mathrm{tiny}},
\]

\[
R_{\mathrm{total}}
=
\frac{\left\lVert\sum_i\mathbf F_i\right\rVert}
{2\sum_{i<j}\lVert\mathbf f_{ij}\rVert+\mathrm{tiny}}.
\]

The preregistered C3 tolerances are \(10^{-12}\) for float64 and
\(5\times10^{-6}\) for float32.

## 2. Pair geometry and sign convention

For a reciprocal directed neighborhood, define the minimum-image displacement

\[
\mathbf r_{ij}=\mathbf x_i-\mathbf x_j^{(\mathrm{image})},
\qquad
\mathbf r_{ji}=-\mathbf r_{ij}.
\]

The project kernel uses a single symmetric pair support

\[
H_{ij}=\frac{H_i+H_j}{2}=H_{ji}
\]

and a radial two-dimensional Wendland C4 gradient

\[
\mathbf g_{ij}=\nabla_iW_{ij}.
\]

Because the support is symmetric and the kernel is radial,

\[
\mathbf g_{ji}=-\mathbf g_{ij},
\qquad
\mathbf r_{ji}\cdot\mathbf g_{ji}
=\mathbf r_{ij}\cdot\mathbf g_{ij}\le0.
\]

The force routines evaluate one physical interaction for each unique
unordered pair and accumulate the same raw pair value on particles \(i\) and
\(j\) with opposite signs. The conservation audit is stronger than that
accumulation identity: `pressure_conservation_metrics` and
`viscosity_conservation_metrics` locate the actual reciprocal directed edge,
re-evaluate its kernel gradient, and independently reconstruct
\(\mathbf f_{ji}\). They do not define the audited reverse force by simply
negating \(\mathbf f_{ij}\).

## 3. Conservative pressure operator

### 3.1 Formula and structural proof

The implemented pressure force on \(i\) from \(j\) is

\[
\boxed{
\mathbf f^p_{ij}
=
-m_im_j
\left(
\frac{p_i}{\rho_i^2}
+
\frac{p_j}{\rho_j^2}
\right)
\nabla_iW_{ij}
}.
\]

Let

\[
A_{ij}=\frac{p_i}{\rho_i^2}+\frac{p_j}{\rho_j^2}.
\]

The coefficient is symmetric for positive, negative, and mixed-sign pressure:
\(A_{ji}=A_{ij}\). Evaluation on the actual reciprocal edge therefore gives

\[
\mathbf f^p_{ji}
=-m_jm_iA_{ji}\mathbf g_{ji}
=-\mathbf f^p_{ij}.
\]

Consequently, the total internal pressure force cancels pairwise. The sign of
the pressure changes whether an interaction is attractive or repulsive, but
does not change the conservation proof.

Because the raw symmetric-support kernel gradient is radial,
\(\mathbf f^p_{ij}\parallel\mathbf r_{ij}\). Its minimum-image pair torque is

\[
\tau^p_{ij}
=
\mathbf r_{ij}\times\mathbf f^p_{ij}
=0.
\]

The torque audit uses the minimum-image lever arm. A torque computed directly
from two independently wrapped coordinate representatives would not be an
equivalent periodic-domain quantity.

### 3.2 Pressure matrix

The following maxima cover every positive, negative, and mixed-sign pressure
case under both uniform density and
\(\rho=1+0.05\sin(2\pi x)\). Each float64 cell contains the 300 primary rows
plus six precision-reference rows for that density/pressure combination.
Each float32 cell contains the six preregistered precision cases.

| dtype | density | pressure field | max \(R_{\mathrm{pair}}\) | max \(R_{\mathrm{total}}\) | max relative minimum-image pair torque |
|---|---|---|---:|---:|---:|
| float64 | uniform | positive | 5.627030e-18 | 1.525314e-17 | 3.167966e-16 |
| float64 | uniform | negative | 5.627231e-18 | 1.582326e-17 | 3.249463e-16 |
| float64 | uniform | mixed sign | 5.292258e-18 | 1.611829e-17 | 3.089105e-16 |
| float64 | variable 5% | positive | 2.142755e-18 | 9.942285e-18 | 3.304981e-16 |
| float64 | variable 5% | negative | 5.081097e-18 | 1.090134e-17 | 3.225979e-16 |
| float64 | variable 5% | mixed sign | 1.196307e-18 | 1.528517e-17 | 3.142608e-16 |
| float32 | uniform | positive | 0.000000e+00 | 8.983166e-09 | 1.580199e-07 |
| float32 | uniform | negative | 2.650092e-14 | 5.796890e-09 | 1.514464e-07 |
| float32 | uniform | mixed sign | 1.245303e-14 | 2.500120e-09 | 1.513202e-07 |
| float32 | variable 5% | positive | 2.919891e-14 | 4.390987e-09 | 1.566863e-07 |
| float32 | variable 5% | negative | 2.392815e-14 | 4.475206e-09 | 1.500668e-07 |
| float32 | variable 5% | mixed sign | 1.124874e-14 | 3.732590e-09 | 1.542569e-07 |

Across the complete pressure matrix, the final maxima are:

- float64: \(R_{\mathrm{pair}}=5.627231\times10^{-18}\),
  \(R_{\mathrm{total}}=1.611829\times10^{-17}\), and relative pair torque
  \(3.304981\times10^{-16}\);
- float32: \(R_{\mathrm{pair}}=2.919891\times10^{-14}\),
  \(R_{\mathrm{total}}=8.983166\times10^{-9}\), and relative pair torque
  \(1.580199\times10^{-7}\).

The largest absolute minimum-image pair torque is
\(1.084202\times10^{-19}\) in float64 and
\(1.455192\times10^{-11}\) in float32. All relative values are below their
dtype-specific C3 thresholds. In particular, changing pressure sign or using
variable density does not recreate the mixed-sign Antuono conservation defect
observed in Stage 01B.

`tests/test_stage01c_pressure_antisymmetry.py` separately exercises both
density cases, all three pressure-sign cases, and both dtypes. It asserts the
pair-force, total-force, pair-torque, and total-torque limits for every
combination.

## 4. Conservative physical-viscosity operator

### 4.1 Preregistered \(\Gamma_{ij}\)

The Stage 01C viscosity force is

\[
\boxed{
\mathbf f^\nu_{ij}
=m_im_j\Gamma_{ij}(\mathbf v_j-\mathbf v_i)
}
\]

with the preregistered coefficient

\[
\boxed{
\Gamma_{ij}
=
-\frac{4\nu}{\rho_i+\rho_j}
\frac{\mathbf r_{ij}\cdot\nabla_iW_{ij}}
{r_{ij}^2+(0.01H_{ij})^2}
}.
\]

The physical kinematic viscosity \(\nu\) is an explicit scalar. The
implementation rejects nonfinite or negative \(\nu\), nonpositive or
nonfinite densities/supports, nonfinite geometry, and a radial kernel product
with the wrong sign.

The density sum, pair support, distance, and radial kernel product are
unchanged when \(i\) and \(j\) are exchanged. Thus

\[
\Gamma_{ji}=\Gamma_{ij}.
\]

For the monotone Wendland C4 kernel,

\[
\mathbf r_{ij}\cdot\nabla_iW_{ij}\le0.
\]

With \(\nu\ge0\), \(\rho_i,\rho_j>0\), and a positive denominator, it follows
that

\[
\Gamma_{ij}\ge0.
\]

The measured minimum is numerical signed zero in both dtypes; no negative
\(\Gamma\) was observed. The actual reverse edge was independently evaluated,
and the maximum relative \(\Gamma\)-symmetry residual was
\(2.659611\times10^{-18}\) in float64 and
\(9.716125\times10^{-15}\) in float32.

### 4.2 Viscosity scaling and pair conservation

Since \(\Gamma_{ij}\) is linear in \(\nu\),

\[
\mathbf f^\nu_{ij}\big|_{\nu=0}=0,
\qquad
\mathbf f^\nu_{ij}(2\nu)=2\mathbf f^\nu_{ij}(\nu).
\]

`tests/test_stage01c_viscosity_antisymmetry.py` verifies that the
\(\nu=0\) particle-force tensor has exactly zero nonzero entries and that
\(\mathbf F(0.04)=2\mathbf F(0.02)\) with `rtol=0` and `atol=0`.

Using \(\Gamma_{ji}=\Gamma_{ij}\),

\[
\mathbf f^\nu_{ji}
=m_jm_i\Gamma_{ji}(\mathbf v_i-\mathbf v_j)
=-\mathbf f^\nu_{ij}.
\]

This proof is unchanged by variable density because the density combination
in \(\Gamma\) is pair symmetric.

| dtype | density | max relative \(\Gamma\) asymmetry | max \(R_{\mathrm{pair}}\) | max \(R_{\mathrm{total}}\) |
|---|---|---:|---:|---:|
| float64 | uniform | 2.659611e-18 | 7.298523e-18 | 3.333217e-17 |
| float64 | variable 5% | 2.536649e-18 | 4.611211e-18 | 3.405914e-17 |
| float32 | uniform | 0.000000e+00 | 0.000000e+00 | 7.172363e-09 |
| float32 | variable 5% | 9.716125e-15 | 7.549304e-15 | 1.096742e-08 |

The complete float64/float32 maxima are respectively
\(7.298523\times10^{-18}/7.549304\times10^{-15}\) for pair force and
\(3.405914\times10^{-17}/1.096742\times10^{-8}\) for total force. All are
below the preregistered C3 limits.

### 4.3 Dissipation identity

The particle-accumulated viscous power is

\[
\begin{aligned}
P_\nu
&=\sum_i\mathbf v_i\cdot\mathbf F^\nu_i\\
&=-\sum_{i<j}
m_im_j\Gamma_{ij}
\lVert\mathbf v_j-\mathbf v_i\rVert^2
\le0.
\end{aligned}
\]

The right-hand side is also evaluated directly from unordered pairs, rather
than inferred from the accumulated particle forces.

| dtype | density | accumulated-power range | max absolute difference from pair-direct identity |
|---|---|---:|---:|
| float64 | uniform | [-3.126145, -2.759583] | 8.881784e-16 |
| float64 | variable 5% | [-3.129042, -2.762152] | 8.881784e-16 |
| float32 | uniform | [-3.122012, -2.997231] | 2.384186e-07 |
| float32 | variable 5% | [-3.124829, -3.000070] | 4.768372e-07 |

Every measured power is strictly negative. The largest power, and therefore
the value closest to a possible sign violation, is \(-2.7595834604\) in
float64 and \(-2.9972314835\) in float32. The discrepancies between the two
independent power evaluations are compatible with dtype-dependent
accumulation rounding. `tests/test_stage01c_viscous_dissipation.py` checks
both the nonpositive sign and the power identity.

### 4.4 Angular momentum limitation

The vector \(\mathbf v_j-\mathbf v_i\) is not generally parallel to
\(\mathbf r_{ij}\), so this componentwise Brookshaw viscosity is not a
central-force discretization:

\[
\tau^\nu_{ij}
=m_im_j\Gamma_{ij}
\mathbf r_{ij}\times(\mathbf v_j-\mathbf v_i)
\]

need not vanish. It guarantees linear momentum conservation and nonpositive
viscous power, but does not guarantee angular momentum conservation. This is
an explicit property of the selected formula, not a failed roundoff
criterion.

The largest observed absolute minimum-image viscous pair torque is
\(5.009542\times10^{-4}\) in the full float64 matrix and
\(1.272333\times10^{-4}\) in the smaller float32 precision subset. These
values must not be compared as a dtype convergence pair because the two
matrices contain different numbers of configurations.

## 5. Frozen Stage 01B actual-generic comparison

### 5.1 Comparator formula

The project-owned comparator reconstructs the frozen Stage 01B default
generic-Laplacian algebra without invoking its failed custom backward:

\[
\boxed{
\mathbf a_i^{B}
=
-2\nu\sum_j
\frac{m_j}{\rho_j}
(\mathbf v_j-\mathbf v_i)
\frac{\mathbf r_{ij}\cdot\nabla_iW_{ij}}
{(r_{ij}+10^{-8}H_i)^2}
}.
\]

`tests/test_stage01c_viscosity_antisymmetry.py` independently reconstructs
this expression and requires bitwise equality with the comparator. The
denominator is the frozen \((r+10^{-8}H_i)^2\), not the Stage 01C
\(r^2+(0.01H_{ij})^2\) regularization.

The Stage 01B weighting is one-sided. After multiplication by \(m_i\), its
opposite directed pair uses \(1/\rho_i\) instead of \(1/\rho_j\). It is
therefore pair conservative for uniform density up to accumulation rounding,
but not for a general variable-density state.

### 5.2 Manufactured velocity error

Both operators were evaluated on the same uniform-density manufactured
velocity field against the exact target
\(\nu\nabla^2\mathbf v\). The float64 values below are maxima over all 300
primary configurations. Float32 values are maxima over the six canonical
precision cases; their layouts were generated once in float64 and then cast
to float32, so the comparison does not mix dtype and random-layout changes.

| dtype | operator | max L1 error | max L2 error | max Linf error |
|---|---|---:|---:|---:|
| float64 | Stage 01C conservative pair viscosity | 0.083827 | 0.114471 | 0.539488 |
| float64 | frozen Stage 01B actual generic | 0.083970 | 0.114705 | 0.540482 |
| float32 | Stage 01C conservative pair viscosity | 0.081729 | 0.110383 | 0.522482 |
| float32 | frozen Stage 01B actual generic | 0.081874 | 0.110605 | 0.523695 |

The two errors are close, but neither operator uniformly dominates the other.
For the float64 10% jitter, \(64\times64\) ensemble:

| support family | Stage 01C mean L2 | Stage 01B mean L2 |
|---|---:|---:|
| constant neighbor, \(H/\Delta x=4\) | 0.110593 | 0.110819 |
| increasing neighbor, \(H/\Delta x=6\) | 0.033723 | 0.033661 |

The increasing-neighbor family substantially reduces the disorder error for
both formulas. The small difference between the two columns is not a
conservation proof; it includes the deliberately different regularizations.

### 5.3 Total-force comparison

The structural difference becomes clear under variable density:

| dtype | density | max Stage 01C \(R_{\mathrm{total}}\) | max Stage 01B \(R_{\mathrm{total}}\) | max acceleration Linf difference |
|---|---|---:|---:|---:|
| float64 | uniform | 3.333217e-17 | 7.076632e-17 | 1.568e-03 |
| float64 | variable 5% | 3.405914e-17 | 2.613359e-02 | 4.087816e-02 |
| float32 | uniform | 7.172363e-09 | 4.842792e-08 | 1.453e-03 |
| float32 | variable 5% | 1.096742e-08 | 2.608262e-02 | 4.059055e-02 |

At uniform density, both total-force residuals are at their respective
rounding levels. Under the required 5% density variation, the frozen Stage
01B generic residual reaches approximately 2.6%, whereas the Stage 01C
conservative force remains at \(3.41\times10^{-17}\) in float64 and
\(1.10\times10^{-8}\) in float32. The accuracy table and the force-balance
table therefore support different claims: the new formula retains comparable
uniform-density manufactured accuracy while repairing the variable-density
pair structure.

## 6. Separation from consistency corrections

The conservative pressure and viscosity paths use only the raw radial
`edge_kernel_gradients` and pair accumulation. Shepard normalization,
first-moment correction matrices, linear reproducing weights, isotropic
quadratic-response calibration, and quadratic weighted least squares are
evaluated only as interpolation or manufactured differential-operator
candidates.

No WLS, Shepard, one-sided normalization, or correction matrix is inserted
into either conservative pair force. Thus the measured pressure
antisymmetry, pressure centrality, viscosity \(\Gamma\ge0\), and viscous-power
identity are properties of the forward formulas themselves; they are not
created by a posteriori antisymmetric projection.

## 7. Operator decision

The conservative-operator portion of C3 passes:

- every positive, negative, and mixed-sign pressure case is pair
  antisymmetric under uniform and variable density;
- the pressure force is central under the minimum-image geometry;
- the preregistered viscosity \(\Gamma\) is symmetric and nonnegative;
- \(\nu=0\) is exactly zero and doubling \(\nu\) exactly doubles the force;
- viscosity remains pair and globally conservative under variable density;
- viscous power is nonpositive and agrees with its direct pair identity;
- the lack of a viscous angular-momentum guarantee is explicitly retained;
- the frozen Stage 01B actual-generic comparison preserves its one-sided
  density weighting and original \(10^{-8}H_i\) denominator.

`stage01c_gate_evidence.csv` records all C3 checks as `True`. This decision is
limited to the static operator evidence documented above.

For exact evidence identification, the input SHA-256 values at report
generation were:

```text
e94c30a6e70e886ea02a2e09224ee7cc1a85932f7c063342f83d19141bc8d23e  conservation_metrics.csv
9f8c2979e1c1d95b6dcaab406e9212699f3eb9c3f2ce026c06565108d022a1f9  operator_candidate_metrics.csv
3427a6713959861bc54195ad8818f80a7057aae7c2fdb8829422f97b9d17e1a7  precision_comparison.csv
16170863a9b5f712c4ffa82c147d558e082df63ebd3f1672409c3a37f4f2234f  stage01c_gate_evidence.csv
```
