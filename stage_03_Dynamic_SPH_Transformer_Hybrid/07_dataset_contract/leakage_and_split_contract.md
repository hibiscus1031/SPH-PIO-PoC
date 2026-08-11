# Leakage and split contract

The split atom is a complete lineage component. Before normalization or model access, construct the lineage graph, compute connected components, freeze component-to-role assignment, and audit that no component crosses training, validation, sealed test, or independent validation.

Random particle, edge, frame, or window splitting is forbidden. Overlapping windows cannot cross roles. Resolution, dt, support, restart/resample descendants, and alternative views remain in their root component. No role label may enter model features/state.

Validation supports preregistered development decisions only. Sealed test is accessed once under the test-release policy; independent D-R3/D-R4 remains isolated from threshold selection. Leakage discovery invalidates every connected affected artifact and requires a versioned re-split before further use.
