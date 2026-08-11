# Stage 02I-R Architecture Scope Decision

## Evidence chain

- The periodic continuum pressure, viscosity, and total integrals are zero: PASS.
- The baseline SPH reciprocal topology and pairwise cancellation are exact up to roundoff: PASS.
- Fourier and analytic references agree on both the field and jitter residual: PASS.
- The jitter residual follows the particle quadrature, not reference sensitivity or SPH topology.
- All 5 regular targets remain exactly representable by a general antisymmetric pair force within tolerance.
- Both jitter targets fail the general pair gate, and their node residuals exceed reference disagreement by factors above `5.9e9` and `5.3e10`.
- No target modification, mean subtraction, or projection writeback is allowed or used.

## Qualified decision

The prefrozen rules select `PAIR_ONLY_REGULAR_SCOPE`.

The legal future pair-force PIO scope contains exactly:

1. `i_res_n12_h26_regular`
2. `i_anchor_n16_h26_regular`
3. `i_res_n20_h26_regular`
4. `i_sup_n16_h22_regular`
5. `i_sup_n16_h30_regular`

The two jitter targets, `i_dis_n16_h26_jitter05` and `i_dis_n16_h26_jitter10`, remain preserved as distribution-shift validation/diagnostic evidence and are not pair-force training labels.

## Alternatives not selected

A versioned conservative target contract is not established because this stage has no independent, physically consistent, preregistered conservative reference quadrature. A hybrid pair/node architecture is not required because the node residual is attributed to particle quadrature contamination rather than to a stable physical/operator target component. The residual source is not unresolved: the continuum, SPH, dual-reference, quadrature, and incidence evidence are mutually consistent.

## Stage 02J boundary

Stage 02J is not executed in this stage. It is only limited-authorized for a future controlled dataset construction using the five listed regular candidates. Jitter labels, versioned targets, and hybrid node heads are outside that authorization.

No dataset, model, training, normalization, split, or performance result was generated.

