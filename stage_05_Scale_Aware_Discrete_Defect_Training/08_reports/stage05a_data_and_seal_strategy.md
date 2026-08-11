# Stage 05A Data and Seal Strategy

Stage 05 reuses Stage 04B read-only: TRAIN `LCDF_01/04/05/06/07/08`, VALIDATION `LCDF_02/09`, and SEALED_TEST `LCDF_03/10`. Formula components are split atoms; frames, windows, particles, edges, resolutions, and variants are not. Roles, trajectory identities, fixed-topology and analytic/DOP853 qualification, and formula/state/target seals are preserved with zero substitution or leakage.

Stages 05A–05C keep validation target decode and all sealed formula/state/target/origin decode counts at zero. Stage 05D may open validation only after the training protocol is frozen. The test remains closed until Stage 05F, when all training has ended and selected checkpoint hashes are closed; only then may a single audited release occur.

Stage 05A inspected public documents and manifest metadata only. It materialized no trajectory or target and decoded no payload.
