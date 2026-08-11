# Stage 07A role transition

- `LCDF_01`, `LCDF_04`, `LCDF_05`, `LCDF_06`, `LCDF_07`, `LCDF_08`: remain `ANCHOR_TRAIN_V1` and enter future TRAIN_V2.
- `LCDF_02`, `LCDF_09`: permanently become `CONSUMED_VALIDATION_V1_DIAGNOSTIC_ONLY`; no checkpoint selection, gate, hyperparameter choice, or fresh-validation claim is permitted.
- `LCDF_03`, `LCDF_10`: remain `SEALED_TEST_V1`; formula/state/source/target/origin decode counters remain zero.
- Eight prospectively hash-assigned heterogeneous lineages become `NEW_TRAIN_V2`.
- Four prospectively hash-assigned heterogeneous lineages become `FRESH_VALIDATION_V2` and remain payload-sealed.

TRAIN_V2 identity is exactly six anchors plus eight new lineages. Consumed validation is not moved into TRAIN_V2.

