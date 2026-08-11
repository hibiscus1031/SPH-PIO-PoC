# Stage 02I-R Final Report

## 1. Stage 02I freeze

A SHA-256 manifest freezes 12 required Stage 02I/02H/02A evidence files and all seven individual Stage 02I target records. Existing Stage 01 and Stage 02A–02I files were treated as read-only inputs.

## 2. Seven-candidate preservation

All 7 `candidate_discretization_target` records are preserved without reclassification: 5 historical `pair_force_compatible` and 2 historical `node_residual_only`. The historical Stage 02J authorization remains recorded as `false`; this stage does not rewrite that record.

## 3. Pressure/viscosity/total force decomposition

For every case and component, `F_ref`, `F_SPH`, and `F_target` were computed using forward, reverse, and Kahan float64 sums. All identities `F_target = F_ref - F_SPH` pass deterministic repetition. The five regular residuals are roundoff scale. Jitter05 and jitter10 total normalized residuals are `3.719907e-3` and `1.200237e-2`; their pressure residuals are `3.720178e-3` and `1.199582e-2`, and viscosity residuals are `5.452967e-3` and `1.710758e-2`.

## 4. SPH pairwise cancellation

All seven reciprocal graphs pass topology checks. Pressure, viscosity, and total pair antisymmetry residuals are exactly zero by construction; global SPH normalized residuals are approximately `1e-17`, below the Stage 01 `1e-10` tolerance. Baseline SPH conservation failure is not triggered.

## 5. Continuum momentum balance

Analytic and Fourier integrals are exactly `(0,0)` for pressure, viscosity, and total. A 512×512 periodic quadrature returns a total of approximately `(-1.025e-18,-7.526e-19)`. The continuum balance is PASS and the frozen operator is globally pair-force compatible.

## 6. Particle quadrature attribution

Under the frozen masses, the jitter reference sums reproduce the target residuals while the continuum integral is zero. Zeroth/first-moment defects increase from `1.34016e-2/9.98945e-4` at jitter05 to `2.78877e-2/2.11220e-3` at jitter10, and minimum coverage isotropy decreases from `0.921065` to `0.856082`. Volume weighting is diagnostic only and is not used to alter labels. The residual source is particle quadrature contamination under the frozen equal-mass target contract.

## 7. Fourier/analytic conservation comparison

The two independent references agree: jitter total-force differences are `2.57115e-17` and `4.96092e-17`, with field RMS differences `2.74857e-14` and `1.71647e-14`. Reference sensitivity remains closed.

## 8. General antisymmetric pair representability

The five regular cases pass exact representability within `1e-10`, with normalized projection residuals from `1.11e-15` to `3.66e-15`. Jitter05 and jitter10 fail with residuals `3.23544e-3` and `9.61310e-3`. General vector pair force is the linear-momentum hard gate.

## 9. Central-force diagnostic

All five regular cases also pass the central-pair diagnostic. Each jitter central residual equals its general-pair residual to numerical precision. Torque residuals are retained but do not override the general-pair gate.

## 10. Jitter pair/node decomposition

For jitter05, `||y_pair||=3.148475e-3`, `||y_node||=1.018676e-5`, and `||y_node||/||y||=3.23544e-3`. For jitter10, the values are `5.906646e-3`, `5.678379e-5`, and `9.61310e-3`. Spatial distributions, Fourier signatures, geometry correlations, and uncertainty comparisons are retained. Neither projection is written back.

## 11. Architecture scope decision

The prefrozen evidence rules select `PAIR_ONLY_REGULAR_SCOPE`. A versioned conservative target contract is not established, and a hybrid pair/node head is not physically required by the present evidence.

## 12. Stage 02J authorization

Stage 02J is not executed. Future Stage 02J work is limited-authorized only for the five regular candidates: `i_res_n12_h26_regular`, `i_anchor_n16_h26_regular`, `i_res_n20_h26_regular`, `i_sup_n16_h22_regular`, and `i_sup_n16_h30_regular`. The two jitter candidates remain distribution-shift validation/diagnostic evidence and are excluded as pair-force training labels.

## 13. No target modification

No original target was modified, mean-subtracted, overwritten, or replaced by a conservation projection.

## 14. No dataset

No dataset, sample set, split assignment, or normalization statistics were generated.

## 15. No model

No PIO implementation, Transformer, attention module, neural network, or optimizer was generated.

## 16. No training

No training, validation, benchmark execution, or performance claim was produced.

## 17. Historical boundaries unchanged

Stage 01 remains `V2_QUALIFICATION_FAIL`; Stage 01H remains `FINITE_RESOLUTION_DOMINANT`; viscosity operator form remains `NOT_CONFIRMED`; Stage 02I remains `QUALIFIED_SPATIAL_TARGET_POOL_NOT_READY` with 7 candidates, 5 pair-compatible and 2 node-residual-only. No historical conclusion was overwritten.

## Final unique state

CONSERVATION_COMPATIBILITY_RESOLVED_PAIR_ONLY
