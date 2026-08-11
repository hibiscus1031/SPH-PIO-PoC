# Stage 02I — Freeze and Scope

## Read-only freeze

Before any Stage 02I target evaluation, a SHA-256 manifest froze 12 Stage 02H/02G/02B artifacts and all 12 accepted-reference evidence records from the Stage 02H six-case suite. The frozen inputs include the Stage 02H final report, candidate matrix/results, bias and cross-reference evidence, acceptance rules/results, Stage 02G attribution closure, and Stage 02B schema, eligibility, split, and uncertainty contracts.

Accepted reference IDs remain:

- primary: `H_REF_FOURIER2`;
- secondary independent check: `H_REF_ANALYTIC`.

Diagnostic references `H_REF_QWLS2_INCUMBENT` and `H_REF_CWLS3` remain present and are excluded from target construction. No Stage 02H threshold, verdict, or diagnostic candidate was modified.

## Target and operator scope

The primary target is `a_H_REF_FOURIER2 - a_SPH`; the secondary target is `a_H_REF_ANALYTIC - a_SPH`. Their difference is stored directly. No averaging, post-hoc weighting, or error-dependent reference selection is permitted.

Both references and baseline SPH evaluate the same density and pressure fields, isothermal EOS, viscosity coefficient, pressure-plus-viscosity terms, timestamp, and periodic domain. No external source, trajectory replacement, convective derivative, temporal derivative, finite-difference velocity derivative, or time integrator is used.

The resulting compatibility label is restricted to `PASS_WITHIN_FROZEN_SPATIAL_OPERATOR_SCOPE`. It does not imply full-PDE trajectory exactness, Stage 01 V2 PASS, arbitrary-flow continuum alignment, or confirmation of the viscosity operator form.

Evidence: `04_target_attribution/qualified_spatial_targets/freeze/`.
