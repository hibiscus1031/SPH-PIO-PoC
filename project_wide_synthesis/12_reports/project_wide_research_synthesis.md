# SPH-PIO-PoC 全项目研究综合

**工作流：Cross-Stage Synthesis S1**  
**性质：只读、非计算性证据审计**  
**扫描截止：2026-08-05**

## 执行摘要

[PROJECT_EVIDENCE] 项目形成了从环境、SPH V&V、reference/target/data、保守架构、动态实现到多步梯度和拓扑事件的完整证据链。它没有形成动态训练或rollout成功证据。最稳健的现时发表主线是verification-first方法与负结果；Stage04以后再按决策树选择合并或拆分。

## 1. 项目起源与核心科学问题

[PROJECT_EVIDENCE] 项目起点是把SPH物理求解与可学习粒子相互作用/动态历史结合，但很快把核心问题改写为：在任何训练与性能主张之前，reference、离散、结构、数据、梯度和拓扑证据是否分别合格。

## 2. 原始SPH–Transformer设想

[PROJECT_EVIDENCE] 原设想包含静态pair correction和动态Transformer历史closure。[INFERENCE] 项目后续最重要的修正，是不再把架构存在等同于可学习、可微、可rollout或优于基线。

## 3. V&V方法论修正

[PROJECT_EVIDENCE] 项目建立L0–L10证据层、预注册硬门、失败保留、sealed test、hash freeze与组成分量/总体状态分层。

## 4. Stage00环境资格

[PROJECT_EVIDENCE] CPU/MPS请求操作通过；MPS邻域为CPU桥接的hybrid路径；full diffSPH execution在Stage00仍不可判断。

## 5. Stage01数值验证完整过程

[PROJECT_EVIDENCE] 时间线覆盖V0执行、V1算子、资源诊断、V2重资格、模型形式归因、WCSPH MMS、plateau-aware重资格与独立shear/acoustic验证。最终Stage01仍为V2_QUALIFICATION_FAIL。

## 6. Stage01全部失败与修复

[PROJECT_EVIDENCE] V1实现/结构缺陷由Stage01C修复；资源增长由D-R至D-P形成有界GC政策；TGV模型形式错配推动MMS；严格收敛门推动plateau-aware协议；shear失败被限定为finite-resolution dominant。所有旧FAIL保持。

## 7. Stage01最终边界

[PROJECT_EVIDENCE] acoustic component PASS与MMS requalification PASS不能覆盖独立shear门；Stage01 V2未恢复，viscosity operator-form failure未确认。

## 8. Stage02 PIO理论

[PROJECT_EVIDENCE] Stage02A冻结增量pair-force、reference hierarchy、守恒/对称与标签资格合同；理论完整不等于数据或模型性能。

## 9. target/reference/dataset路线

[PROJECT_EVIDENCE] D–I逐步分离temporal/spatial/reference/quadrature与conservation；J暴露单lineage泄漏；J-W最终形成20-record、4-lineage、10/5/5 split的blind static dataset。

## 10. Stage02 static training及失败

[PROJECT_EVIDENCE] v0.1为STATIC_PAIR_FORCE_FITTING_NOT_QUALIFIED，v0.2为STATIC_PAIR_FORCE_FITTING_V02_NOT_QUALIFIED。K1/K2 validation/test transfer与守恒局部通过，但train-fit硬门不满足；static route终止。

## 11. Stage02主要创新与边界

[PROJECT_EVIDENCE] 贡献在reference/target资格链、pair antisymmetry、lineage split、regularity前瞻证伪、结构正确性与learnability分离、conditioning归因。边界是没有rollout/solver consequence。

## 12. Stage03动态新假设

[PROJECT_EVIDENCE] D0–D3引入因果历史、动态图和zero-correction合同；短历史改善closure仍未测试。

## 13. dynamic reference hierarchy

[PROJECT_EVIDENCE] D-R1/D-R2/D-R3在各自范围资格化；acoustic仅linear-regime conditional，periodic vortex不是exact source-free，D-R4 physical validation不可用。

## 14. D0–D3实现

[PROJECT_EVIDENCE] Stage03C验证独立RK2、D0–D3接口、start/midpoint graph rebuild、accepted-only history commit、checkpoint与one-step autograd。

## 15. zero correction与守恒

[PROJECT_EVIDENCE] zero correction 288/288 bitwise；pair-force结构和stage conservation在冻结门内通过。不得外推到训练后性能。

## 16. multistep AD/FD

[PROJECT_EVIDENCE] 360 probes中216 stable、144失败；history 0/6；总体NOT_QUALIFIED。

## 17. topology event

[PROJECT_EVIDENCE] cutoff birth/death、6/6 deterministic replay、12/12 fixed-side gradient通过；这是QUALIFIED_COMPONENT，不是可微neighbor search总体声明。

## 18. Stage03失败归因

[PROJECT_EVIDENCE] reverse/JVP、extended FD、horizon与backend联合诊断支持mixed/unresolved；19项仍未解析，history influence强衰减。

## 19. Stage03暂停原因

[PROJECT_EVIDENCE] Stage03E authorization=false；多步梯度硬门失败，训练、rollout、性能均未执行，因此路线PAUSED而非训练失败。

## 20. 项目所有创新登记

[PROJECT_EVIDENCE] 20项内部贡献见innovation register。[LITERATURE_VERIFICATION_REQUIRED] 未在P2直接覆盖者统一标为POTENTIAL_NOVELTY_REQUIRES_LITERATURE_VERIFICATION。

## 21. 项目所有未解决问题

[PROJECT_EVIDENCE] 包括Stage01支持尺度独立性、static learnability的一般性、history attenuation机制、19项gradient归因、D-R4、动态训练/rollout/refinement/cost。

## 22. 可发表证据

[PUBLICATION_RECOMMENDATION] 主文适合资格链、关键失败、reference角色、zero-correction、结构守恒、360-probe总体结果、topology分量与claim boundary。

## 23. 只能放补充材料的证据

[PUBLICATION_RECOMMENDATION] 全量seed/checkpoint/hash、完整probe矩阵、每case reference/QC、资源重复与全部状态账本放补充材料，并在正文保留汇总与失败可见性。

## 24. 只能内部保存的证据

[PUBLICATION_RECOMMENDATION] 临时launch日志、私有验证访问控制、冗长debug traces和不进入资格的内部seals只保留审计；不得用作主张。

## 25. 单篇整合方案

[PUBLICATION_RECOMMENDATION] 仅Scenario5优先评估Option A；需要Stage04完整强证据和可控篇幅。

## 26. 两篇拆分方案

[PUBLICATION_RECOMMENDATION] 默认以Paper1承载Stage00–03资格方法，Paper2仅承载Stage04新训练/性能；执行overlap matrix与anti-salami规则。

## 27. Stage04后决策树

[PROJECT_EVIDENCE] 六场景以task-aligned gradient、training、rollout、validation/refinement和一般性逐级分叉；Stage04 delta不改写历史。

## 28. 最终研究边界

[PROJECT_EVIDENCE] 已支持实现、结构、zero-correction、reference与topology组成分量；不支持Stage01 V2恢复、static fit资格、多步梯度资格、dynamic training、rollout、solver improvement、Transformer superiority或cost utility。

## 29. artifact/hash index

[PROJECT_EVIDENCE] 冻结输入4889项、788536770 bytes；Git HEAD `ff86f5e0b99966ad6fa5896fe3d9a0c3f001cd57`。完整路径/哈希/大小/mtime/角色/manifest membership见`00_freeze/project_wide_input_freeze_manifest.json`与`01_artifact_inventory/complete_artifact_inventory.json`。

## 附录A：全阶段状态摘要

| 阶段 | exact status | 边界 |
|---|---|---|
| Stage 00 | CONDITIONAL | 环境预检不是求解器验证 |
| Stage 01 | CONDITIONAL PASS (V0 only) | 只支持对应冻结范围 |
| Stage 01B | V1_FAIL | 只支持对应冻结范围 |
| Stage 01C | C1_PASS_C2_PASS_C3_PASS_C4_PASS | 只支持对应冻结范围 |
| Stage 01D | V2_FAIL | 只支持对应冻结范围 |
| Stage 01D-R | RESOURCE_FAIL_LINEAR_GROWTH | 只支持对应冻结范围 |
| Stage 01D-R2 | ATTRIBUTION_UNRESOLVED | 只支持对应冻结范围 |
| Stage 01D-R3 | R3_CONFIRMATION_UNRESOLVED | 只支持对应冻结范围 |
| Stage 01D-R4 | R4_RETENTION_REDETECTED | 只支持对应冻结范围 |
| Stage 01D-R5 | R5_BOUNDED_GC_DELAY_CONFIRMED | 只支持对应冻结范围 |
| Stage 01D-P | POLICY_PASS_ISOLATED_DEFAULT_GC | 只支持对应冻结范围 |
| Stage 01D2 | STAGE01D2_V2_REQUALIFICATION_FAIL | 只支持对应冻结范围 |
| Stage 01E | E_MODEL_FORM_ALIGNMENT_DOMINANT | 只支持对应冻结范围 |
| Stage 01F | MMS_SPECIFICATION_PASS | 只支持对应冻结范围 |
| Stage 01F2 | MMS_IMPLEMENTATION_VERIFIED_PASS | 只支持对应冻结范围 |
| Stage 01F3 | MMS_CONVERGENCE_VERIFICATION_FAIL | 只支持对应冻结范围 |
| Stage 01F3-R | SEMIDISCRETE_REFERENCE_QUALIFIED_DENSE_EQUIVALENT | 只支持对应冻结范围 |
| Stage 01F3B | MMS_CONVERGENCE_VERIFICATION_FAIL | 只支持对应冻结范围 |
| Stage 01F3C | CT2_MIXED_OR_UNRESOLVED | 只支持对应冻结范围 |
| Stage 01F4 | PLATEAU_AWARE_PROTOCOL_APPROVED | 只支持对应冻结范围 |
| Stage 01F5 | PLATEAU_AWARE_REQUALIFICATION_DESIGN_APPROVED | 只支持对应冻结范围 |
| Stage 01F5-P | EXECUTION_MANIFEST_INCOMPLETE | 只支持对应冻结范围 |
| Stage 01F5-Q | FORMAL_SPACE_EXECUTION_BUNDLE_READY | 只支持对应冻结范围 |
| Stage 01F5B | PLATEAU_AWARE_MMS_REQUALIFICATION_PASS | 只支持对应冻结范围 |
| Stage 01G design | INDEPENDENT_VALIDATION_AND_V2_DESIGN_APPROVED | 只支持对应冻结范围 |
| Stage 01G-P | INDEPENDENT_VALIDATION_EXECUTION_READY | 只支持对应冻结范围 |
| Stage 01G-E | INDEPENDENT_VALIDATION_EVALUATOR_READY | 只支持对应冻结范围 |
| Stage 01G preflight V2 | INDEPENDENT_VALIDATION_EXECUTION_AUTHORIZED | 只支持对应冻结范围 |
| Stage 01G-R | EXECUTION_INFRA_READY_FOR_BENCHMARK | 只支持对应冻结范围 |
| Stage 01G execution | V2_QUALIFICATION_FAIL | 只支持对应冻结范围 |
| Stage 01H | VISCOSITY_DIAGNOSIS_COMPLETE | 只支持对应冻结范围 |
| Stage 02A | PIO_THEORY_QUALIFICATION_COMPLETE | 数学合同不等于模型有效性或性能。 |
| Stage 02B | DATASET_QUALIFICATION_COMPLETE | 协议 PASS 不是数据资格 PASS。 |
| Stage 02C | DATASET_GENERATION_AUDIT_COMPLETE | R2 记录默认仅为诊断，不是训练标签。 |
| Stage 02D | TARGET_ATTRIBUTION_QUALIFICATION_COMPLETE | 完成归因程序不等于目标已归因。 |
| Stage 02E | TARGET_CONSTRUCTION_COMPLETE | 非零 target 不自动是空间离散 target。 |
| Stage 02F | SPATIAL_TARGET_QUALIFICATION_COMPLETE | 程序完成不代表六分量 attribution PASS。 |
| Stage 02G | SPATIAL_ATTRIBUTION_CLOSURE_COMPLETE | 诊断闭包不升级历史 candidate。 |
| Stage 02H | REFERENCE_FIDELITY_QUALIFICATION_COMPLETE | reference PASS 仅限冻结空间算子与 case scope。 |
| Stage 02I | QUALIFIED_SPATIAL_TARGET_POOL_NOT_READY | 目标归因 PASS 不等于 pair-force scope 全部可用。 |
| Stage 02I-R | CONSERVATION_COMPATIBILITY_RESOLVED_PAIR_ONLY | scope resolution 不覆盖 Stage 02I NOT READY。 |
| Stage 02J | CONTROLLED_REGULAR_DATASET_NOT_READY | 受控 corpus 不是 train-ready dataset。 |
| Stage 02J-R | MULTIFAMILY_CONTROLLED_DATASET_NOT_READY | 未物化候选不能计为数据记录。 |
| Stage 02J-S | VERSIONED_MULTIFAMILY_DATASET_NOT_READY | 开发集规律不能替代 blind qualification。 |
| Stage 02J-T | REGULARITY_GATE_V03_NOT_QUALIFIED | 局部 PASS 不生成最终 v0.3 contract。 |
| Stage 02J-V | REGULARITY_HARD_GATE_ROUTE_TERMINATED | route terminated 不等于数据或架构失败。 |
| Stage 02J-W | BLIND_MULTIFAMILY_DATASET_READY | READY 不覆盖 J/J-R/J-S/J-T 的历史失败。 |
| Stage 02K | PAIR_FORCE_PIO_ARCHITECTURE_QUALIFIED | K0 diagnostic；attention necessity 未建立。 |
| Stage 02L | STATIC_FITTING_PROTOCOL_READY | READY 不是拟合成功。 |
| Stage 02M | STATIC_PAIR_FORCE_FITTING_NOT_QUALIFIED | validation/test局部结果不覆盖 train-fit failure。 |
| Stage 02M-R | STATIC_FITTING_FAILURE_ATTRIBUTED_OPTIMIZATION_CONDITIONING | 不覆盖 M 的 NOT QUALIFIED。 |
| Stage 02M-P | STATIC_FITTING_PROTOCOL_V02_READY | conditioning readiness 不是 learnability evidence。 |
| Stage 02M-Q | STATIC_PAIR_FORCE_FITTING_V02_NOT_QUALIFIED | 静态失败不等于 rollout failure；rollout从未执行。 |
| Stage 03A | DYNAMIC_HYBRID_SOLVER_SPECIFICATION_COMPLETE | 规格完整不等于实现、可训练性或性能成立。 |
| Stage 03B | DYNAMIC_REFERENCE_TRAJECTORY_QUALIFICATION_COMPLETE | 参考资格化不等于模型、数据集或动态性能资格化。 |
| Stage 03C | DYNAMIC_RK2_HYBRID_IMPLEMENTATION_VERIFIED | implementation verified 与 one-step plumbing verified 不证明完整多步梯度资格。 |
| Stage 03D | DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED | 总体 NOT_QUALIFIED；topology component PASS 不得写成 Stage 03D 总体 PASS。 |
| Stage 03D-R | DYNAMIC_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED | D-R 是归因诊断，不覆盖、不修复 Stage 03D 的 NOT_QUALIFIED。 |
| Stage 03D-S | STAGE03_ROUTE_PAUSED_GRADIENT_BOUNDARY_COMPLETE | 闭环报告不修复Stage03D |
| Publication P1 | PUBLICATION_EVIDENCE_LOCK_AND_DRAFT_V01_COMPLETE | 草稿不是发表接受 |
| Publication P2 | PUBLICATION_LITERATURE_VERIFICATION_AND_POSITIONING_COMPLETE | 不将文献空缺写成绝对首次 |

## 附录B：核心失败摘要

| ID | 阶段 | 状态 | 教训 |
|---|---|---|---|
| F-A01 | Stage 00/01G-R | CONDITIONAL / EXECUTION_INFRA_READY_FOR_BENCHMARK | 环境PASS必须带边界。 |
| F-B01 | Stage 01B | V1_FAIL | 最小复现先于模型归因。 |
| F-C01 | Stage 01B | V1_FAIL | 硬保证必须编码进作用形式。 |
| F-D01 | Stage 01D–D-P | V2_FAIL → POLICY_PASS_ISOLATED_DEFAULT_GC | 资源门与科学门分离。 |
| F-E01 | Stage 01E | E_MODEL_FORM_ALIGNMENT_DOMINANT | benchmark知名度不能替代方程一致性。 |
| F-F01 | Stage 01F3 | MMS_CONVERGENCE_VERIFICATION_FAIL | 先资格化reference角色。 |
| F-G01 | Stage 01D2/01F3B/01G | V2_QUALIFICATION_FAIL | 不以单个component PASS恢复总体V2。 |
| F-H01 | Stage 02D–I | QUALIFIED_SPATIAL_TARGET_POOL_NOT_READY | target非零不等于可训练。 |
| F-I01 | Stage 02J | CONTROLLED_REGULAR_DATASET_NOT_READY | 家族血缘先于随机切分。 |
| F-J01 | Stage 02J-S/T/V | REGULARITY_HARD_GATE_ROUTE_TERMINATED | 失败后不校阈值。 |
| F-K01 | Stage 02K | PAIR_FORCE_PIO_ARCHITECTURE_QUALIFIED | 合格组件不得提升为性能PASS。 |
| F-L01 | Stage 02M-R | STATIC_FITTING_FAILURE_ATTRIBUTED_OPTIMIZATION_CONDITIONING | 归因诊断不等于训练资格。 |
| F-M01 | Stage 02M/M-Q | STATIC_PAIR_FORCE_FITTING_V02_NOT_QUALIFIED | transfer PASS不能覆盖train FAIL。 |
| F-N01 | Stage 03C | DYNAMIC_RK2_HYBRID_IMPLEMENTATION_VERIFIED | 实现验证不是performance。 |
| F-O01 | Stage 03D/03D-R | DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED | 多epsilon稳定窗比单epsilon更严格。 |
| F-P01 | Stage 03D | TOPOLOGY_EVENT_COMPONENT_QUALIFIED | 分量PASS与总体NOT_QUALIFIED并存。 |
| F-Q01 | Stage 01F5-P/P1/P2 | EXECUTION_MANIFEST_INCOMPLETE → repaired | 缺证据必须是EVIDENCE_INCOMPLETE。 |
| F-R01 | Stage 02/03 | NOT_AUTHORIZED / NOT_EXECUTED | 未执行必须显式可见。 |
