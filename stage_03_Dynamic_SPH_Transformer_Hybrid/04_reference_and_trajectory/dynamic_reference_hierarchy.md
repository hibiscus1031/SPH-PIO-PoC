# Dynamic reference hierarchy

| Class | Definition and role | Qualification boundary |
|---|---|---|
| D-R1 | Analytic/manufactured-solution trajectories for code verification, rollout-loss plumbing, and AD/FD; controlled training families are possible only with family-isolated validation. | MMS verifies equations/code and is not physical validation. Source terms and exact solution must be recorded. |
| D-R2 | High-accuracy time integration (DOP853 or equivalent) of the same semidiscrete operator. | Isolates time-integration error; is not automatically spatial truth or independent validation. |
| D-R3 | Source-free analytic or genuinely independent validation, never used for training, normalization, or threshold selection. Candidates: viscous shear decay, acoustic wave, periodic vortex decay. | Independence and source-free status must be qualified per family. |
| D-R4 | V&V-qualified external reference: independent solver, analytic solution, experiment, or qualified high-fidelity configuration. | Current state `NOT_AVAILABLE`; higher-resolution SPH alone cannot be labeled D-R4. |

Every reference record must identify governing problem, operator/source, spatial and temporal discretization, tolerances, uncertainty, lineage, intended role, disallowed uses, and artifact hashes. Qualification is family-specific and cannot be inherited merely from a shared analytic formula.
