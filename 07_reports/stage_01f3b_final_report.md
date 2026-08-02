# Stage 01F3B — MMS convergence verification with qualified dense semidiscrete reference

## Final status

**MMS_CONVERGENCE_VERIFICATION_FAIL**

The single failing formal condition is CT2 for continuous-time velocity exact error. All semidiscrete RK2 order, formal space, source, conservation, topology, resource, reference, provenance and determinism requirements passed. Because CT1–CT5 are required for PASS and continuous-time trend must pass before CONDITIONAL is available, the strict result is FAIL rather than CONDITIONAL.

## 1. Stage 01F3-R freeze

Stage 01F3-R commit `f952147d8059f3319147ecde65c4edf370023bb4` is frozen by annotated tag `stage-01f3r-semidiscrete-reference-dense-equivalent`. Fourteen manifest hashes pass; its status remains `SEMIDISCRETE_REFERENCE_QUALIFIED_DENSE_EQUIVALENT`.

## 2. Historical Stage 01F3 FAIL

Stage 01F3 remains `MMS_CONVERGENCE_VERIFICATION_FAIL`. No old file, report, trajectory, tag or failure evidence was modified.

## 3. Dynamic topology contract

MMS-A retained constant edge identity. MMS-B used legal reciprocal cutoff crossings; identity count greater than one was allowed. Across every formal trajectory, duplicate/nonreciprocal edges, strict-support omissions, unexpected exterior edges and total structural defects were zero. State and RHS values were finite.

## 4. Prerequisite gate

The frozen Python 3.12 environment completed 236 pytest tests. Stage 01F3-R identities, Stage 01F/01F2 source identities, dense references, three sparse/dense RHS states, two fresh ten-step smokes, resource policy and child reclamation all passed.

## 5. Dense semidiscrete reference

The frozen three-level Stage 01F3-R dense all-pairs DOP853 NPZ files were used without modification. All ten RK2 semidiscrete trajectories remained more than 20 times above their reference uncertainty floors.

## 6. RK2 semidiscrete time order

MMS-A position/velocity fitted orders are `1.974/2.012`; MMS-B orders are `1.967/2.007`. Finest/coarsest error ratios are `0.00377–0.00430`, all local-median and valid-point gates pass, and SD1–SD6 pass for both solutions.

## 7. MMS-A/B continuous-time trends

All 10 trajectories and both successive-dt self-difference gates pass. Position, density and pressure settle onto spatial platforms. Velocity exact error, however, increases slightly from coarsest to finest: MMS-A `2.593688e-3→2.593997e-3` (+0.01195%); MMS-B `2.599595e-3→2.599676e-3` (+0.00312%). This violates strict CT2 for both solutions. Continuous exact-error fits are not called pure RK2 order.

## 8. Space timestep isolation

Candidate-step differences are below `5.3e-6` relatively, so `dt_space=6.25e-5` was frozen before formal N16/N24/N48 results.

## 9. Consistency-path space matrices

MMS-A passes A-S1–A-S6; MMS-B passes B-S1–B-S6. All primary errors decrease at all four resolutions. Global slopes range from 1.389 to 1.724. This is the preregistered increasing-neighbor consistency path, not a fixed-stencil single-h family.

## 10. Fixed-ratio diagnostic

All 8 hard paths pass. Fixed `H/dx=4.5` shows a clear kernel-density and pressure floor, especially from N32 to N48, while the formal increasing-neighbor path continues to improve substantially.

## 11. Conditional N64

No trigger fired: primary errors are monotone, local orders have positive sign, N48/N32 ratios are `0.52–0.55`, and the formal path is interpretable. N64 status is `NOT_REQUIRED`; it was not run.

## 12. Conservation, external force and energy

Maximum pair/internal/assembly/momentum residuals are `3.561e-16`, `2.284e-17`, `5.529e-16`, and `2.084e-17`. Maximum viscous power is negative. External power and kinetic-energy update diagnostics are retained at each sampled time; the largest energy-update defect is `1.036e-8` and has no preregistered hard gate.

## 13. Resources and determinism

All 46 child trajectories pass and are reclaimed. Peak RSS is 607 MB, maximum RSS growth 38.5 MB/9.96%, and maximum step-time ratio 1.071. All four deterministic repeats are bitwise identical in checkpoints, deterministic scalar summaries and topology event sequences.

## 14. Order and GCI qualification

Position, density and pressure do not meet the 25% local-order stability gate: **GCI not justified**. Velocity qualifies only for the increasing-neighbor path, with global order about 1.45 and a broad fine-grid GCI near 142%; no cross-variable GCI is claimed.

## 15. Numerical uncertainty

Semidiscrete reference and spatial timestep floors are well below their measured errors. The remaining limitation is cancellation between shrinking temporal error and dominant spatial velocity error, which approaches its platform from below and violates CT2's exact inequality.

## 16. Failures and limitations

Only CT2 failed. This result is retained even though the increase is small and mechanically explained. No reference, source, balance, resource, topology, separation, determinism or provenance hard failure occurred.

## 17. Unique Stage 01F3B status

The unique status is `MMS_CONVERGENCE_VERIFICATION_FAIL`.

## 18. Stage 01G eligibility

Stage 01G application is **not permitted**, because only `MMS_CONVERGENCE_VERIFICATION_PASS` authorizes it. Stage 01G was not started.

## 19. Downstream boundary

V3 and Stage 02 remain unstarted. No MLP, Transformer or attention model was trained, and no learning labels were generated. Historical Stage 01D2 and Stage 01F3 failures remain unchanged.

Machine-readable status: `06_experiments/stage_01f3b_mms_convergence/results/stage01f3b_evaluation.json`.
