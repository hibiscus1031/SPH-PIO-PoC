# Trajectory sample schema

The future canonical sample is a whole trajectory or immutable rollout segment. Required metadata fields are: schema/version; root family and lineage-component IDs; parent/derivation edges; reference class and role; split/seal role; governing/source configuration hashes; initial and warm-start state hashes; particle count/dimension; mass, domain, EOS, support and boundary metadata; dt/time grid; accepted state and graph hashes; feature-schema/normalization hashes; valid mask; and uncertainty record.

Frame payloads contain accepted `x,v,rho` with EOS-derived `p`; persistent particle alignment; and graph reference/hash. Targets are stored in a physically separate target namespace and cannot be loaded by forward feature construction. Midpoint stages, if retained for verification, are explicitly `provisional` and never samples or history instants.

Particles, edges, frames, and overlapping windows are subrecords, not IID samples. Stage 03A defines the schema only and materializes no trajectory.
