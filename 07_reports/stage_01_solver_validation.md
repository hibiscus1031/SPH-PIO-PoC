# Stage 01 — Full diffSPH solver validation and Taylor–Green baseline

Date: 2026-07-31  
Final status: **CONDITIONAL PASS**

This report covers only Stage 01.  No neural network was trained, no
Transformer or training dataset was created, no CUDA/cuDNN/NVIDIA package was
installed, the system Python was not changed, and Stage 02 was not started.

## 1. Executive summary

The official diffSPH Taylor–Green numerical chain is executable on this
Apple-Silicon machine on CPU and on a hybrid MPS path.  All 10 canonical
400-step runs completed, the CPU results showed a monotonic three-resolution
error trend, the 3-step autograd checks passed on CPU and MPS, and the
1024-particle MPS process completed a bounded 600.116-second stability test.

The result is not an unconditional `PASS` for two concrete reasons:

1. `torchCompactRadius` has no native MPS compact neighbor-search
   implementation.  It detaches and transfers positions to CPU for neighbor
   search, then returns indices to MPS.  The run is therefore hybrid, not pure
   MPS.
2. In the pinned diffSPH commit, the reachable DeltaSPH velocity-diffusion
   function hard-codes \(\alpha=0.01\).  The official notebook's effective
   viscosity estimate consequently changes with resolution, so the
   16/24/32 comparison is a credible official-demo resolution trend, but not a
   fixed-Reynolds-number convergence study.

| Item | Decision | Direct evidence |
|---|---|---|
| Full diffSPH solver | PASS | 10 canonical raw/log bundles; no invalid canonical bundle |
| CPU | PASS | 256, 576 and 1024 particles, two repeats each |
| MPS | CONDITIONAL | 256 and 1024 particles, two repeats each; CPU neighbor-search bridge |
| Numerical trend | PASS as a trend | velocity and energy errors decrease monotonically |
| Strict convergence | NOT CLAIMED | resolution-specific effective \(\nu\) and Re |
| Multi-step autograd | PASS | `stage_01_gradient_check.md` |
| 10-minute resource test | PASS with thermal slowdown | 3276 steps in 600.116 s |
| Recommended next backend | CPU | fastest tested complete path and exact repeatability |
| Verified next-stage ceiling | 1024 particles | larger cases were not tested |

Primary evidence is in
`07_reports/stage_01_numerical_metrics.csv`,
`07_reports/stage_01_runtime_metrics.csv`, and
`06_experiments/stage_01_tgv/figures/`.

## 2. Complete diffSPH solver decision

**Decision: PASS for the tested official DeltaSPH TGV chain.**

The installed source is diffSPH `0.2.1` at official commit
`fff180c81d57a51035de9f4d358dbcaccf973928`.  The Python-tree SHA-256 of
the checkout and installed package is identical:

```text
09d59c684565d12051cb0a491daf08478f43ab3803a74e9947a3a7e5beb474f8
```

The reused official entries are:

- `examples/weaklyCompressible/05_TGV.ipynb`
- `examples/weaklyCompressible/scripts/05_TGV.py`
- `examples/weaklyCompressible/scripts/exampleUtil.py`

`01_solver/diffsph_adapter/` does not reimplement an alternative SPH method
and does not patch third-party source.  It invokes the official scheme,
initializer and integrator while adding headless output, explicit device
selection, device auditing, deterministic CPU-canonical initial states, and
project metrics.  The exercised chain contains:

- particle sampling and 256-iteration official particle shuffle;
- a 2-D periodic domain and compact neighbor search;
- Wendland4 kernel and density computation;
- isothermal weakly-compressible EOS
  \(p=c_s^2(\rho-\rho_0)\);
- Antuono pressure term;
- DeltaSPH density diffusion (resolved default \(\delta=0.1\));
- DeltaSPH velocity diffusion (reachable coefficient
  \(\alpha=0.01\));
- symplectic-Euler time integration and state update;
- fixed-interval trajectory, numerical metrics and runtime metrics.

Canonical entry pattern:

```text
PYTHONPATH=01_solver PYTORCH_ENABLE_MPS_FALLBACK=0 \
python -m diffsph_adapter.run_tgv \
  --config 01_solver/configs/tgv_cpu_16.yml --run-id run-1
```

No core source patch was required.  Source provenance and the two upstream
limitations are captured verbatim in
`06_experiments/stage_01_tgv/logs/stage01_source_provenance.txt`.

### Configuration used

Common configuration:

| Quantity | Value |
|---|---|
| Domain | \([-1,1)\times[-1,1)\), periodic in both axes |
| Initial density | \(\rho_0=1\) |
| Initial velocity | \(u_x=-\sin(\pi x)\cos(\pi y)\), \(u_y=\cos(\pi x)\sin(\pi y)\) |
| Scheme | `DeltaSPH` |
| Kernel | `Wendland4` |
| \(n_h\) / target neighbors | 4 / \(16\pi\approx50.2655\) |
| Pressure | `Antuono` |
| EOS | `isoThermal`, \(p=c_s^2(\rho-\rho_0)\) |
| Density diffusion | DeltaSPH, \(\delta=0.1\) default |
| Velocity diffusion | reachable hard-coded \(\alpha=0.01\) |
| Shifting | active, `delta`; free-surface handling off |
| Gravity / surface detection | off / off |
| Integrator | `symplecticEuler` |
| dtype / seed | `float32` / `20260731` |
| Time step | \(5\times10^{-4}\) |
| Canonical duration | 400 steps, nominal \(t=0.2\) |
| Metric interval | 20 steps |
| Warm-up | 3 steps on a deep copy, excluded from initial state |

The analytical diagnostic is

\[
\mathbf u(x,y,t)=\mathbf u(x,y,0)\exp(-2\nu_\mathrm{ref}\pi^2t).
\]

The official notebook's post-hoc mapping gives the following
resolution-dependent values:

| Grid | Particles | \(h\) | \(c_s\) | \(\nu_\mathrm{ref}\) | \(Re=UL/\nu_\mathrm{ref}\) |
|---|---:|---:|---:|---:|---:|
| 16×16 | 256 | 0.5 | 138.169957 | 0.143927039 | 13.895930 |
| 24×24 | 576 | 0.333333343 | 92.113305 | 0.063967575 | 31.265841 |
| 32×32 | 1024 | 0.25 | 69.084979 | 0.035981760 | 55.583718 |

The reference derivation and its limitation are recorded in
`01_solver/reference_solutions/taylor_green_analytic.md`.

Environment evidence reports Python `3.12.13`, PyTorch `2.13.0`,
diffSPH `0.2.1`, torchCompactRadius `0.5.5`, `arm64`, available MPS,
`pip check` success, and no CUDA/cuDNN/NVIDIA package-name match:
`06_experiments/stage_01_tgv/logs/stage01_environment_validation.txt`.

## 3. CPU decision

**Decision: PASS.**

CPU completed all three required sizes in the required order, twice per
configuration.  Every run reached 400 steps with no NaN/Inf, no unsupported
operator, no first-failure step and no device mismatch.  The two repeats at
each resolution produced identical final-state SHA-256 values and exactly
identical numerical metric histories.

| Particles | Mean startup (s) | Mean warm-up (s) | Mean step (s) | Mean wall time (s) | Peak RSS range (bytes) |
|---:|---:|---:|---:|---:|---:|
| 256 | 3.6563 | 0.07995 | 0.014436 | 5.8539 | 432717824–433192960 |
| 576 | 4.3877 | 0.09274 | 0.018146 | 7.3405 | 438878208–440598528 |
| 1024 | 6.2064 | 0.12699 | 0.027594 | 11.1287 | 459505664–461914112 |

The CPU repeat runtime range was 0.30–3.77%, while numerical outputs were
exact.  Evidence is in the CPU summary rows of
`07_reports/stage_01_runtime_metrics.csv` and the
`cpu_n*_run-*.txt` logs.

## 4. MPS decision

**Decision: CONDITIONAL PASS, not pure-MPS PASS.**

MPS completed 256 and 1024 particles twice, plus the 1024-particle 600-second
test.  In every audited full step, all 85 state/domain/update tensors were on
`mps:0`; no PyTorch unsupported operator was raised and
`PYTORCH_ENABLE_MPS_FALLBACK=0`.  The conditional 576-particle fallback was
not invoked because both 1024-particle canonical runs completed.

Nevertheless, the dependency itself explicitly transfers neighbor-search
inputs to CPU.  Every MPS runtime summary therefore truthfully records:

```text
device_fallback = True
device_fallback_type =
torchCompactRadius_compact_neighbor_search_cpu_bridge
pytorch_mps_fallback = False
```

| Particles | Mean startup (s) | Mean warm-up (s) | Mean step (s) | Mean wall time (s) | Final MPS allocation |
|---:|---:|---:|---:|---:|---:|
| 256 | 4.3792 | 0.60568 | 0.119863 | 48.5812 | 3.65 MB current / 44.47 MB driver |
| 1024 | 7.1107 | 0.62205 | 0.171629 | 69.3209 | 7.91 MB current / 341–342 MB driver |

MPS repeats did not produce identical final hashes.  Across all recorded
times and metrics, the maximum repeat differences were
\(1.99\times10^{-5}\) at 256 particles and
\(1.07\times10^{-5}\) at 1024 particles.  This small nondeterminism is
retained as `REPEAT_DIFFERENCE` in the runtime CSV and is not hidden.

## 5. CPU/MPS differences

CPU and MPS used byte-identical CPU-canonical initial states.  Their initial
state hashes match at each resolution, including:

```text
16×16: 71ae6b619257084c7cbd93c266882c2b9df3e3b71d898f2ebc72f14edbaa71c8
32×32: 22bd4bacb0d8c36a021eb0f99ef756a968ef468f9adba75ac237b4525f425f17
```

At \(t\approx0.2\), the principal CPU/MPS metric differences are small:

- 16×16 velocity relative-L2 differs by at most
  \(5.73\times10^{-6}\) relative;
- 32×32 velocity relative-L2 differs by at most
  \(8.58\times10^{-7}\) relative;
- kinetic-energy relative error differs by at most
  \(1.33\times10^{-5}\) relative at 16×16 and
  \(4.22\times10^{-6}\) at 32×32;
- 32×32 relative momentum drift differs by 4.7–6.9% in relative terms,
  but both values are only \(2.5\)–\(2.7\times10^{-7}\); the absolute
  difference is below \(1.9\times10^{-8}\).

No unexplained order-of-magnitude CPU/MPS difference was found.  Performance,
however, strongly favors CPU: the tested hybrid MPS path was about 8.30×
slower per step at 256 particles and 6.22× slower at 1024 particles.  This is
consistent with small workloads plus repeated MPS↔CPU neighbor-search
transfers.

## 6. Three-resolution results

The table uses CPU run 1 at the final canonical sample; CPU run 2 is
numerically identical.

| Metric | 256 | 576 | 1024 |
|---|---:|---:|---:|
| Velocity relative L2 | 0.520431 | 0.219682 | 0.121579 |
| Velocity RMSE | 0.147239 | 0.0853635 | 0.0527593 |
| Total kinetic energy | 0.522363 | 0.893031 | 0.939320 |
| Kinetic-energy relative error | 0.631531 | 0.478606 | 0.247017 |
| Energy change from initial | 0.476622 | 0.106969 | 0.0606802 |
| Relative momentum drift | 0.00393636 | \(4.66260\times10^{-7}\) | \(2.53383\times10^{-7}\) |
| Mean density | 1.000397 | 1.001603 | 1.001601 |
| Min density | 0.999903 | 1.001503 | 1.001493 |
| Max density | 1.000792 | 1.001768 | 1.001805 |
| Relative density fluctuation | 0.0007918 | 0.0017684 | 0.0018046 |
| Maximum particle speed | 0.846831 | 0.941432 | 0.969860 |
| NaN/Inf | no | no | no |

Full time histories, rather than only this endpoint, are retained in
`07_reports/stage_01_numerical_metrics.csv`.

## 7. Error and resolution trend

The observed official-demo trend is favorable:

- velocity relative-L2 decreases
  \(0.5204\rightarrow0.2197\rightarrow0.1216\);
- velocity RMSE decreases
  \(0.1472\rightarrow0.08536\rightarrow0.05276\);
- kinetic-energy relative error decreases
  \(0.6315\rightarrow0.4786\rightarrow0.2470\);
- energy change from the initial state decreases
  \(0.4766\rightarrow0.1070\rightarrow0.06068\).

Density fluctuation does not decrease monotonically:
\(0.000792\rightarrow0.001768\rightarrow0.001805\), but remains bounded
below 0.00181 at the canonical endpoint.  The full velocity and energy curves
move closer to their resolution-specific references.

This report therefore states **resolution trend**, not strict convergence or
convergence order.  Because \(\nu_\mathrm{ref}\) and Re vary across the three
grids, the trend cannot prove convergence for one fixed physical
Taylor–Green problem.  No parameter was tuned after seeing the results.

## 8. Conservation and energy

The 24×24 and 32×32 momentum drift is at the \(10^{-7}\) level.  The
16×16 case reaches 0.00394, a visible low-resolution error that is retained in
the linear-range plot; it is not clipped or removed.  All density ranges stay
close to \(\rho_0=1\), and no canonical state becomes non-finite.

The large 16×16 analytical energy error and rapid energy loss are consistent
with the very large post-hoc viscosity at that resolution.  Increasing
resolution reduces both energy loss and analytical energy error.  Because the
viscosity mapping is only a post-hoc estimate, these curves are diagnostics,
not a calibrated physical-viscosity validation.

Plots:

- `06_experiments/stage_01_tgv/figures/velocity_error_vs_time.png`
- `06_experiments/stage_01_tgv/figures/kinetic_energy_vs_time.png`
- `06_experiments/stage_01_tgv/figures/momentum_drift_vs_time.png`
- `06_experiments/stage_01_tgv/figures/density_fluctuation_vs_time.png`
- `06_experiments/stage_01_tgv/figures/final_velocity_field.png`

## 9. Multi-step automatic differentiation

**Decision: PASS for \(dL/d\alpha\), where \(\alpha\) is initial velocity
amplitude.**

On both CPU and MPS, three complete SPH steps retained the graph, all 85
audited tensors stayed on the requested device, and the final gradient was
finite and non-zero.

| Backend | Autograd gradient | Centered finite difference | Relative difference |
|---|---:|---:|---:|
| CPU | -0.0489228778 | -0.0488819787 | 0.000835990 |
| MPS | -0.0489228889 | -0.0488820951 | 0.000833839 |

The MPS neighbor topology is selected through a detached CPU search, so this
test validates the differentiable velocity-value path and does not claim
differentiability of discrete neighbor changes with respect to position.
Details and per-step `grad_fn` records are in
`07_reports/stage_01_gradient_check.md` and
`06_experiments/stage_01_tgv/processed/gradient_check.json`.

## 10. Sustained run and memory behavior

**Decision: PASS for 1024-particle, 10-minute process/resource stability,
with measurable thermal-performance slowdown.**

The hybrid MPS run completed 3276 steps in 600.115864 seconds.  The runtime
CSV contains one summary and 20 approximately 30-second segments.

| Quantity | Observed value |
|---|---:|
| Overall mean step time | 0.181129 s |
| Min / max individual step | 0.061510 / 0.361594 s |
| First-half segment mean | 0.167266 s |
| Second-half segment mean | 0.198872 s |
| Second-half increase | 18.90% |
| Current MPS allocation, first / last segment | 7.77 / 7.68 MB |
| Driver allocation, first / last segment | 248.5 / 478.4 MB |
| Process peak RSS, first / final high-water mark | 1.113 / 1.209 GB |
| PyTorch recommended maximum | 12.713 GB |
| Process killed / memory pressure | no / not observed |
| NaN/Inf / unsupported operator | no / no |

Current allocation did not grow.  Driver allocation rose as caching warmed,
but its growth slowed markedly in the second half; this does not look like an
active-tensor leak, although a 10-minute run cannot rule out longer-horizon
driver-cache growth.

Segment means rose from roughly 0.16–0.17 s/step to a later plateau near
0.19–0.20 s/step.  On this fanless machine, thermal steady state or throttling
is the most plausible explanation, but that is an inference from wall-clock
segments, not a temperature measurement.

The final fixed-interval numerical record is step 3260 at
\(t\approx1.63\).  It remains finite; maximum density fluctuation over the
long run is 0.003672 and relative momentum drift remains near
\(2.5\times10^{-6}\).  However, the analytical velocity error reaches 1.43
and analytical energy error reaches 4.86.  Long-time physical fidelity is
therefore **not** established by this resource test.

Evidence:
`06_experiments/stage_01_tgv/logs/mps_n32_stability-600s.txt` and the
`analysis_role=stability` rows in both aggregate CSV files.

## 11. Known failures and limitations

1. **Preserved pre-fix trial.**  The first CPU 16×16 trial used an incorrect
   fixed analytical viscosity assumption.  It was not deleted or mixed into
   aggregate results; it is preserved under the
   `cpu_n16_pre-reference-fix_run-1` stem and explicitly excluded by the
   analysis audit.
2. **No fixed-Re convergence claim.**  Reachable upstream code hard-codes
   velocity-diffusion \(\alpha=0.01\); the later configuration lookup is
   unreachable after a `return`.
3. **Hybrid MPS.**  Neighbor search is CPU-backed and explicitly detaches
   positions.  MPS is not an all-operator native accelerator path.
4. **MPS nondeterminism.**  Repeated MPS final hashes differ, although metric
   differences remain \(O(10^{-5})\) or smaller.
5. **MPS performance.**  The tested hybrid MPS path is 6.2–8.3× slower per
   step than CPU and shows an approximately 19% first-half/second-half
   long-run slowdown.
6. **Long-time analytical mismatch.**  The 10-minute resource run remains
   finite but does not track the post-hoc analytical reference at late time.
7. **Scope of operator support.**  The default DeltaSPH TGV chain produced no
   unsupported operator.  This does not validate unexercised diffSPH schemes
   or switches.
8. **Warnings.**  Final pytest reports 430 warnings, chiefly upstream
   `torch.jit.script` deprecation notices, default-support warnings, and
   checkpoint warnings.  There are no test failures or skips.
9. **Git scope.**  Experiment metadata records the frozen project base
   `4b5821b1eebaee4b102631e7095f5bec2896eefb`, exact package versions, and
   third-party Python-tree hashes.  Stage 01 has not been tagged or committed
   in this stage; it should be reviewed and frozen before Stage 02.

## 12. Recommendation on entering Stage 02

**Recommendation: enter Stage 02 only conditionally, after review and a
Stage 01 freeze.  Stage 02 has not been started.**

The full solver, short-time resolution trend and tested amplitude gradient are
sufficient for a two-dimensional proof-of-concept baseline.  Before making
quantitative fixed-viscosity or fixed-Re claims, the project should select an
upstream version or separately reviewed patch/configuration in which physical
viscosity is actually controlled.  That decision is outside Stage 01 and no
core solver rewrite was attempted here.

## 13. Recommended backend and verified safe size

- **Primary backend:** CPU.  It is the fastest tested complete path, is
  exactly repeatable in these runs, and avoids MPS↔CPU neighbor transfers.
- **Verified safe particle count:** 1024 particles for the next PoC step.
  This is a measured ceiling, not a theoretical hardware limit; larger cases
  were not tested and should not be called safe from this evidence.
- **MPS use:** optional experimental comparison only, limited to 1024
  particles until a native neighbor-search path exists.  It was resource-safe
  for 10 minutes but slower and mildly nondeterministic.

## 14. Evidence map

| Evidence | Project-relative path |
|---|---|
| Aggregate numerical metrics | `07_reports/stage_01_numerical_metrics.csv` |
| Aggregate runtime/repeat/stability metrics | `07_reports/stage_01_runtime_metrics.csv` |
| Gradient report | `07_reports/stage_01_gradient_check.md` |
| Canonical YAML configs | `01_solver/configs/tgv_*.yml` |
| Resolved per-run configs | `06_experiments/stage_01_tgv/raw/*_config.json` |
| Raw trajectories and per-run CSV | `06_experiments/stage_01_tgv/raw/` |
| Complete canonical logs | `06_experiments/stage_01_tgv/logs/{cpu,mps}_n*_run-*.txt` |
| Stability log | `06_experiments/stage_01_tgv/logs/mps_n32_stability-600s.txt` |
| Source provenance | `06_experiments/stage_01_tgv/logs/stage01_source_provenance.txt` |
| Environment/package validation | `06_experiments/stage_01_tgv/logs/stage01_environment_validation.txt` |
| Aggregate artifact/repeat audit | `06_experiments/stage_01_tgv/logs/stage01_analysis_validation.txt` |
| Final pytest output | `06_experiments/stage_01_tgv/logs/final_pytest.txt` |
| Required figures | `06_experiments/stage_01_tgv/figures/` |
| Adapter | `01_solver/diffsph_adapter/` |
| Metric implementations | `05_metrics/` |
| Tests | `tests/` |
| Preserved excluded trial | `06_experiments/stage_01_tgv/raw/cpu_n16_pre-reference-fix_run-1_*` |

Final pytest result:

```text
22 passed, 0 failed, 0 skipped, 430 warnings in 5.10 s
```

**Final Stage 01 status: CONDITIONAL PASS.**
