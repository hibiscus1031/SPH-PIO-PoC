# Stage 03A reference hierarchy report

D-R1 analytic/MMS trajectories verify code, loss plumbing, and AD/FD; MMS is not physical validation. D-R2 high-accuracy time integration of the same semidiscrete operator isolates time error but is not spatial truth. D-R3 source-free analytic/independent families are validation-only and isolated from training, normalization, and thresholds; candidates include shear decay, acoustic wave, and periodic vortex decay. D-R4 is a V&V-qualified external reference and is currently `NOT_AVAILABLE`; higher-resolution SPH alone is not D-R4.

The sample/split atom is a complete trajectory-family lineage component. Frames, particles, edges, overlapping windows, resolution/dt/support variants, restarts, resamples, and views are dependent. A shared analytic formula at changed resolution, dt, or start time is not automatically an independent physical family.

Stage 01 R3 evidence remains historical and cannot be converted to Stage 03 training or fresh blind evidence. New disjoint training, validation, sealed-test, and independent source-free families must be generated or qualified later. Reference uncertainty remains explicit; dominance is classified `DYN_REFERENCE_UNCERTAINTY_DOMINANT`. Stage 03A generated no trajectory.
