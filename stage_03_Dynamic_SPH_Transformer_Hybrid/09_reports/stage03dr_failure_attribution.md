# Stage 03D-R Failure Attribution

Stage 03D remains `DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED`. Stage 03D-R contract: `sha256:63ef93fe7af7c10ffb6a6e1d944003b5e3e85818f98bac6f6b1b9333a479c2d9`.

All 144 failures have one primary reason. Counts: `{"AD_FD_DIRECTION_OR_SIGN_MISMATCH": 5, "DERIVATIVE_NEAR_STRUCTURAL_ZERO": 29, "FD_NONMONOTONE_NO_ADJACENT_WINDOW": 69, "FD_ROUNDOFF_DOMINATED": 3, "FD_TRUNCATION_DOMINATED": 3, "NUMERICAL_NONSMOOTHNESS_WITH_FIXED_GRAPH": 16, "UNRESOLVED": 19}`. Reverse/JVP contradiction is never silently attributed to FD; history object/detach mismatches, cancellation, horizon scaling, near-zero sensitivity, roundoff/truncation and fixed-graph non-smoothness follow the frozen priority order.
