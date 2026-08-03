# Stage 01G-P — Metric and gate contract audit

## Shear metrics

The frozen evaluator contract includes velocity vector L2/Linf, periodic position L2/Linf, fitted decay rate, amplitude ratio, density L2/Linf drift, pressure L2/Linf, transverse leakage, momentum, viscous power, and topology/resource/determinism. These support SHEAR1–SHEAR8 without an unregistered metric.

## Acoustic metrics

The frozen contract includes density/velocity fundamental amplitudes, phase speed, one-period phase error, density/velocity signal-normalized L2, pressure error, second-harmonic/fundamental ratio, transverse leakage, mean momentum drift, mean density/pressure bias, and topology/resource/determinism. These support ACOUSTIC1–ACOUSTIC10.

## Normalization and immutability

Field norms are particle-volume weighted; vector composition, minimum-image position error, modal projection, phase construction, harmonic ratio, spatial ordering, and time-step sensitivity are explicitly defined. Zero-signal relative metrics have a declared absolute-diagnostic treatment. An epsilon denominator is explicitly forbidden. There is no hidden normalization.

Metrics are evaluator-only. `threshold_changes_after_results_authorized` is false; metric feedback to RHS, initialization, reference, or thresholds is prohibited. Main dt, half dt, common times, thresholds, and run IDs are present in the frozen tag and match current files byte-for-byte.

Metric and gate contract audit: **PASS**.
