# Stage 04C Access Control

Both START and END denial audits passed. The application allowlist rejected validation targets and sealed formula/state/target paths before OS-level reads; file permissions were not used as the sole seal.

| Counter | Final value |
|---|---|
| sealed_formula_decode_count | 0 |
| sealed_state_decode_count | 0 |
| sealed_target_decode_count | 0 |
| train_state_array_decode_count | 114 |
| validation_target_decode_count | 0 |

TRAIN state-array containers decoded: 114. All were resolved below `stage04b/exact_trajectories/train` by the frozen allowlist. No cross-role access occurred.
