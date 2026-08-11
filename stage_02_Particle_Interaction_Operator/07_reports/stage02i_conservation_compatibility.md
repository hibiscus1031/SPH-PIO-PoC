# Stage 02I — Conservation and Pair-Force Compatibility

For every primary target, the audit computes

\[
r_F=\frac{\lVert\sum_i m_i\Delta a_i\rVert}{\sum_i m_i\lVert\Delta a_i\rVert}
\]

against the inherited \(10^{-10}\) internal-force tolerance. No target mean is subtracted and no target vector is modified.

| Candidate class | Normalized total-force residual | Architecture compatibility |
|---|---:|---|
| N12/N16/N20 regular resolution | 2.36e-16–3.84e-16 | pair-force compatible |
| N16 regular support cases | 1.03e-16–3.84e-16 | pair-force compatible |
| N16 jitter-5% | 3.7199e-3 | node residual only |
| N16 jitter-10% | 1.2002e-2 | node residual only |

Five candidates are compatible with an antisymmetric pair-force architecture at the frozen tolerance. The two disorder candidates pass six-component scientific attribution but cannot be represented as a purely internal antisymmetric pair correction without changing the target; they are therefore retained as `node_residual_only`.

Torque and target power are reported for all cases as diagnostics only. No angular-momentum or dissipation qualification is inferred.

Machine audit: `04_target_attribution/qualified_spatial_targets/conservation/conservation_compatibility_audit.json`.
