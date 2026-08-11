# Family-lineage contract

Lineage is a graph with immutable root-family nodes and derivation edges for resolution, dt, support, restart, resample, window, augmentation/view, phase/start-time, and reference conversion. The leakage component is the connected component after treating all information-sharing derivation edges as undirected.

All frames, overlapping windows, refinements, support variants, restarts, resamples, and views of one root remain together unless an independence rule was frozen before generation and demonstrated without outcome access. A common analytic formula at different resolution/dt/start time remains one physical-formula family by default.

IDs and hashes are content-addressed and cannot be rewritten when split roles are assigned. Any lineage correction creates a new manifest version and invalidates affected splits/seals until requalified.
