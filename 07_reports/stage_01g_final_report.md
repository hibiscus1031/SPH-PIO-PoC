# Stage 01G final report — Independent Benchmark Validation and V2 Qualification Design

## 1. Stage 01F5B freeze

Stage 01F5B remains uniquely `PLATEAU_AWARE_MMS_REQUALIFICATION_PASS`. Its final report, final evaluation, canonical run-status table, 339-item final SHA-256 inventory, reference qualification, T/P/H/S evidence, N64 branch, determinism, source-tree identity, hard-safety records, trajectories, checkpoints, and failures remain unmodified.

## 2. Evidence/archive commit reconciliation

The final evidence snapshot is `ac8e06aa0ba3c5cc54fb567d1d40bd0f36e4487f`; the final archive is its descendant `6cbfea24cf1f2fd55f2bad0b949083ed4ab953c3`. Annotated tag `stage-01f5b-plateau-aware-mms-requalification-pass` points to the archive commit. Their only two differences are added attempt CSVs classified as report/manifest/test/archive metadata. Numerical source, evaluator scientific logic, gates/thresholds/configuration, run evidence/checkpoints, and qualification data have zero differences. The detailed audit is in `stage_01g_f5b_freeze.md`.

## 3. Infrastructure retry preservation

The original `f5_n64_smoke_a` raw infrastructure failure is retained. It launched no solver and created no numerical state. The sole authorized `f5_n64_smoke_a_infra_retry1` and the evaluator’s reconciliation evidence are frozen; no scientific failure is reclassified.

## 4. Benchmark A: viscous transverse shear wave

On \([-1,1)^2\), \(\rho_0=1\), \(c_s=20\), \(\nu=0.02\), \(U_s=0.5\), \(k_s=2\pi\), and \(t_f=0.2\). The source-free closed form is

\[
\rho=\rho_0,\ p=0,\ u_x=U_s\sin(k_sy)e^{-\nu k_s^2t},\ u_y=0,
\]

with unwrapped trajectory

\[
x=x_0+U_s\sin(k_sy_0)(1-e^{-\nu k_s^2t})/(\nu k_s^2),\quad y=y_0.
\]

Uniform mass is \(m_i=\rho_0(2/N)^2\). This is not free-surface, wall-boundary, or turbulence validation.

## 5. Benchmark B: low-amplitude acoustic standing wave

On the same domain, \(\rho_0=1\), \(c_s=20\), \(\nu=0\), \(k_a=\pi\), and \(t_f=0.1\). Independent linear theory gives

\[
\rho=\rho_0[1+\epsilon_a\cos(k_ax)\cos(c_sk_at)],
\quad u_x=c_s\epsilon_a\sin(k_ax)\sin(c_sk_at),\quad u_y=0,
\]
\[
p=c_s^2(\rho-\rho_0).
\]

The main amplitude is 0.005; 0.0025 and 0.01 complete the amplitude audit. Initial masses are \(m_i=\rho(x_i,0)(2/N)^2\), remain fixed, and numerical density always comes from the kernel sum. This is linear-acoustic-regime validation only. Finite-amplitude bias is model-form uncertainty, not pure numerical error.

## 6. Preregistered validation matrices

The five shear IDs are `g_shear_n24`, `g_shear_n32`, `g_shear_n48`, `g_shear_n32_dt_half`, and `g_shear_n48_rep2`. The seven acoustic IDs are `g_acoustic_e5e3_n24`, `g_acoustic_e5e3_n32`, `g_acoustic_e5e3_n48`, `g_acoustic_e5e3_n32_dt_half`, `g_acoustic_e5e3_n48_rep2`, `g_acoustic_e2p5e3_n48`, and `g_acoustic_e1e2_n48`.

Formal N values are 24, 32, and 48; H/dx values are respectively 4.5, 5.049509756796392, and 5.5. Main dt is 6.25e-5; N32 half-dt is 3.125e-5. Every ID has a separate future directory. Integer-tick common times are frozen in the design configuration and full matrix CSV.

## 7. Qualification gates

SHEAR1–SHEAR8 freeze finite/hard safety, N48 velocity L2 (0.02), decay rate (0.02), position L2 (0.01), density Linf drift (5e-3), transverse leakage (1e-3), strict N24>N32>N48 velocity/position ordering, and N32 time-step sensitivity (0.10).

ACOUSTIC1–ACOUSTIC10 freeze finite/hard safety, N48 phase speed (0.02), density and velocity fundamental amplitudes (0.05 each), one-period signal-normalized L2 (0.10 each), transverse leakage (1e-3), strict main-amplitude spatial ordering, N32 time-step sensitivity (0.10), non-increasing nonlinear contamination as epsilon decreases, and the linear-regime claim boundary. The exact wording is in the benchmark reports and `preregistered_stage01g.yml`.

All runs inherit the Stage 01F5B conservation, topology, resource, determinism, child-process, GC, and reclamation gates. Because both cases are source-free, source call count is zero and external-force balance cannot replace internal momentum conservation.

## 8. Independence and inverse-crime protection

Neither benchmark uses \(f_{MMS}\), a Stage 01F source adapter, project RK2 for the reference, or Stage 01F3B/F3C/F5B trajectories/errors as validation points. Shear uses an analytic continuum field and analytic trajectory; acoustics uses independent linear theory. Validation metrics do not enter solver RHS, and references are never corrected by SPH residuals. Thresholds are immutable after results exist.

## 9. Uncertainty budget

The mandatory components are analytic/linear reference, RK2 time-step, increasing-neighbor spatial envelope, N48/N32 difference, float64 determinism, acoustic finite-amplitude model form, kernel-density/EOS background, topology/resource, and the Stage 01F5B `GCI not justified` limitation. GCI failure does not permit omission, and no false scalar total GCI may be generated.

## 10. V2 evidence map

V1/code verification maps to Stage 01C, 01F, 01F2, and 01F3-R. Solution verification maps to Stage 01F5B T/P/H/S, references, determinism, N64, and hard safety. Independent validation is reserved for future shear and acoustic evidence. Uncertainty maps to reference, time-step, spatial envelope, acoustic amplitude/model form, determinism, resources, and GCI limitation.

No V2 state is generated in Stage 01G. A later pass requires every shear and acoustic gate plus frozen identity, hard safety, complete uncertainty, and complete provenance. A core-gate failure means `V2_QUALIFICATION_FAIL`; missing evidence means `V2_QUALIFICATION_EVIDENCE_INCOMPLETE`.

## 11. Domain of validity

The preregistered domain is 2D, periodic, smooth weakly compressible, low-Mach flow using Wendland C4, frozen EOS and pressure/viscosity operators, CPU float64, and the tested resolution/support range.

## 12. Explicit exclusions

Free surfaces, solid-wall boundaries, shocks, multiphase flow, FSI, turbulence, 3D, and learned correctors are excluded.

## 13. Unique Stage 01G design status

`INDEPENDENT_VALIDATION_AND_V2_DESIGN_APPROVED`

Commit identity is reconciled; both source-free benchmarks, parameters, metrics, thresholds, run IDs, independence boundary, model-form boundary, uncertainty budget, V2 evidence map, and provenance are complete. Numerical execution count is zero.

## 14. Eligibility for the next application

The project is eligible to **apply for a separately authorized independent-validation execution stage**. Stage 01G itself is not execution authority and no benchmark has been run.

## 15. Downstream boundary

V3 and Stage 02 remain unstarted. Model training and learning-label generation remain unstarted and unauthorized. Even a future V2 pass will not start them automatically.
