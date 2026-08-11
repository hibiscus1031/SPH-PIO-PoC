# Stage 02M-S — Evidence matrix

| ID | Class | Evidence level | Claim | Limitation |
|---|---|---|---|---|
| A1 | Numerics/reference | `qualified_with_stage01_failure_boundary` | MMS 与半离散时间 reference 验证链已建立。 | 不覆盖独立 shear V2 failure。 |
| A2 | Numerics/reference | `confirmatory_scope_limited` | Fourier 与 analytic reference 在冻结 periodic-vortex scope 内独立一致。 | 仅限冻结空间算子、周期涡旋与 case matrix。 |
| A3 | Numerics/reference | `qualified_candidate_level` | 七个 spatial targets 完成 six-component attribution。 | 其中2个 jitter 不满足 pair-force global residual。 |
| A4 | Numerics/reference | `confirmatory_dataset_scope` | resolution consistency 在最终 blind families 的冻结路径通过。 | 无连续收敛阶或任意高分辨率 truth 结论。 |
| A5 | Numerics/reference | `confirmatory_dataset_scope` | support consistency 在最终 blind families 通过。 | 仅覆盖预注册 H/dx 组合。 |
| A6 | Numerics/reference | `audited` | reference uncertainty、roundoff 与 deterministic evidence 已逐阶段保留。 | 没有单一 universal uncertainty/GCI。 |
| B1 | Dataset | `confirmatory` | 四个 blind families 按冻结 seed/formula 单次生成。 | 仅20个完整 graphs。 |
| B2 | Dataset | `confirmatory` | family lineage 独立且 leakage graph 为四个 components。 | 共同代码/EOS 是 infrastructure，不是样本独立性。 |
| B3 | Dataset | `confirmatory` | prefrozen train/validation/test=10/5/5 split 无跨 split lineage。 | 每个 validation/test 仅一个 family。 |
| B4 | Dataset | `confirmatory` | 输入 normalization 仅由10个 train graphs 拟合。 | 监督尺度 v0.2 是另一个 train-only统计。 |
| B5 | Dataset | `confirmatory_contract_specific` | 20/20 records 在 Stage 02J-W eligibility contract 下 PASS。 | regularity effect 明确为 none/diagnostic。 |
| C1 | Architecture | `confirmatory_structural` | K1/K2 pair-force construction 硬编码 pair antisymmetry 与线性动量守恒。 | 不保证静态可学习性或动态稳定性。 |
| C2 | Architecture | `confirmatory_structural` | K1/K2 permutation/edge reorder、translation/Galilean、O(2)、periodicity gates PASS。 | 只在冻结 metamorphic matrix 与 float64 tolerance 下。 |
| C3 | Architecture | `confirmatory_structural` | K1/K2 differentiability 与 edge-local O(E d) resource scaling PASS。 | 未测 solver-wide scaling。 |
| C4 | Architecture | `confirmatory_negative_control` | directed-softmax negative control 暴露非互易 attention 的守恒失败。 | 并不证明 reciprocal attention 优于所有非-attention 模型。 |
| D1 | Learning | `confirmatory_negative_result` | v0.1 九运行静态拟合未满足冻结资格门。 | 仅静态同任务 protocol v0.1。 |
| D2 | Learning | `diagnostic_attribution` | v0.1 failure 的主要可审计贡献被归因为 optimization conditioning。 | post-hoc attribution；不证明修复充分。 |
| D3 | Learning | `descriptive_confirmatory` | v0.2 改善 conditioning，并使 K1/K2 validation/test transfer gates 3/3 PASS。 | train-fit B gate仍失败；新旧 families 非 paired benchmark。 |
| D4 | Learning | `confirmatory_negative_result` | v0.2 K1 train gate 0/3，K2 train gate 1/3，均未达到2/3。 | 只支持冻结静态协议的失败。 |
| D5 | Learning | `confirmatory_provenance` | v0.2 test release合规且9个selected checkpoints各评一次。 | test通过不能覆盖 train-fit failure。 |
| D6 | Learning | `terminal_decision` | 静态 PIO learning route 已终止。 | 终止仅针对当前 static delta_a learning hypothesis 与两份协议。 |

Confirmatory, diagnostic and negative evidence remain separately labeled. No dynamic solver evidence exists.
