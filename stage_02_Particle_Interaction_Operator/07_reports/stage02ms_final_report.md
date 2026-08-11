# Stage 02M-S — Static learning route closure final report

## 1. Stage 02M-Q failure preservation

Stage 02M-Q 的唯一训练判定保持为 `STATIC_PAIR_FORCE_FITTING_V02_NOT_QUALIFIED`。v0.2 的 K1 train-fit gate 为 0/3，K2 为 1/3；validation/test 的局部通过、conditioning 改善或单个 K2 seed 均不覆盖冻结的 2-of-3 train-fit 规则。所有历史状态均记录为 `superseded=false`。

## 2. Static learning route termination

两次预注册静态拟合协议均已完成且未资格化；v0.2 是 optimization-conditioning 假设下唯一允许的重试。因此 `static_pio_learning_route_terminated=true`，`training_protocol_v03_permitted=false`，`Stage02N_authorized=false`。未来假设只能建立全新 Stage 03。

## 3. Complete Stage 02 status ledger

机器账本覆盖 Stage 02A、02B、02C、02D、02E、02F、02G、02H、02I、02I-R、02J、02J-R、02J-S、02J-T、02J-V、02J-W、02K、02L、02M、02M-R、02M-P 和 02M-Q，共 22 个唯一状态。每项均包含 purpose、input freeze、execution/training/optimizer counts、principal evidence/blocker、downstream authorization、historical hash 与解释边界。机器文件：`08_route_closure/status_ledger/stage02_complete_status_ledger.json`。

## 4. Verified evidence

- Stage 01 的可审计 baseline 与 `V2_QUALIFICATION_FAIL` 被作为不变外部边界。
- 在冻结 periodic-vortex scope 内，Fourier 与 analytic reference 独立一致。
- 七个空间 target 完成归因；五个 regular cases 进入 pair-only scope，两个 jitter cases 保持 node-residual-only。
- 最终 blind dataset 为 20 graphs、4 个 lineage-disconnected family components、10/5/5 split、train-only normalization。
- K1/K2 在 pair antisymmetry、线性动量、periodicity、permutation、translation/Galilean、O(2)、differentiability 和 edge-local resource scaling 合同下 PASS。
- v0.1/v0.2 的运行、checkpoint selection、sealed test、postfit conservation/symmetry 与资源证据均保持完整 provenance。

## 5. Negative evidence

- Stage 01 V2 qualification failure 未被隐藏或重写。
- Regularity-hard-gate v0.1–v0.4 路线以 false positive、cross-mode magnitude 与 invariance failures 终止。
- v0.1 九运行静态拟合未满足冻结 success gates。
- v0.2 九运行重试仍未满足 train-fit qualification；K1 0/3，K2 1/3。
- Rollout 与 solver-in-the-loop 是 `NOT AUTHORIZED / NOT EXECUTED`，不是 dynamic failure。

## 6. Supported claims

允许主张：构建了冻结 scope 内的 blind multifamily reference-qualified dataset；互易 pair-force architecture 强制离散线性动量守恒；K1/K2 满足冻结 equivariance/periodicity contracts；两次预注册静态拟合均未满足 train-fit qualification；architecture correctness 不蕴含 static learnability。

## 7. Unsupported claims

禁止主张：learned correction improves SPH、learned model restores V2、attention is superior、Transformer is necessary、rollout is stable、solver is accelerated、arbitrary-flow generalization、viscosity operator is confirmed、high-resolution SPH is truth。逐项允许/禁止措辞见 `08_route_closure/claim_boundary/stage02_claim_boundary.json` 与 `07_reports/stage02ms_claim_boundary.md`。

## 8. Paper-direction comparison

| Direction | Readiness | Strongest contribution | Fatal weakness | Current CMAME defensible |
|---|---|---|---|---|
| Paper A: Transformer/Attention-corrected SPH solver | `NOT_READY` | qualified conservative architecture contract | no qualified static model and no solver-performance evidence | no |
| Paper B: V&V-first qualification framework | `DRAFTABLE_AFTER_SYNTHESIS` | auditable reference→target→dataset→architecture→learning decision chain | single mechanics scope and no solver consequence | no |
| Paper C: architecture validity versus static learnability negative result | `DRAFTABLE` | two frozen protocols falsify static qualification within scope | one dataset scope cannot establish a general law | no |

## 9. Recommended manuscript framing

推荐 Paper B + Paper C 的 methodology/negative-results hybrid。工作标题为：*Verification- and qualification-first development of conservative learned correction operators for SPH: from reference construction to falsified static fitting*。主线不得以“Transformer successfully improves SPH”为前提；K2 仅作为 qualified architecture arm，而非已证明优越的 solver。

## 10. CMAME readiness assessment

当前结论为 `NOT_YET_DEFENSIBLE`。CMAME 的 scope 与方法学取向相容，但现有证据尚未展示 qualified computational method 对 solver outcome 的影响，也缺少跨机制外部一般性。现阶段可以形成边界明确的完整期刊稿，但更适合先按 methodology/negative-results paper 定位，不应把 CMAME-ready 当成事实。

## 11. Missing evidence

进入更强 CMAME 主张最关键的三项新证据是：

1. 跨 mechanics regime / cross-flow replication，并重新完成独立 reference/V&V；
2. 非神经或低维 identifiable conservative baseline，建立机制与可识别性对照；
3. 由全新 Stage 03 前瞻授权的 one-step/trajectory/solver-consequence evidence，而不是复用已消费的 Stage 02 test。

Main text 可承载 qualification pipeline、reference/target hierarchy、blind dataset structure、architecture contracts、完整 static gate outcomes 与 route termination。逐文件 hashes、全量 seed/checkpoint 表和 audit registries 放 supplement；失败候选逐行日志、资源探针与内部 seal receipts 仅保留审计。

## 12. Stage 02 Research Record path

中文综合记录位于 `stage_02_Particle_Interaction_Operator/documents/Stage_02_Research_Record.docx`。最终渲染为 24 页 Letter portrait，含封面、静态目录、摘要、16 个必需章节、7 个公式、17 个数据表、3 个记录内流程/状态图与五个附录。24 页已逐页检查；a11y high/medium/low 均为 0，无空白页、溢出、缺字或失效外部链接。

## 13. Figure/table package

已规划 8 幅图：qualification pipeline、reference/target hierarchy、decision/failure tree、dataset family/split/leakage、K0/K1/K2 conservation contract、v0.1/v0.2 trajectories、seed-level frozen gate outcomes、claim boundary。已规划 6 张表：status ledger、reference qualification、dataset inventory、architecture hard gates、v0.1/v0.2 fitting、final evidence/claim matrix。图表完整性规则明确禁止删除失败 seed、只展示最佳 seed或将粒子数作为统计样本数。

## 14. Future Stage 03 options

- Branch 1 / new Stage 03A：停止学习修正，论文聚焦 V&V/qualification framework。
- Branch 2 / new Stage 03B：学习低维、可唯一识别的物理系数或 closure。
- Branch 3 / new Stage 03C：建立真实多状态 trajectory dataset，并重新执行独立 reference/V&V。
- Branch 4 / new Stage 03D：解析或回归型 non-neural conservative correction。

这些分支仅完成 decision design，本阶段未执行。

## 15. No new training

Stage 02M-S 新训练运行数为 0，optimizer steps 为 0；未新增 model、feature、loss、optimizer、seed 或 v0.3 protocol。

## 16. No new test

Stage 02M-S 新 test evaluations 为 0；未重新读取或评价 sealed test，未重新选择 checkpoint。

## 17. No rollout

Rollout 数为 0，solver-in-the-loop executions 为 0。其状态只能写为 `NOT AUTHORIZED / NOT EXECUTED`。

## 18. Historical hashes unchanged

Freeze manifest 记录 1,788 个 Stage 01/Stage 02 历史文件及 9 个 selected checkpoints。闭包时逐文件重新计算 SHA-256，要求并确认 1,788/1,788 unchanged；Stage 02A–02M-Q 与 Stage 01 既有文件均未修改。复核结果写入 `08_route_closure/manifests/stage02ms_closure_manifest.json`。

## Final state

`STAGE02_ROUTE_CLOSED_PUBLICATION_BOUNDARY_COMPLETE`
