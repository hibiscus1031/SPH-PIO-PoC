# Reference lineage and role contract

| Root family | Frozen role |
|---|---|
| `DR1_LAGRANGIAN_COMPRESSION` | `component_verification_and_future_training_candidate` |
| `DR1_COUPLED_DEFORMATION` | `component_verification_and_future_training_candidate` |
| `DR2_SEMIDISCRETE_TIME_REFERENCE` | `time_error_isolation_only` |
| `DR3_OBLIQUE_SHEAR_A` | `independent_source_free_validation_only` |
| `DR3_OBLIQUE_SHEAR_B` | `independent_source_free_validation_only` |
| `ACOUSTIC_CANDIDATE` | `conditional_or_rejected` |
| `PERIODIC_VORTEX_CANDIDATE` | `qualified_or_reclassified_mms_only` |

Different `N`, dt/tolerance, `H/dx`, output time, integrator identity, or record view remains a descendant of the same physical/formula lineage. D-R1 being a future training candidate grants no dataset or training authorization in Stage 03B. D-R3 families are permanently excluded from future training, normalization, threshold selection, and architecture selection. Stage 01 shear/acoustic has role `historical_independent_evidence_only` and is neither renamed nor copied.
