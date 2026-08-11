# Full-Gradient Norm Gate

Stage 05C evaluates the complete `L_def` gradient with respect to every preregistered optimizer parameter group. For each group it must report gradient L2 norm, elementwise RMS, Linf norm, finite count, nonzero count, total count, and deterministic-repeat agreement.

Qualification is group-aware and optimizer-aligned. A single unit random direction and a fixed absolute directional threshold may not serve as the sole hard gate. Stage 05C must preregister finite/nonzero tolerances, repeat tolerances, required group coverage, aggregation rules, and failure statuses before any derivative evaluation.

This evidence cannot alter Stage 04C: its 864/864 failures, 2592 near-zero components, and zero qualified groups remain historical facts under the former contract.
