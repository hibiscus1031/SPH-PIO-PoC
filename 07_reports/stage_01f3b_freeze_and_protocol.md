# Stage 01F3B freeze and protocol

## Frozen prerequisite

Stage 01F3-R final evidence commit is `f952147d8059f3319147ecde65c4edf370023bb4`. Annotated tag `stage-01f3r-semidiscrete-reference-dense-equivalent` resolves to that commit. Its unique status is `SEMIDISCRETE_REFERENCE_QUALIFIED_DENSE_EQUIVALENT`; the historical Stage 01F3 status remains `MMS_CONVERGENCE_VERIFICATION_FAIL`.

The Stage 01F3B manifest freezes the Stage 01F3-R final report, evaluator, 461-state sparse/dense evidence, 216-event topology evidence, cutoff evidence, MMS-A/B qualification JSON, dense reference NPZ files, pilot evidence, and the Stage 01F3 frozen manifest. Existing Stage 01F3 and Stage 01F3-R files are read-only for this stage.

## Frozen numerical protocol

- Semidiscrete RK2 time matrix: MMS-A/B, N16, `t_final=0.01`, five preregistered time steps, 11 common times, qualified dense DOP853 reference.
- Continuous MMS time matrix: MMS-A/B, N32, `t_final=0.02`, five preregistered time steps, 21 common times.
- Space-step isolation: N32 at `6.25e-5` and `3.125e-5`; selection is frozen before N16/N24/N48 results exist.
- Formal spatial path: N16/24/32/48 with increasing `H/dx`; conditional N64 only under the preregistered triggers and preflight.
- Diagnostic spatial path: fixed `H/dx=4.5`; it cannot replace the formal path.
- Determinism repeats use new Stage 01F3B run IDs and are separate child processes.

Every RK2 trajectory is executed in an independent child process with cyclic GC enabled and `torch.no_grad()`. No per-step tensor history is retained; only 11/21 physical-time checkpoints, scalar summaries, and relative evidence paths are returned. In-loop `gc.collect()` and disabling cyclic GC are prohibited.

## Dynamic-topology contract

MMS-A is expected to keep a constant edge identity. MMS-B may change identity through reciprocal cutoff crossings. Identity count greater than one is not a failure. Duplicate, nonreciprocal, omitted strict-support, unexpected exterior edges, other structural defects, nonfinite state/RHS, or unilateral switching are hard failures.

## Scope boundary

Stage 01F2 smoke, Stage 01F3 pilot, and Stage 01F3-R pilot are excluded from formal fits. Stage 01G, V3, Stage 02, training, and label generation remain outside scope.
