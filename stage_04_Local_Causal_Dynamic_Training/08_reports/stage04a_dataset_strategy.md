# Stage 04A — Dataset strategy report

Stage 04 requires a new, prospectively generated and qualified D-R1 trajectory-family pool. The existing Stage 03B 18 trajectories cannot simply be repartitioned. Stage 04B must cover multiple independent analytic material-map formula lineages spanning compression, shear–compression coupling, rotating/deforming modes, multimode deformation, and controlled low-Mach regimes.

The split atom is the complete formula-lineage component. Variations of `N`, `dt`, phase, amplitude, or support remain in the same component unless a strict prospective contract establishes otherwise. Random frame, overlapping-window, particle, and edge splits are prohibited.

Complete components are assigned disjointly to train families, validation families, sealed-test families, and independent D-R3 validation. Before sealed-test release, target/state decode count is exactly zero. Test values cannot influence normalization, thresholds, checkpoint selection, budgets, or architecture.

D-R3 oblique shear remains `independent_validation_only` and cannot enter training, normalization, validation selection, or threshold selection. Its use is deferred to Stage 04G under a frozen protocol.

Stage 04A generates no trajectory, creates no test payload, and releases no target/state.
