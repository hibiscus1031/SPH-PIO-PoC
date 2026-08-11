# Analytic/MMS boundary

D-R1 manufactured solutions may verify dynamic RHS assembly, source injection, RK2 stage semantics, state-loss plumbing, causal history, and multistep AD/FD. The exact manufactured field, required source terms, periodicity, smoothness, and admissible parameter domain must be frozen before execution.

Any D-R1 family admitted to training must have its entire lineage component assigned to training. Validation/test MMS families require distinct root constructions and cannot be derived by changing only resolution, time step, support, start time, phase view, or window.

MMS is verification, not physical validation. Agreement with a source-forced manufactured trajectory cannot support claims about source-free physics, Stage 01 recovery, or D-R3/D-R4 validation. One-step acceleration diagnostics cannot replace state rollout verification.
