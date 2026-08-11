# Stage 06B Checkpoint and Selection Policy

Each future run saves update 0, every 20 updates, terminal, and selected identities. Selection is the minimum validation global-balanced Q_def; ties choose the earlier update; updates below 320 are recorded but ineligible. Sealed test and diagnostic metrics do not participate. Payload includes model, optimizer, scheduler, RNG, update, protocol hash, and run identity.
