# Trajectory-family contract

The statistical sample is one complete trajectory family or one complete rollout segment carrying immutable family lineage. Particles, edges, frames, overlapping windows, and views are dependent observations, never IID split atoms.

A lineage component includes a root physical/analytic problem and every descendant sharing the same initial-condition construction or trajectory information: all frames/windows, resolutions, time-step variants, support variants, restarts, resamples, augmentations, and alternative views. Unless a later preregistered proof establishes independence before data access, all such descendants remain in one leakage component.

The split atom is the whole trajectory-family/lineage component. No random frame/window split is permitted. The same analytic formula at a different resolution, `dt`, or start time is not automatically an independent physical family. Every segment records root family ID, parent IDs, transformation/derivation edges, initial-state hash, reference class, solver/source configuration, and split role.

Stage 03A creates no trajectory payload and assigns no actual families to splits.
