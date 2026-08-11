# Stage 02C — Case Contract

规范清单见 `../03_dataset/cases/case_manifest.yaml`，版本为 `stage02c-case-manifest-1.0.0`。

## 1. Frozen case matrix

| case | role | trajectory family | resolution | H/dx | disorder | reference | horizon |
|---|---|---|---:|---:|---|---|---:|
| `r2_regular_n6` | positive pipeline | periodic low-Mach vortex / regular | 6×6 | 2.6 | regular | R2 dense+DOP853 | 0.002 s |
| `r2_jitter05_n8` | positive pipeline | periodic low-Mach vortex / jitter | 8×8 | 2.6 | 5% dx, seed 2202 | R2 dense+DOP853 | 0.002 s |
| `r2_duplicate_edge_negative_n6` | predefined rejection control | topology control | 6×6 | 2.6 | regular, seed 3303 | R2 dense+DOP853 | 0.002 s |

每个 case 物化 `t=0` 与 `t=0.002` 两个 frame。Manifest 同时冻结 initial-condition family、resolution family、
`h_over_dx_family`、disorder family、reference identity、seed 和 time horizon。

## 2. No post-hoc selection

`selection_policy=enumerate_all_manifest_cases_no_posthoc_filter`。所有预注册 case 均生成并保留；没有随机生成后
筛选。5% jitter 使用冻结 seed，只用于覆盖 disorder 路径。

## 3. Negative control

负控制在 sample evaluation graph 中预先注入一个 duplicate directed edge；state trajectory 仍由无缺陷 graph
生成，从而将 eligibility rejection 与 trajectory instability 分离。该控制必须 topology FAIL、reason codes 包含
`REJECT_TOPOLOGY`，并保持在审计数据中；它不是可训练失败样本。

## 4. Reference exclusion

全部 case 的 `reference_class` 均为 `R2_semidiscrete_qualified`。没有 R1、R3 或 RX；R1 仍需未来单独通过
WCSPH model-form alignment，R3 independent shear/acoustic 未被读取、生成或吸收。
