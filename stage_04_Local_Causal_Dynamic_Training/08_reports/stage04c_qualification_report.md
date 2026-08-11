# Stage 04C Qualification Report

Formal evidence is complete: D1 144, D2 216, D3 504, total 864 probes. Reverse/JVP passed 100%; no sign mismatch, topology change, parameter mutation, access violation, structural failure, or resource failure occurred.

| Arm | Group | Passed lineages | Required | Pass |
|---|---|---|---|---|
| D1 | D1_TOKEN_ENCODER | 0 | 6 | False |
| D1 | D1_PAIR_HEAD | 0 | 6 | False |
| D2 | D2_TOKEN_ENCODER | 0 | 6 | False |
| D2 | D2_GRU | 0 | 6 | False |
| D2 | D2_PAIR_HEAD | 0 | 6 | False |
| D3 | D3_TOKEN_ENCODER | 0 | 6 | False |
| D3 | D3_ATTENTION_O | 0 | 6 | False |
| D3 | D3_FEED_FORWARD | 0 | 6 | False |
| D3 | D3_PAIR_HEAD | 0 | 6 | False |
| D3 | D3_ATTENTION_Q | 0 | 6 | False |
| D3 | D3_ATTENTION_K | 0 | 6 | False |
| D3 | D3_ATTENTION_V | 0 | 6 | False |

The decisive hard-gate failure is `all_near_zero`: 864/864 probes have all three directional task-loss components below 1e−10. The contract forbids treating an all-near-zero probe as qualification evidence. Consequently every arm has 0% probe pass rate, below the required 85%, and every parameter group fails lineage coverage.

Verdict: `TASK_ALIGNED_PARAMETER_GRADIENT_NOT_QUALIFIED`.
