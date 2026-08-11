# 完整失败登记与十项深度分析

[PROJECT_EVIDENCE] 本登记保留基础设施失败、科学失败、NOT_QUALIFIED 与 NOT_EXECUTED 的差异。

| ID | 类别 | 阶段 | exact status | 直接原因 | 后续影响 |
|---|---|---|---|---|---|
| F-A01 | A 环境与依赖问题 | Stage 00/01G-R | CONDITIONAL / EXECUTION_INFRA_READY_FOR_BENCHMARK | 平台/依赖边界而非科学模型失败。 | 要求CPU canonical与基础设施/科学失败分离。 |
| F-B01 | B 数值实现错误 | Stage 01B | V1_FAIL | 上游接口和执行栈缺陷。 | 推动Stage01C项目侧唯一pair几何/native AD。 |
| F-C01 | C 守恒/对称结构问题 | Stage 01B | V1_FAIL | 离散作用结构不是事后数值噪声。 | 推动对称非负pair作用及K1/K2硬结构。 |
| F-D01 | D 资源和内存问题 | Stage 01D–D-P | V2_FAIL → POLICY_PASS_ISOLATED_DEFAULT_GC | retired对象受GC延迟、topology与fixture语义共同影响。 | 旧V2失败保留，但建立隔离子进程资源政策。 |
| F-E01 | E 模型形式不一致 | Stage 01E | E_MODEL_FORM_ALIGNMENT_DOMINANT | 不可压TGV压力与WCSPH EOS初始化不一致。 | 推动WCSPH-compatible MMS。 |
| F-F01 | F reference specification问题 | Stage 01F3 | MMS_CONVERGENCE_VERIFICATION_FAIL | continuum truth、semidiscrete time truth与spatial truth角色混淆。 | Stage01F3-R建立dense-equivalent same-semidiscrete DOP853。 |
| F-G01 | G solution verification问题 | Stage 01D2/01F3B/01G | V2_QUALIFICATION_FAIL | 有限分辨率、支持尺度共变与门设计敏感性。 | 形成plateau-aware protocol与finite-resolution边界。 |
| F-H01 | H target attribution问题 | Stage 02D–I | QUALIFIED_SPATIAL_TARGET_POOL_NOT_READY | 高分辨率SPH并非自动truth。 | 推动R2S、Fourier/analytic与pair-only scope。 |
| F-I01 | I dataset lineage/leakage问题 | Stage 02J | CONTROLLED_REGULAR_DATASET_NOT_READY | 粒子/边/patch随机切分会泄漏。 | Stage02J-W形成4 lineage、10/5/5 blind split。 |
| F-J01 | J regularity contract问题 | Stage 02J-S/T/V | REGULARITY_HARD_GATE_ROUTE_TERMINATED | regularity统计量不足以作为必要且稳定的资格硬门。 | hard-gate路线终止；regularity降为diagnostic。 |
| F-K01 | K architecture representability问题 | Stage 02K | PAIR_FORCE_PIO_ARCHITECTURE_QUALIFIED | 此类别未观察架构硬失败，但representability不等于learnability。 | 允许进入协议，但不宣称Transformer优越。 |
| F-L01 | L optimization conditioning问题 | Stage 02M-R | STATIC_FITTING_FAILURE_ATTRIBUTED_OPTIMIZATION_CONDITIONING | 优化conditioning与尺度影响训练门。 | 促成v0.2监督尺度与新blind families。 |
| F-M01 | M static learnability问题 | Stage 02M/M-Q | STATIC_PAIR_FORCE_FITTING_V02_NOT_QUALIFIED | train-fit硬门未满足，即使validation/test transfer与守恒通过。 | static route终止；Stage02N未授权。 |
| F-N01 | N dynamic implementation问题 | Stage 03C | DYNAMIC_RK2_HYBRID_IMPLEMENTATION_VERIFIED | 未观察实现硬失败；多步问题属于后续资格层。 | 授权Stage03D而不授权训练。 |
| F-O01 | O multistep differentiability问题 | Stage 03D/03D-R | DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED | 固定拓扑AD/FD稳定窗及history门失败。 | Stage03E未授权；路线暂停。 |
| F-P01 | P topology-event问题 | Stage 03D | TOPOLOGY_EVENT_COMPONENT_QUALIFIED | 拓扑分量是piecewise-smooth边界，不代表可微neighbor search。 | 保留为QUALIFIED_COMPONENT。 |
| F-Q01 | Q evidence/provenance问题 | Stage 01F5-P/P1/P2 | EXECUTION_MANIFEST_INCOMPLETE → repaired | 复杂工作流中合同完整性本身是资格前置。 | 引入freeze、sealed test、delta manifest与claim audit。 |
| F-R01 | R 未执行或未授权事项 | Stage 02/03 | NOT_AUTHORIZED / NOT_EXECUTED | 上游static fit和multistep gradient未资格。 | 不得产生性能或优越性主张。 |

## 1. Stage 01B V1 failure

[PROJECT_EVIDENCE] kernel consistency 与 manufactured Laplacian 在10% jitter高分辨率反弹；variable-density viscosity与mixed-sign pressure不满足严格pair内部力结构；上游generic Laplacian三步backward在`h_i=None`失败。因此`V1_FAIL`是已执行硬门失败。Stage01C用唯一pair几何、10-seed ensemble、对称pair作用和native PyTorch AD修复C1–C4，但没有回写Stage01B。

## 2. Stage 01D资源增长

[PROJECT_EVIDENCE] 旧N32 smoke触发RSS增长门；D-R复核仍见post-warm-up增长，D-R2/R3未唯一归因，D-R4在正确weakref语义下重新检测retention，D-R5显示GC-disabled线性而default-GC 2000步上包络有界。D-P的1600步隔离子进程canary通过。[INFERENCE] 最稳妥结论是“有界GC延迟与生命周期效应”，不是简单memory leak；旧`V2_FAIL`不变。

## 3. Stage 01D2 V2 failure

[PROJECT_EVIDENCE] 时间序列可解释，但空间误差非单调；jitter显著恶化并触发冻结资源/无序门，最终为`STAGE01D2_V2_REQUALIFICATION_FAIL`。这些门已执行，因此是FAIL；V3不能开始。

## 4. Stage 01E model-form mismatch

[PROJECT_EVIDENCE] 210个静态case闭合最大Linf为`8.357594e-14`；EOS/operator比`144.053`，EOS/viscosity比`1621.69`。不可压TGV解析压力与WCSPH EOS初值不相容，推动WCSPH-compatible MMS；该归因不恢复V2。

## 5. Stage 01F3/F3B/F3C convergence gates

[PROJECT_EVIDENCE] F3与F3B均保持`MMS_CONVERGENCE_VERIFICATION_FAIL`；F3-R只资格化same-semidiscrete dense-equivalent reference；F3C虽见近二阶时间行为，但cancellation/plateau门仍失败，状态`CT2_MIXED_OR_UNRESOLVED`。因此后续建立前瞻性plateau-aware协议，并保留旧失败。

## 6. Stage 01G V2 failure

[PROJECT_EVIDENCE] acoustic gates通过，但shear N48 decay-rate相对误差`0.0279495032685`超过`0.02`。Stage01H将其分类为`FINITE_RESOLUTION_DOMINANT`，时间步贡献极小、重复bitwise一致；由于H/dx与N共变，不能宣称viscosity operator-form failure。

## 7. Stage 02 target/reference failures

[PROJECT_EVIDENCE] Stage02D–I依次暴露temporal contamination、spatial attribution不足、quadrature/reference角色混淆与pair-only conservation scope；Stage02J-S/T/V前瞻证伪regularity hard gate。修正链是same-state target → independent Fourier/analytic reference → pair-only scope → lineage-based blind dataset；任何中间candidate都未被追认为旧PASS。

## 8. Stage 02 static fitting failure

[PROJECT_EVIDENCE] v0.1状态`STATIC_PAIR_FORCE_FITTING_NOT_QUALIFIED`；v0.2状态`STATIC_PAIR_FORCE_FITTING_V02_NOT_QUALIFIED`。v0.2 K1 train-fit通过seed数`0`，K2为`1`；validation/test各有3个seed通过且守恒保持，但冻结B门要求整体train fit，故不能把transfer PASS写成模型成功。M-R支持optimization conditioning归因，监督尺度`a_sup=0.392220124168075`后仍未资格，static route必须终止。

## 9. Stage 03D multistep gradient failure

[PROJECT_EVIDENCE] 机器清单记录`360` probes、`216` stable windows、`144` failures、history `0/6`、per-stage conservation `540/540`。D-R的reverse/JVP 60/60与extended FD不能覆盖stable-window失败；backend sensitivity、conditioning/non-smooth/structural-zero与history attenuation共同导致`DYNAMIC_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED`。

## 10. 未执行事项

[PROJECT_EVIDENCE] dynamic training、autonomous rollout、solver-in-the-loop与full performance evaluation均为`NOT_AUTHORIZED / NOT_EXECUTED`。它们不是失败，也没有可用的训练曲线、性能优势或成本结论。
