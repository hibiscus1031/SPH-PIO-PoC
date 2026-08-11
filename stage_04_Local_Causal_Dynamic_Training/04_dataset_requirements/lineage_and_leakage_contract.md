# Lineage and leakage contract

## Split atom

The indivisible split atom is the complete analytic formula-lineage component. Every trajectory, resolution, timestep, phase, amplitude, support choice, low-Mach setting, and all overlapping origins/windows derived from that component must remain in one downstream role.

## Prohibited splits

Random frame, overlapping-window, random particle, and random edge splits are prohibited. Near-identical material-map variants may not be relabeled as independent families merely because numerical controls differ. Deduplication and lineage-component assignment must precede role allocation.

## Information leakage

Training-role data alone may fit learned parameters and training normalization statistics. Validation families may be used only under the Stage 04D checkpoint/selection contract and may not determine component weights retrospectively. Sealed-test targets/states and independent D-R3 targets/states may not influence training, normalization, validation selection, thresholds, architecture, budget, or checkpoint rules.

All artifacts must carry formula identifier, lineage-component identifier, generation-config hash, trajectory identifier, origin identifier, role, and parent provenance. Any lineage collision across roles invalidates the affected split until corrected before test release.
