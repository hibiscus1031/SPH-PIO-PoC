# Stage 01C support-scaling audit

Date: 2026-07-31

Scope: preregistered static support and neighbor-count scaling; no TGV
execution

## 1. Decision

Both preregistered support families satisfy the requirement that the physical
compact-support radius \(H\) strictly decreases as particle resolution
increases.

Only the increasing-neighbor family satisfies the additional consistency
requirement that the ensemble mean neighbor count strictly increases at every
refinement:

- regular endpoint neighbor-count ratio: 2.30612245;
- 5% jitter: 2.36407294;
- 10% jitter: 2.36040129.

The constant-neighbor family behaves as designed: its neighbor count remains
approximately fixed, with endpoint ratios 1.00000000, 0.99976212, and
1.00020028. It is retained as a diagnostic family, not relabeled as an
increasing-neighbor consistency path.

The support-scaling component of C2 is **PASS** for the increasing-neighbor
family. Its selected raw \(S_0\) and WLS gradient/divergence/Laplacian curves
all improve from \(N=16\) to \(N=64\), have positive mean and median slopes,
and have no statistically supported finest-grid rebound.

## 2. Preregistered support laws

The frozen source is:

`06_experiments/stage_01c_disorder_statistics/configs/`
`preregistered_design.yml`.

The domain length is \(L=2\), \(dx=L/N\), and:

\[
H=(H/dx)\,dx.
\]

The support ratios were frozen before Stage 01C results:

| Particles/axis | Constant family \(H/dx\) | Increasing family \(H/dx\) |
|---:|---:|---:|
| 16 | 4.0 | 4.0 |
| 24 | 4.0 | 4.5 |
| 32 | 4.0 | 5.0 |
| 48 | 4.0 | 5.5 |
| 64 | 4.0 | 6.0 |

Consequently:

| Particles/axis | \(dx\) | Constant \(H\) | Increasing \(H\) |
|---:|---:|---:|---:|
| 16 | 0.125000000 | 0.500000000 | 0.500000000 |
| 24 | 0.083333333 | 0.333333333 | 0.375000000 |
| 32 | 0.062500000 | 0.250000000 | 0.312500000 |
| 48 | 0.041666667 | 0.166666667 | 0.229166667 |
| 64 | 0.031250000 | 0.125000000 | 0.187500000 |

Thus the increasing-neighbor path does not hold physical \(H\) fixed.
Although \(H/dx\) grows, \(H\) itself decreases strictly:

\[
0.5>0.375>0.3125>0.2291667>0.1875.
\]

No support ratio was changed after viewing an error curve.

## 3. Neighbor-count scaling

Evidence:

- `06_experiments/stage_01c_support_scaling/results/`
  `support_scaling.csv`;
- `06_experiments/stage_01c_support_scaling/results/`
  `support_family_checks.csv`;
- `06_experiments/stage_01c_support_scaling/figures/`
  `support_scaling.png`.

The table reports the 10-seed ensemble mean particle neighbor count, including
the self edge.

| Family | N | H | Regular mean | 5% jitter mean | 10% jitter mean |
|---|---:|---:|---:|---:|---:|
| constant | 16 | 0.500000 | 49.000000 | 47.004688 | 47.541406 |
| constant | 24 | 0.333333 | 49.000000 | 46.989236 | 47.539236 |
| constant | 32 | 0.250000 | 49.000000 | 47.003906 | 47.565234 |
| constant | 48 | 0.166667 | 49.000000 | 46.990365 | 47.563108 |
| constant | 64 | 0.125000 | 49.000000 | 46.993506 | 47.550928 |
| increasing | 16 | 0.500000 | 49.000000 | 47.004688 | 47.541406 |
| increasing | 24 | 0.375000 | 69.000000 | 66.932292 | 66.003819 |
| increasing | 32 | 0.312500 | 81.000000 | 74.999023 | 75.964258 |
| increasing | 48 | 0.229167 | 97.000000 | 96.998438 | 96.398264 |
| increasing | 64 | 0.187500 | 113.000000 | 111.122510 | 112.216797 |

Endpoint checks:

| Family | Layout | N16 mean | N64 mean | N64/N16 | Strictly decreasing H | Strictly increasing ensemble neighbor mean |
|---|---|---:|---:|---:|---|---|
| constant | regular | 49.000000 | 49.000000 | 1.00000000 | True | False |
| constant | 5% jitter | 47.004688 | 46.993506 | 0.99976212 | True | False |
| constant | 10% jitter | 47.541406 | 47.550928 | 1.00020028 | True | False |
| increasing | regular | 49.000000 | 113.000000 | 2.30612245 | True | True |
| increasing | 5% jitter | 47.004688 | 111.122510 | 2.36407294 | True | True |
| increasing | 10% jitter | 47.541406 | 112.216797 | 2.36040129 | True | True |

The per-particle endpoint ranges are:

| Family/layout | N16 min--max | N64 min--max |
|---|---:|---:|
| constant regular | 49--49 | 49--49 |
| constant 5% jitter | 45--49 | 45--49 |
| constant 10% jitter | 45--51 | 45--52 |
| increasing regular | 49--49 | 113--113 |
| increasing 5% jitter | 45--49 | 109--115 |
| increasing 10% jitter | 45--51 | 108--117 |

Every row in `support_scaling.csv` has:

- `maximum_duplicate_edges=0`;
- `maximum_strict_omissions=0`.

Neighbor growth therefore does not come from repeated edges or omitted-edge
accounting.

## 4. Selected error endpoints under the two support laws

The C2 machine selection is stored in:

`06_experiments/stage_01c_operator_candidates/results/`
`candidate_selection.csv`.

It selects raw SPH for \(S_0\) and quadratic WLS for gradient, divergence, and
Laplacian. The following are ensemble mean L2 endpoints.

| Family/layout | Raw \(S_0\), N16 \(\to\) N64 | WLS gradient | WLS divergence | WLS Laplacian |
|---|---:|---:|---:|---:|
| constant regular | 0.000415750 \(\to\) 0.000415750 | 0.766584 \(\to\) 0.0531578 | 1.37131 \(\to\) 0.0950915 | 4.80978 \(\to\) 0.327386 |
| constant 5% | 0.00900502 \(\to\) 0.00913915 | 0.766966 \(\to\) 0.0531875 | 1.37207 \(\to\) 0.0951411 | 4.80976 \(\to\) 0.328502 |
| constant 10% | 0.0179828 \(\to\) 0.0182645 | 0.768056 \(\to\) 0.0532736 | 1.37405 \(\to\) 0.0952853 | 4.81406 \(\to\) 0.331852 |
| increasing regular | 0.000415750 \(\to\) \(2.47905\times10^{-5}\) | 0.766584 \(\to\) 0.118634 | 1.37131 \(\to\) 0.212218 | 4.80978 \(\to\) 0.734725 |
| increasing 5% | 0.00900502 \(\to\) 0.00406380 | 0.766966 \(\to\) 0.118649 | 1.37207 \(\to\) 0.212243 | 4.80976 \(\to\) 0.735023 |
| increasing 10% | 0.0179828 \(\to\) 0.00812461 | 0.768056 \(\to\) 0.118690 | 1.37405 \(\to\) 0.212312 | 4.81406 \(\to\) 0.735877 |

The constant family produces smaller finite-resolution WLS derivative errors
at N64 and near-second-order slopes, because its physical support shrinks as
\(H\propto dx\). Its raw jittered \(S_0\), however, remains at a nearly fixed
neighbor-sampling floor.

The increasing family shrinks \(H\) more slowly while increasing the sample
population. Its finite-resolution derivative errors are consequently larger
and its slopes are approximately 1.35 rather than 1.93, but raw jittered
\(S_0\) now decreases credibly. This is the intended truncation-versus-
quadrature tradeoff between the two paths.

## 5. Mean/median slopes and finest-grid rebound

Evidence:

- `06_experiments/stage_01c_disorder_statistics/results/`
  `ensemble_slopes.csv`;
- `06_experiments/stage_01c_disorder_statistics/results/`
  `finest_rebound_audit.csv`.

Mean and median L2 slopes are:

| Family | Layout | Raw \(S_0\) | WLS gradient | WLS divergence | WLS Laplacian |
|---|---|---:|---:|---:|---:|
| constant | regular | `-8.09e-14/-7.98e-14` | 1.92852/1.92852 | 1.92852/1.92852 | 1.94130/1.94130 |
| constant | 5% | -0.0110535/-0.0168695 | 1.92848/1.92847 | 1.92852/1.92849 | 1.93898/1.93886 |
| constant | 10% | -0.0116261/-0.0177217 | 1.92834/1.92835 | 1.92843/1.92832 | 1.93260/1.93246 |
| increasing | regular | 2.02711/2.02711 | 1.35013/1.35013 | 1.35013/1.35013 | 1.35985/1.35985 |
| increasing | 5% | 0.571567/0.565749 | 1.35039/1.35037 | 1.35042/1.35041 | 1.35959/1.35949 |
| increasing | 10% | 0.570794/0.565414 | 1.35115/1.35112 | 1.35119/1.35112 | 1.35939/1.35929 |

Each cell is `mean-curve slope / median-curve slope`.

For the support-sensitive raw \(S_0\) disorder cases:

| Family/layout | N64 mean | N64 sample std | N64 median | Bootstrap mean CI95 | Mean \(\Delta_{64-48}\) | Paired CI95 | Systematic rebound |
|---|---:|---:|---:|---|---:|---|---|
| constant 5% | 0.00913915 | 0.000205780 | 0.00912969 | [0.00901742, 0.00925750] | \(-2.30\times10^{-7}\) | [-0.000232371, 0.000170321] | False |
| constant 10% | 0.0182645 | 0.000416167 | 0.0182414 | [0.0180145, 0.0185029] | \(-3.70\times10^{-6}\) | [-0.000444049, 0.000317003] | False |
| increasing 5% | 0.00406380 | 0.000133186 | 0.00407315 | [0.00397873, 0.00414324] | -0.000754099 | [-0.000916677, -0.000627023] | False |
| increasing 10% | 0.00812461 | 0.000265295 | 0.00814111 | [0.00796542, 0.00827649] | -0.00150844 | [-0.00185542, -0.00126707] | False |

The constant-family paired intervals span zero. There is no supported
\(48\)-to-\(64\) rebound, but the full five-level mean and median slopes are
negative and the endpoint ratios exceed one. The constant jittered raw
\(S_0\) curves therefore remain ineligible under the preregistered C2 rule.

The increasing-family intervals are entirely negative, mean and median slopes
are positive, and endpoint ratios are approximately 0.451. These curves meet
all three C2 trend conditions.

All selected derivative curves in both families have strictly negative
paired rebound intervals. For increasing-neighbor 10% jitter:

- WLS gradient:
  \(\Delta=-0.0572646\), CI
  \([-0.0572714,-0.0572563]\);
- WLS divergence:
  \(\Delta=-0.102418\), CI
  \([-0.102449,-0.102385]\);
- WLS Laplacian:
  \(\Delta=-0.356678\), CI
  \([-0.356880,-0.356451]\).

## 6. C2 machine rule and numerical-floor exception

The machine rule is implemented in:

`01_solver/structure_preserving/evaluate_requalification.py:51-157`.

It uses only increasing-neighbor L2 rows and requires, for regular, 5%, and
10% layouts:

- endpoint ratio below one;
- positive mean slope;
- no systematic N64 rebound.

It then ranks eligible candidates using the finest 5%/10% geometric mean.
This procedure selected raw \(S_0\) and WLS gradient/divergence/Laplacian.

Shepard-normalized and RKPM-style kernel weights reach float64 \(S_0\) L2
errors of approximately \(2\times10^{-16}\) to \(4\times10^{-16}\). Their
roundoff-level residuals fluctuate relatively with resolution, giving
endpoint ratios above one, some negative slopes, and positive paired
differences of only a few \(10^{-17}\). The frozen relative rule therefore
marks them ineligible.

This is a numerical-floor effect, not physical growth of an interpolation
error. The rule was deliberately not modified after observing the result.
Raw \(S_0\) is consequently the selected *C2 trend curve*, even though
Shepard and RKPM-style weights are much more accurate in absolute
zeroth-order reproduction.

## 7. Precision isolation and interpretation

Canonical float32/float64 evidence is in:

- `06_experiments/stage_01c_operator_candidates/results/`
  `precision_isolation.csv`;
- `06_experiments/stage_01c_operator_candidates/results/`
  `precision_comparison.csv`.

The same float64 reference positions are used for both dtypes. For the
selected curves:

- maximum relative raw-\(S_0\) dtype difference:
  \(1.6622\times10^{-3}\), with maximum absolute difference
  \(1.4705\times10^{-7}\);
- maximum WLS-gradient difference:
  \(3.2597\times10^{-6}\);
- maximum WLS-divergence difference:
  \(1.9818\times10^{-6}\);
- maximum WLS-Laplacian difference:
  \(2.7746\times10^{-6}\).

These differences are much smaller than the disordered selected-curve errors,
so the constant-versus-increasing distinction is a support/discretization
effect, not a float32 artifact.

In contrast, the corrected \(S_0\) candidates scale from float64 roundoff
(\(\sim10^{-16}\)) to float32 roundoff (\(\sim10^{-7}\)). This confirms that
their failed relative trend eligibility is a precision floor.

## 8. Separation from conservative pair forces

Support scaling and manufactured-operator selection do not authorize
one-sided corrections inside conservative pair forces.

- Shepard and RKPM-style weights are interpolation/reproduction candidates.
- WLS and first-moment matrices are derivative candidates.
- Conservative pressure and viscosity require a shared symmetric-support
  radial gradient and explicitly symmetric pair coefficients.

A correction evaluated independently at particle \(i\) and particle \(j\)
need not be identical on a disordered layout. Applying it to only one edge
direction can destroy pair antisymmetry even when it improves a manufactured
derivative. The preregistration therefore forbids inserting one-sided or MLS
corrections directly into pair forces.

The support-scaling C2 pass and the conservative-force qualification are
separate pieces of evidence.

## 9. Evidence summary and limits

`stage01c_gate_evidence.csv` records the support result as:

```text
3 layouts; neighbor endpoint ratios 2.30612–2.36407,
H strictly decreases and ensemble neighbor mean strictly increases
```

This agrees with `support_family_checks.csv` and the full 300-row primary
matrix. The increasing-neighbor family satisfies the preregistered consistency
support requirements; the constant-neighbor family remains an informative
comparison with fixed neighbor population.

No time integration or TGV calculation is contained in this report.
