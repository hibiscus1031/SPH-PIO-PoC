# Stage 02M-P — Blind-family design

复用 Stage 02J-T/V generator source和mode/physics规则，无物理修改。两族均在 protocol hash 后按固定 root seed 单次物化，无重抽、替换或结果依赖 regeneration：

| family | role | root seed | formula hash |
|---|---|---:|---|
| V02_BLIND_VALIDATION_01 | future_validation | 2026080501 | `sha256:28886b28ecad9e2bc0340b69094101ad4b89c72e7d48da8ea7ad4660ac7c973e` |
| V02_BLIND_TEST_01 | future_test | 2026080502 | `sha256:5e6a31f8512f2c8d14b2b8f15587273c404cd50c1d20f79af7c9d3810204c47d` |

每族恰有 N12/H2.6、N16/H2.6、N20/H2.6、N16/H2.2、N16/H3.0 五个完整图。
