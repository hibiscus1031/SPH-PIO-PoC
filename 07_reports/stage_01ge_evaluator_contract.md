# Stage 01G-E evaluator contract

## Current frozen state

Stage 01G remains `INDEPENDENT_VALIDATION_AND_V2_DESIGN_APPROVED`; Stage 01G-P remains `INDEPENDENT_VALIDATION_EXECUTION_READY`. The current V2 state remains `V2_QUALIFICATION_EVIDENCE_INCOMPLETE` because the first execution preflight found no frozen executable independent-validation evaluator or authoritative hash.

Stage 01G-E adds a new evaluator qualification layer without modifying Stage 01G equations, run IDs, metrics, thresholds, uncertainty budget, V2 boundary, or the retained preflight failure.

## Read/write boundary

The evaluator accepts only mappings containing trajectory samples, independent reference samples, metadata, diagnostics, weights, and the frozen config hash. Schema validation deep-copies the evidence before metric computation. The caller’s trajectory and reference objects are never modified.

Outputs are newly allocated metric dictionaries, gate-result dictionaries, component-wise uncertainty records, provenance hashes, and Markdown qualification summaries. There is no API for modifying solver state, initialization, RHS, reference values, thresholds, or an input trajectory.

## Module design

| Module | Qualified responsibility |
|---|---|
| `common_metrics.py` | weighted vector/scalar norms, periodic error, modal projection, decay/phase fits, fixed relative-change rules |
| `shear_evaluator.py` | velocity/position error, decay, amplitude, density/pressure drift, leakage, momentum and diagnostics |
| `acoustic_evaluator.py` | fundamental amplitudes, phase speed/error, space-time signal errors, harmonic ratio, leakage, mean momentum drift and bias |
| `gate_rules.py` | immutable SHEAR1–8, ACOUSTIC1–10 and hard-safety binding |
| `uncertainty_report.py` | nine separate uncertainty components; no synthetic total GCI |
| `schema.py` | input/output shape, finiteness, common-time and deep-copy validation |
| `provenance.py` | frozen input identity and canonical evidence hashes |
| `report_generator.py` | deterministic report rendering only |

The evaluator neither generates analytic/linear reference data nor integrates any state.
