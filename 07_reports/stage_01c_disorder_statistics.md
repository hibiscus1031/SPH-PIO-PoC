# Stage 01C particle-disorder statistics

Date: 2026-07-31

Scope: preregistered static kernel and manufactured-operator statistics only;
no TGV execution

## 1. Decision

The preregistered Stage 01C disorder matrix is complete:

- 300 of 300 primary static configurations are present;
- all 10 preregistered random seeds are present;
- regular, 5% jitter, and 10% jitter layouts are present at
  \(16^2,24^2,32^2,48^2,64^2\) particles;
- both the constant-neighbor and increasing-neighbor support families are
  present;
- the primary ensemble dtype is float64;
- every ensemble group contains 10 rows;
- mean, sample standard deviation, median, percentile-bootstrap 95%
  confidence interval, mean and median log-error/log-\(dx\) slopes, endpoint
  ratios, and paired-seed finest-grid rebound statistics were written.

The preregistered C2 machine rule selected four curves:

1. raw SPH weights for the zeroth kernel moment \(S_0\);
2. quadratic weighted least squares (WLS) for gradient;
3. quadratic WLS for divergence;
4. quadratic WLS for Laplacian.

On the increasing-neighbor family, all four selected L2 curves have:

- finite results for every required layout;
- mean \(N=64/N=16\) endpoint ratios below one;
- positive mean ensemble slopes;
- no statistically supported \(N=64\) rebound.

The machine-readable C2 result is therefore **PASS**. This is a static
operator-consistency result under the exact preregistered rule. It is not a
time-dependent solver result.

Two points require careful interpretation:

- in the constant-neighbor family, the raw jittered \(S_0\) error remains at
  an approximately constant disorder floor and does not meet the relative
  C2 trend rule, even though the selected WLS derivatives converge;
- Shepard and RKPM-style zeroth-order corrections reduce float64 \(S_0\)
  error to approximately \(10^{-16}\), but become ineligible because the
  preregistered relative endpoint/slope/rebound tests operate below a
  numerical floor. Their ineligibility is not physical divergence.

## 2. Frozen design and case accounting

The design was frozen in:

`06_experiments/stage_01c_disorder_statistics/configs/`
`preregistered_design.yml`.

It records:

- frozen Stage 01B commit:
  `6f26750fea615c79b08a11fddfd832105b985235`;
- frozen tag: `stage-01b-v1-fail`;
- resolutions: 16, 24, 32, 48, and 64 particles per axis;
- jitter fractions: 0, 0.05, and 0.10;
- support families: `constant_neighbor` and `increasing_neighbor`;
- primary dtype: float64;
- bootstrap resamples: 2,000;
- bootstrap RNG seed: `20261999`;
- no post-result change to seeds, support ratios, or thresholds.

The 10 preregistered layout seeds are:

```text
20261001
20261019
20261037
20261061
20261079
20261103
20261121
20261147
20261171
20261189
```

The primary result file is:

`06_experiments/stage_01c_disorder_statistics/results/`
`per_seed_metrics.csv`.

Its 300 rows factor exactly as:

\[
2\ \text{support families}
\times
5\ \text{resolutions}
\times
3\ \text{layouts}
\times
10\ \text{seeds}
=300.
\]

The file contains 150 rows per support family, 100 rows per layout, and 60
rows per resolution. The regular layout is deterministic, so its 10 seed
labels reproduce the same particle state; zero ensemble standard deviation
for regular-layout rows is therefore expected and is not an estimate of
random-layout variability.

For all 300 configurations, the maximum values of:

- `duplicate_edge_count`;
- `omitted_strict_support_edge_count`;
- `nonreciprocal_nonself_edge_count`;
- `out_of_bounds_edge_count`

are zero. The maximum `minimum_image_linf` is
\(2.220446049250313\times10^{-16}\). These topology facts prevent duplicate
edges or periodic-distance errors from contaminating the disorder trends
reported below.

## 3. Statistical definitions and machine-readable fields

The long-form candidate errors are in:

`06_experiments/stage_01c_operator_candidates/results/`
`operator_candidate_metrics.csv`.

It contains 19,800 rows. For each candidate, operator, norm, support family,
resolution, layout, and seed, the measured error is stored in `error`.

The ensemble summaries are in:

`06_experiments/stage_01c_disorder_statistics/results/`
`ensemble_summary.csv`.

The relevant fields are:

- `sample_count`;
- `mean`;
- `sample_standard_deviation`;
- `median`;
- `bootstrap_mean_CI95_low`;
- `bootstrap_mean_CI95_high`;
- `minimum`;
- `maximum`.

Every group has `sample_count=10`. The bootstrap interval is the
preregistered percentile interval for the mean, using 2,000 resamples and
seed `20261999`.

Five-resolution trend statistics are in:

`06_experiments/stage_01c_disorder_statistics/results/`
`ensemble_slopes.csv`.

The slope is ordinary least squares over all five resolutions:

\[
\log(\text{ensemble error})
=
p\log(dx)+c.
\]

Because \(dx\) decreases during refinement, \(p>0\) denotes decreasing error.
The file reports both:

- `mean_log_error_log_dx_slope`;
- `median_log_error_log_dx_slope`;

and both mean and median \(N=64/N=16\) endpoint ratios.

The finest-grid audit is in:

`06_experiments/stage_01c_disorder_statistics/results/`
`finest_rebound_audit.csv`.

For each matched seed it forms:

\[
\Delta_{64-48}=e_{64}-e_{48}.
\]

`systematic_finest_rebound=True` only when the paired-seed bootstrap 95%
confidence interval for the mean difference lies entirely above zero. A
negative interval is evidence of improvement; an interval spanning zero is
not a statistically supported rebound.

## 4. C2 candidate selection

The exact selection result is:

`06_experiments/stage_01c_operator_candidates/results/`
`candidate_selection.csv`.

The machine first requires, on the increasing-neighbor L2 curves:

1. finite errors and all 300 required candidate/operator rows;
2. mean endpoint ratio below one on regular, 5%, and 10% layouts;
3. positive mean ensemble slope on all three layouts;
4. no systematic \(N=64\) rebound on any layout.

Among eligible candidates, it minimizes the geometric mean of the
finest-resolution 5% and 10% jitter L2 means.

| Principal operator | Selected candidate | Variant | Finest jitter L2 geometric mean |
|---|---|---|---:|
| `kernel_S0` | `raw_sph` | `raw_kernel_weights` | 0.00574602224 |
| `gradient` | `quadratic_weighted_least_squares` | `local_quadratic_weighted_least_squares_gradient` | 0.11866916008 |
| `divergence` | `quadratic_weighted_least_squares` | `local_quadratic_weighted_least_squares_gradient` | 0.21227729782 |
| `Laplacian` | `quadratic_weighted_least_squares` | `local_quadratic_weighted_least_squares_laplacian` | 0.73544972319 |

For gradient, the corresponding finest-jitter geometric means of the other
eligible candidates are:

- first-order gradient matrix: 0.12722290802;
- raw SPH difference gradient: 0.13169525154;
- Shepard-scaled difference gradient: 0.13406530339.

For divergence they are 0.22752638760, 0.23301264074, and 0.23722264572.
For Laplacian they are 1.40540059960, 1.42480899260, and 1.43696453174.
Thus WLS is selected by the frozen ranking rule, not by visual inspection.

`stage01c_gate_evidence.csv` records:

```text
C2,eligible_selected_operator_count,True,4,
"4, one for each preregistered principal operator",
candidate_selection.csv
```

## 5. Constant-neighbor selected-curve statistics

The following table reports the selected L2 curves. The five slash-separated
values are ensemble means at \(N=16,24,32,48,64\). The next column reports
the \(N=64\) sample standard deviation, median, and bootstrap 95% confidence
interval for the mean. `Slope` is the mean-curve log-error/log-\(dx\) slope.
The paired interval applies to the mean of \(e_{64}-e_{48}\).

| Layout | Curve | Mean L2 at \(N=16/24/32/48/64\) | \(N=64\): std; median; bootstrap mean CI95 | Slope | Mean 64/16 | Mean \(\Delta_{64-48}\); paired CI95 | Systematic rebound |
|---|---|---|---|---:|---:|---|---|
| regular | raw \(S_0\) | 0.000415750/0.000415750/0.000415750/0.000415750/0.000415750 | \(5.71\times10^{-20}\); 0.000415750; [0.000415750, 0.000415750] | \(-8.09\times10^{-14}\) | 1.000000 | \(-6.87\times10^{-17}\); [\(-6.87\times10^{-17}\), \(-6.87\times10^{-17}\)] | False |
| regular | WLS gradient | 0.766584/0.362227/0.208214/0.0939888/0.0531578 | 0; 0.0531578; [0.0531578, 0.0531578] | 1.92852 | 0.0693436 | -0.0408310; [-0.0408310, -0.0408310] | False |
| regular | WLS divergence | 1.37131/0.647971/0.372464/0.168132/0.0950915 | 0; 0.0950915; [0.0950915, 0.0950915] | 1.92852 | 0.0693436 | -0.0730408; [-0.0730408, -0.0730408] | False |
| regular | WLS Laplacian | 4.80978/2.24789/1.28714/0.579416/0.327386 | 0; 0.327386; [0.327386, 0.327386] | 1.94130 | 0.0680667 | -0.252030; [-0.252030, -0.252030] | False |
| 5% jitter | raw \(S_0\) | 0.00900502/0.00905646/0.00918286/0.00913938/0.00913915 | 0.000206; 0.00912969; [0.00901742, 0.00925750] | -0.0110535 | 1.01490 | \(-2.30\times10^{-7}\); [-0.000232371, 0.000170321] | False |
| 5% jitter | WLS gradient | 0.766966/0.362407/0.208321/0.0940370/0.0531875 | \(2.51\times10^{-6}\); 0.0531877; [0.0531861, 0.0531890] | 1.92848 | 0.0693479 | -0.0408494; [-0.0408517, -0.0408471] | False |
| 5% jitter | WLS divergence | 1.37207/0.648213/0.372632/0.168210/0.0951411 | \(8.16\times10^{-6}\); 0.0951422; [0.0951359, 0.0951454] | 1.92852 | 0.0693410 | -0.0730694; [-0.0730792, -0.0730593] | False |
| 5% jitter | WLS Laplacian | 4.80976/2.24936/1.28839/0.580532/0.328502 | \(5.15\times10^{-5}\); 0.328517; [0.328472, 0.328529] | 1.93898 | 0.0682990 | -0.252030; [-0.252097, -0.251959] | False |
| 10% jitter | raw \(S_0\) | 0.0179828/0.0180948/0.0183503/0.0182682/0.0182645 | 0.000416; 0.0182414; [0.0180145, 0.0185029] | -0.0116261 | 1.01567 | \(-3.70\times10^{-6}\); [-0.000444049, 0.000317003] | False |
| 10% jitter | WLS gradient | 0.768056/0.362945/0.208648/0.0941833/0.0532736 | \(7.77\times10^{-6}\); 0.0532737; [0.0532695, 0.0532783] | 1.92834 | 0.0693616 | -0.0409097; [-0.0409149, -0.0409044] | False |
| 10% jitter | WLS divergence | 1.37405/0.649071/0.373141/0.168460/0.0952853 | \(1.91\times10^{-5}\); 0.0952874; [0.0952731, 0.0952961] | 1.92843 | 0.0693461 | -0.0731752; [-0.0731975, -0.0731499] | False |
| 10% jitter | WLS Laplacian | 4.81406/2.25394/1.29235/0.583958/0.331852 | 0.000127; 0.331889; [0.331774, 0.331922] | 1.93260 | 0.0689340 | -0.252105; [-0.252295, -0.251922] | False |

The WLS manufactured derivatives have credible decreasing mean and median
trends in all three layouts. Raw \(S_0\), however, is essentially constant on
the regular layout and has slightly negative slopes and endpoint ratios above
one under jitter. Its paired \(48\)-to-\(64\) intervals span zero, so there is
no statistically supported *finest-grid* rebound, but the five-resolution
constant-neighbor trend still fails the preregistered endpoint and slope
conditions.

## 6. Increasing-neighbor selected-curve statistics

The same columns are reported for the increasing-neighbor family.

| Layout | Curve | Mean L2 at \(N=16/24/32/48/64\) | \(N=64\): std; median; bootstrap mean CI95 | Slope | Mean 64/16 | Mean \(\Delta_{64-48}\); paired CI95 | Systematic rebound |
|---|---|---|---|---:|---:|---|---|
| regular | raw \(S_0\) | 0.000415750/0.000176986/\(8.83204\times10^{-5}\)/\(4.40180\times10^{-5}\)/\(2.47905\times10^{-5}\) | 0; \(2.47905\times10^{-5}\); [\(2.47905\times10^{-5}\), \(2.47905\times10^{-5}\)] | 2.02711 | 0.0596283 | \(-1.92275\times10^{-5}\); [\(-1.92275\times10^{-5}\), \(-1.92275\times10^{-5}\)] | False |
| regular | WLS gradient | 0.766584/0.452869/0.320397/0.175857/0.118634 | 0; 0.118634; [0.118634, 0.118634] | 1.35013 | 0.154756 | -0.0572233; [-0.0572233, -0.0572233] | False |
| regular | WLS divergence | 1.37131/0.810118/0.573144/0.314582/0.212218 | 0; 0.212218; [0.212218, 0.212218] | 1.35013 | 0.154756 | -0.102364; [-0.102364, -0.102364] | False |
| regular | WLS Laplacian | 4.80978/2.83162/1.99304/1.09106/0.734725 | 0; 0.734725; [0.734725, 0.734725] | 1.35985 | 0.152756 | -0.356333; [-0.356333, -0.356333] | False |
| 5% jitter | raw \(S_0\) | 0.00900502/0.00712898/0.00588604/0.00481790/0.00406380 | 0.000133; 0.00407315; [0.00397873, 0.00414324] | 0.571567 | 0.451281 | -0.000754099; [-0.000916677, -0.000627023] | False |
| 5% jitter | WLS gradient | 0.766966/0.453002/0.320465/0.175880/0.118649 | \(3.04\times10^{-6}\); 0.118649; [0.118647, 0.118650] | 1.35039 | 0.154699 | -0.0572316; [-0.0572354, -0.0572271] | False |
| 5% jitter | WLS divergence | 1.37207/0.810274/0.573252/0.314611/0.212243 | \(1.62\times10^{-5}\); 0.212244; [0.212233, 0.212253] | 1.35042 | 0.154688 | -0.102368; [-0.102384, -0.102352] | False |
| 5% jitter | WLS Laplacian | 4.80976/2.83239/1.99371/1.09143/0.735023 | \(6.94\times10^{-5}\); 0.735039; [0.734981, 0.735063] | 1.35959 | 0.152819 | -0.356406; [-0.356489, -0.356310] | False |
| 10% jitter | raw \(S_0\) | 0.0179828/0.0142493/0.0117670/0.00963306/0.00812461 | 0.000265; 0.00814111; [0.00796542, 0.00827649] | 0.570794 | 0.451799 | -0.00150844; [-0.00185542, -0.00126707] | False |
| 10% jitter | WLS gradient | 0.768056/0.453400/0.320675/0.175954/0.118690 | \(6.81\times10^{-6}\); 0.118691; [0.118686, 0.118693] | 1.35115 | 0.154533 | -0.0572646; [-0.0572714, -0.0572563] | False |
| 10% jitter | WLS divergence | 1.37405/0.810903/0.573582/0.314729/0.212312 | \(3.41\times10^{-5}\); 0.212316; [0.212291, 0.212331] | 1.35119 | 0.154515 | -0.102418; [-0.102449, -0.102385] | False |
| 10% jitter | WLS Laplacian | 4.81406/2.83484/1.99568/1.09256/0.735877 | 0.000139; 0.735903; [0.735794, 0.735961] | 1.35939 | 0.152860 | -0.356678; [-0.356880, -0.356451] | False |

Mean and median slopes agree closely. For example:

- 5% jitter raw \(S_0\): mean/median slopes
  \(0.571567/0.565749\);
- 10% jitter raw \(S_0\): \(0.570794/0.565414\);
- 10% jitter WLS gradient: \(1.35115/1.35112\);
- 10% jitter WLS divergence: \(1.35119/1.35112\);
- 10% jitter WLS Laplacian: \(1.35939/1.35929\).

For every increasing-neighbor selected curve, the paired rebound interval is
strictly negative. Thus the highest resolution improves rather than
systematically rebounding.

## 7. Shepard and RKPM \(S_0\): numerical-floor ineligibility

`01_solver/structure_preserving/kernels.py` implements:

- Shepard weights by nodewise normalization of the raw weights;
- `linear_reproducing_edge_weights`, explicitly documented as RKPM-style
  weights reproducing constants and linear fields.

In float64, both candidates reproduce \(S_0=1\) to approximately machine
precision. Their increasing-neighbor L2 ensemble means are:

| Candidate | Layout | Mean L2 at \(N=16/24/32/48/64\) | Mean slope | Mean 64/16 | Paired \(\Delta_{64-48}\) CI95 | Systematic rebound |
|---|---|---|---:|---:|---|---|
| Shepard | regular | `2.69e-16/8.51e-16/2.00e-16/2.34e-16/3.05e-16` | 0.266878 | 1.13187 | [`7.08e-17`, `7.08e-17`] | True |
| Shepard | 5% jitter | `2.62e-16/3.09e-16/3.14e-16/3.59e-16/3.83e-16` | -0.263801 | 1.46105 | [`2.01e-17`, `2.94e-17`] | True |
| Shepard | 10% jitter | `2.61e-16/3.13e-16/3.22e-16/3.63e-16/3.89e-16` | -0.276595 | 1.49409 | [`2.22e-17`, `3.05e-17`] | True |
| RKPM-style | regular | `2.71e-16/7.46e-16/1.83e-16/2.58e-16/2.99e-16` | 0.213043 | 1.10654 | [`4.12e-17`, `4.12e-17`] | True |
| RKPM-style | 5% jitter | `2.76e-16/3.27e-16/3.31e-16/3.72e-16/3.93e-16` | -0.244998 | 1.42688 | [`1.80e-17`, `2.39e-17`] | True |
| RKPM-style | 10% jitter | `2.75e-16/3.27e-16/3.39e-16/3.74e-16/4.00e-16` | -0.255859 | 1.45168 | [`2.04e-17`, `3.07e-17`] | True |

Accordingly, `candidate_selection.csv` records for both corrected \(S_0\)
candidates:

- `all_errors_finite=True`;
- `all_required_layouts_complete=True`;
- `all_endpoint_ratios_below_one=False`;
- `all_ensemble_slopes_positive=False`;
- `no_systematic_N64_rebound=False`;
- `eligible=False`.

Their finest jitter L2 geometric means are nevertheless only
\(3.8607\times10^{-16}\) for Shepard and
\(3.9634\times10^{-16}\) for RKPM-style weights.

This apparent contradiction is a consequence of the preregistered *relative*
trend rules at a numerical floor. Changes of a few \(10^{-17}\) are large
relative to a \(10^{-16}\) residual, even though the absolute error is already
at float64 roundoff. It is incorrect to call these curves physically
divergent. The rules were not changed after viewing the data, so they remain
ineligible for the C2 machine selection. They remain valid interpolation
correction candidates with a separately stated numerical-floor limitation.

## 8. Float32/float64 canonical-layout isolation

The preregistered canonical cases are:

- regular \(32^2\), seed `20261001`;
- 10% jitter \(32^2\), seed `20261001`;
- 10% jitter \(64^2\), seed `20261001`.

For both support families, positions are generated once in float64 and passed
as the reference layout to both dtype evaluations. The shared
`position_reference_sha256` prevents different random layouts from being
mistaken for a precision effect.

Evidence:

- `06_experiments/stage_01c_operator_candidates/results/`
  `precision_isolation.csv`;
- `06_experiments/stage_01c_operator_candidates/results/`
  `precision_comparison.csv`.

Each entry below is `float32 / float64` L2 error for the selected curve.

| Support family and canonical case | Raw \(S_0\) | WLS gradient | WLS divergence | WLS Laplacian |
|---|---:|---:|---:|---:|
| constant, regular N32 | 0.000415671 / 0.000415750 | 0.208214119 / 0.208213784 | 0.372464389 / 0.372464141 | 1.28713548 / 1.28713863 |
| constant, 10% N32 | 0.018117854 / 0.018117850 | 0.208611578 / 0.208611444 | 0.373288929 / 0.373288761 | 1.29336357 / 1.29336422 |
| constant, 10% N64 | 0.018268252 / 0.018268253 | 0.053262096 / 0.053261922 | 0.095243767 / 0.095243611 | 0.331673324 / 0.331674159 |
| increasing, regular N32 | \(8.84674\times10^{-5}\) / \(8.83204\times10^{-5}\) | 0.320396841 / 0.320397215 | 0.573142827 / 0.573143962 | 1.99304330 / 1.99303777 |
| increasing, 10% N32 | 0.011654816 / 0.011654810 | 0.320679873 / 0.320679721 | 0.573921084 / 0.573920894 | 1.99636662 / 1.99636779 |
| increasing, 10% N64 | 0.008103546 / 0.008103553 | 0.118678614 / 0.118678452 | 0.212241769 / 0.212241584 | 0.735746682 / 0.735748170 |

Across these cases, the maximum relative float32/float64 differences are:

- raw \(S_0\): \(1.6622\times10^{-3}\), arising on the small regular
  increasing-family error; the maximum absolute difference is
  \(1.4705\times10^{-7}\);
- WLS gradient: \(3.2597\times10^{-6}\);
- WLS divergence: \(1.9818\times10^{-6}\);
- WLS Laplacian: \(2.7746\times10^{-6}\).

For the disordered selected curves, float32/float64 changes are orders of
magnitude smaller than the measured errors. Their errors are therefore
dominated by discretization and particle disorder, not float32 accumulation.

The corrected \(S_0\) candidates expose the expected precision floor more
directly. Across the canonical cases:

- Shepard L2 is approximately \(1.10\times10^{-7}\) to
  \(2.00\times10^{-7}\) in float32 and \(2.00\times10^{-16}\) to
  \(3.83\times10^{-16}\) in float64;
- RKPM-style L2 is approximately \(1.09\times10^{-7}\) to
  \(2.39\times10^{-7}\) in float32 and \(1.83\times10^{-16}\) to
  \(3.92\times10^{-16}\) in float64.

For increasing-neighbor, 10% jitter, N64, the exact pairs are:

- Shepard:
  \(1.9993091\times10^{-7}/3.8318546\times10^{-16}\);
- RKPM-style:
  \(2.0613390\times10^{-7}/3.9193619\times10^{-16}\).

This dtype scaling confirms a floating-point reproduction floor. It does not
justify deleting the float32 rows or changing the preregistered eligibility
rule.

## 9. Interpolation, derivative, and pair-force roles

The candidate-selection result must not collapse three distinct numerical
roles.

### 9.1 Interpolation and kernel reproduction

Shepard normalization enforces nodewise zeroth-order normalization.
RKPM-style weights reproduce constant and linear basis functions. Their
machine-precision \(S_0\) results qualify them as interpolation/reproduction
candidates, subject to dtype precision.

### 9.2 Manufactured derivatives

The selected WLS gradient, divergence, and Laplacian are local quadratic
derivative estimators. Their role is to approximate derivatives of the
manufactured scalar and vector fields. Their selection does not assert a
pair-force conservation property.

### 9.3 Conservative pair forces

The preregistration explicitly states:

```text
one-sided or MLS corrections may qualify manufactured operators only
and may not be inserted into pair forces
```

A nodewise Shepard factor, one-sided correction matrix, RKPM coefficient, or
WLS fit generally differs between particles \(i\) and \(j\). Inserting such a
one-sided correction into one edge direction can destroy
\(\mathbf f_{ij}=-\mathbf f_{ji}\).

Pressure and viscosity conservation must instead be obtained from the raw
forward pair formula using a single shared symmetric-support radial kernel
gradient and explicitly symmetric pair coefficients. The static manufactured
operator ranking is therefore not a ranking of conservative force laws.

## 10. C2 conclusion and limits

Machine evidence:

`06_experiments/stage_01c_operator_candidates/results/`
`stage01c_gate_evidence.csv`

records:

- four eligible selected principal operators;
- three increasing-family layouts with strictly decreasing \(H\);
- increasing ensemble neighbor means with endpoint ratios from 2.30612 to
  2.36407.

For the selected increasing-neighbor curves, regular, 5% jitter, and 10%
jitter all have positive mean slopes, endpoint ratios below one, and no
systematic finest-grid rebound. The disorder-statistics portion of C2 is
therefore **PASS under the preregistered machine rule**.

The complete per-seed values, L1/L2/Linf summaries, median slopes, and all
candidate variants remain in the CSV files cited above. This report does not
replace those machine-readable records, does not claim differentiability of
neighbor-topology changes, and does not contain a time-dependent result.
