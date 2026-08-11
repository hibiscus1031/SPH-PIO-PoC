# Stage 00–03 研究工作过程与论文论述资料包

## 0. 阅读说明

【项目证据】 本资料包以 `project_wide_synthesis/00_freeze/project_wide_input_freeze_manifest.json`、完成状态为 `PROJECT_WIDE_EVIDENCE_SYNTHESIS_AND_PUBLICATION_DOSSIER_COMPLETE` 的总档案、59 条 Stage 00–03 时间线记录、机器 JSON/CSV/status、三份 Stage Research Record 为输入。冻结 Git HEAD 为 `ff86f5e0b99966ad6fa5896fe3d9a0c3f001cd57`；总档案最终 manifest 的历史复哈希门为 `PASS`。时间范围止于 Stage 03D-S，不包含任何 Stage 04 新结果。

【项目证据】 状态术语保持 PASS、FAIL、NOT_QUALIFIED、EVIDENCE_INCOMPLETE、NOT_AUTHORIZED、NOT_EXECUTED、DIAGNOSTIC、CONDITIONAL、TERMINATED、PAUSED 与 QUALIFIED_COMPONENT 的原义。局部 PASS 不覆盖总体 FAIL/NOT_QUALIFIED；未执行不写成失败。

- 【项目证据】：可直接追溯到冻结机器证据。
- 【基于证据的推断】：在不改变机器结论的前提下组织因果关系。
- 【论文建议】：面向论文结构、图表与篇幅的选择，不是新科学 verdict。
- 【需外部文献核验】：项目内证据存在，但新颖性或一般性仍需外部文献验证。

【项目证据】 DOCX 研究记录只用于叙事交叉核验；状态和数字以机器 JSON/manifest 为优先。本次核验未发现需要标记为 `EVIDENCE_CONFLICT` 的相反机器 verdict。Stage 01/02/03 DOCX 分别渲染为 14/22/19 页；部分中文字体在 LibreOffice 预览中显示替代方框，但 OOXML 文本可提取，且不影响机器证据裁决。

## 1. 项目全景概述

【基于证据的推断】 项目起点是把 SPH 的局部核支持域与注意力的邻域聚合联系起来：两者都从局部粒子/节点关系形成更新。但这种类比只提供建模启发，不能证明 Transformer 可以替代核函数、守恒离散或时间积分器。SPH 的可信度依赖方程形式、离散一致性、成对作用、邻域拓扑、积分与参考解；注意力层的可表达性也不自动给出守恒、可微、可训练或 rollout 稳定性。

【项目证据】 因而研究对象被收敛为 Particle Interaction Operator：神经模块只输出受合同约束的 pair correction，基线 SPH、状态更新与时间积分保留；零修正必须回到基线，成对反对称必须硬保证线动量守恒。研究顺序也从“先训练后比较”改为 verification-first：先证明环境与求解链可用，再验证算子与资源；随后通过 MMS 和独立物理基准限定求解器可信边界；再资格化 target/reference、数据 lineage 和架构；静态拟合不合格后才建立动态实现，并在训练前验证多步梯度与 topology。

总链条为：

`环境与求解器审计 → 算子与资源资格 → MMS 与独立验证 → target/reference 资格 → 守恒架构 → 静态训练 → 动态混合求解器 → 多步梯度边界`。

## 2. 原始假设及其修正

【项目证据】 假设演化不是结果后改写，而是由冻结失败门触发的前瞻更新。高分辨率 SPH 不能自动成为教师真值，因为同一离散族可能携带时间、空间、quadrature 与模型形式偏差；后续改为 candidate high-fidelity reference，并要求解析、Fourier、same-semidiscrete DOP853 等不同角色分别资格化。static correction 假设在 Stage 02M/M-Q 的 train-fit 门上未资格化；其后继不是宣称 correction 不可学习，而是提出 task-aligned local-causal dynamic hypothesis。短历史改善 closure、attention 优于 MLP、dynamic training 可资格化等假设仍未得到结果支持。

| ID | 原始假设 | 证据状态 | 证伪/限制 | 后继假设 |
|---|---|---|---|---|
| H01 | 高分辨率 SPH 可自动作为真值。 | FALSIFIED | Stage01与Stage02显示离散、时间、quadrature与模型形式污染必须分离。 | 候选reference必须独立资格化。 |
| H02 | WCSPH 与不可压 TGV 在当前设置中模型形式一致。 | LIMITED/FALSIFIED_IN_SCOPE | Stage01E EOS初始化残差主导，比例由机器记录给出。 | 采用WCSPH-compatible MMS与source-free独立验证。 |
| H03 | static pair-force correction 在合格架构下可学习。 | NOT_QUALIFIED | Stage02M/M-Q中K1/K2 train-fit硬门未整体通过。 | 转向局部因果动态训练假设。 |
| H04 | regularity 可作为dataset hard gate。 | FALSIFIED | v0.1–v0.4出现false positive、cross-mode与invariance失败；路线终止。 | regularity仅作diagnostic，dataset eligibility由reference/target/conservation/lineage决定。 |
| H05 | attention优于MLP。 | NOT_TESTED | K1/K2结构资格化不等于优越性；static fitting也未建立稳定优势。 | 未来只可在公平D0–D3合同和合格训练后比较。 |
| H06 | optimization conditioning主导static fitting。 | SUPPORTED_AS_DIAGNOSIS_NOT_GENERAL_LAW | Stage02M-R量化归因支持conditioning，但v0.2仍未资格。 | 需新任务对齐、尺度与blind families检验。 |
| H07 | 短时历史改善动态closure。 | NOT_TESTED/GRADIENT_ATTENUATED | Stage03D history gradient 0/6；D-R观察到history influence强衰减。 | Stage04需local-causal/task-aligned可证伪合同。 |
| H08 | 动态Transformer混合实现正确。 | QUALIFIED_COMPONENT | Stage03C D0/zero-correction/checkpoint/one-step AD通过。 | 实现正确不等于多步可微或训练有效。 |
| H09 | 多步梯度可按360-probe合同资格化。 | NOT_QUALIFIED | 216 stable、144 failure；history 0/6；归因为mixed/unresolved。 | 需新任务对齐梯度合同，不能后改epsilon门。 |
| H10 | 动态训练资格已建立。 | NOT_AUTHORIZED/NOT_EXECUTED | Stage03E=false；optimizer/training=0。 | Stage04必须独立进口新证据。 |
| H11 | Stage04 local-causal training能避开全局history梯度衰减并保持结构性质。 | NOT_TESTED | 仅为Stage04新假设，没有训练或rollout证据。 | 以task-aligned gradient→training→rollout→validation顺序检验。 |

## 3. Stage 00：计算环境与项目基线

【项目证据】 硬件身份为 Apple M2、16 GB unified memory、8-core Metal GPU；CUDA 未使用。CPU tensor、autograd、Linear、MultiheadAttention、scatter/index、cdist/topk 检查通过；MPS built/available 且同一请求集合通过。`torchCompactRadius 0.5.5` 与 `diffSPH 0.2.2` 完成安装/导入及 naive neighbor 预检，但没有在 Stage 00 运行完整 diffSPH solver。项目保留纯 PyTorch 最小 SPH 后备路径，是因为上游偏 CUDA 的说明和局部预检不能覆盖所有 MPS solver path。

【项目证据】 Stage 00 的保守建议是 N≤1,024、batch 1、32 neighbors、float32；这是唯一实测 neighborhood 规模，不是内存上限。MPS 在 1024×1024 matmul 上较快，但 N=1024 neighbor aggregate 反而慢于 CPU，因此后端选择以操作类型和可复现性而非设备标签决定。最终状态为 `CONDITIONAL`：证明“环境可运行”，不证明“数值求解可信”。

| 阶段 | 冻结最终状态 | 执行/输出 | 阻断与边界 | 机器/冻结来源 |
|---|---|---|---|---|
| Stage 00 | CONDITIONAL | CPU/MPS操作检查通过；diffSPH仅安装/导入/邻域预检。 | 完整diffSPH求解器未在该阶段运行。 | `07_reports/stage_00_summary.md` |

## 4. Stage 01：SPH 求解器 V&V 全过程

### 4.1 Stage 01 初始 TGV 运行

【项目证据】 CPU canonical 路径在 256、576、1024 粒子各执行两次；MPS 完成请求 case，但 compact neighbor search 在 CPU 与 MPS 之间桥接，故只能称 hybrid。速度与能量误差随 16×16、24×24、32×32 分辨率下降；initial-velocity-amplitude value path 在 CPU/MPS 上保留三步 autograd，并与 centered FD 一致。该结果只形成 `CONDITIONAL PASS (V0 only)`：证明执行链、窄 value-path AD 和数值趋势，不证明 kernel/Laplacian 一致性、完整 topology differentiability 或 V2 solution verification。

### 4.2 Stage 01B：第一次严格 V&V 失败

【项目证据】 V1 检查暴露四类问题：10% jitter 下 zeroth kernel moment 非单调并可随加密恶化；raw/one-sided Laplacian 在 disorder 下出现负观测阶；非对称内部力结构产生非零归一化总内力残差；pinned upstream generic Laplacian backward 在 `h_i=None` 路径失败。因为这些是 V1 hard gates，V2/TGV 继续执行被停止，最终状态 `V1_FAIL`。这一失败说明早期“能跑且误差下降”没有覆盖算子一致性、守恒结构与反向传播实现。

### 4.3 Stage 01C：算子重资格

【项目证据】 修复采取项目侧 reciprocal graph、局部 WLS/reproducing operator、显式 antisymmetric pair-force residual、viscous power 符号检查和 native AD。C1–C4 全部通过；disorder ensemble 在 N=16/24/32/48/64 上检查端点比、斜率与 N64 rebound，selected WLS 主量没有系统性最高分辨率反弹。该阶段通过的是静态 operator/code verification，不是动态 TGV、V2 或物理验证。

### 4.4 Stage 01D 系列：资源增长与 GC 归因

【项目证据】 Stage 01D 的 N32 smoke 在资源门失败，后续时间/空间/disorder/Mach 多门按合同保持 NOT_RUN。01D-R 复现 apparent linear RSS growth，但明确禁止直接命名为 memory leak；01D-R2 的 storage/edge attribution 未能唯一解释增长，edge count 的 cutoff roundoff 与对象生命周期混合；01D-R3 冻结 topology 后仍未闭合；01D-R4 修正 weakref fixture 后重新检测 retention；01D-R5 则显示 GC-disabled 长窗线性、default-GC 2,000 步出现有界上包络，支持“cyclic GC delayed retention”而非无界泄漏。

【项目证据】 Stage 01D-P 将风险转化为工程合同：trajectory-per-process、default cyclic GC、`no_grad`、parent scalar-only，3/3 1600-step canary 通过。资源政策资格化不回写旧 V2 失败。Stage 01D2 完整重资格中，20 个 AD case 与时间门通过，空间主序列/N48 非单调，6/6 jitter 虽完成轨迹但资源增量越界，10% jitter velocity error median multiplier 为 9.3377，最终 `STAGE01D2_V2_REQUALIFICATION_FAIL`，V3 未启动。

### 4.5 Stage 01E：模型形式一致性

【项目证据】 不可压 TGV 的压力/速度合同与 WCSPH EOS 初始化并不一致。210 个静态 case 与 21 条短轨迹的 residual decomposition 显示 EOS initialization L2 相对 pressure-operator 与 viscosity 项的比值约为 144 和 1,622，closure Linf 仍在约 8.36e-14。结论为 `E_MODEL_FORM_ALIGNMENT_DOMINANT`：模型形式是主要归因，但这不把 Stage 01D2 改写为 PASS，也不能以不可压解析解继续直接评价 WCSPH 全链。

### 4.6 Stage 01F 系列：WCSPH-compatible MMS

【项目证据】 Stage 01F 先建立 WCSPH-compatible manufactured solutions、EOS/continuity/momentum analytic closure 与 source injection；Stage 01F2 用 manual/autograd 双路径、source/balance、periodicity 和 dense/sparse checks 验证实现。Stage 01F3 因 reference/topology identity 与严格单调门失败；01F3-R 资格化 dense-equivalent same-semidiscrete DOP853，分离 continuum/spatial truth 与 semidiscrete temporal truth；01F3B 仍因 total exact velocity error 在空间平台附近轻微反向变化而失败，GCI 不成立；01F3C 判定 time order 接近 2，但 cancellation/plateau 使归因为 mixed/unresolved。

【项目证据】 Stage 01F4 前瞻批准 plateau-aware protocol，旧失败不改；01F5 冻结 T/P/H/S 与安全门；01F5-P 发现 N64 branch/horizon manifest 不完整，状态 `EXECUTION_MANIFEST_INCOMPLETE`；01F5-Q 只修复合同绑定；01F5B 最终 69 行矩阵的有效运行全部通过预注册 T/P/H/S 与 reference/structure/resource/determinism 门，状态 `PLATEAU_AWARE_MMS_REQUALIFICATION_PASS`。但各场量 GCI 仍未资格化，因为局部阶稳定条件不满足；MMS requalification 也不等于独立 V2 physical validation。

### 4.7 Stage 01G：独立验证设计与执行

【项目证据】 独立验证采用 source-free shear wave 与 linear-regime acoustic wave。设计、preexecution、evaluator provenance 与 execution infrastructure 分阶段资格化，保留早期 evaluator 缺失和基础设施失败。正式 12-run matrix 全部形成完整证据；acoustic gates 全 PASS；shear 的 SHEAR1/2/4–8 通过，SHEAR3 decay-rate relative error=0.0279495 失败。因此唯一总体状态为 `V2_QUALIFICATION_FAIL`，局部 acoustic PASS 不能覆盖 shear hard gate。

### 4.8 Stage 01H：黏性衰减误差诊断

【项目证据】 Stage 01H 只做冻结结果诊断：nu_eff bias 随 N 增大严格减小，N48 比 N32 的 decay/velocity error 改善，N32 dt-halving 最大相对变化仅 6.41e-8，repeat bitwise identical。结论 `FINITE_RESOLUTION_DOMINANT`，但 fixed-N H/dx sweep 缺失，resolution 与 support quadrature 不能分离；因此没有确认 viscosity operator-form failure，也不允许 V2 reconsideration。

### 4.9 Stage 01 最终结论

【项目证据】 已验证：V0 执行链、Stage 01C 静态算子、资源隔离政策、WCSPH MMS specification/implementation/plateau-aware requalification、独立 acoustic 分量。失败或未资格化：Stage 01B V1、Stage 01D/01D2 V2、Stage 01G shear hard gate；GCI 不成立。未执行：V3 和由此后的性能链。对 Stage 02 的迁移是：reference 必须资格化；模型形式必须一致；守恒应由结构硬保证；失败门必须保留。

| 阶段 | 冻结最终状态 | 执行/输出 | 阻断与边界 | 机器/冻结来源 |
|---|---|---|---|---|
| Stage 01 | CONDITIONAL PASS (V0 only) | V0工程可执行；V1部分；V2未完成；V3未开始。 | 不可作fixed-physics truth。 | `07_reports/stage_01_scope_reclassification.md` |
| Stage 01B | V1_FAIL | kernel/Laplacian/AD及结构门触发停止。 | V2/TGV未授权。 | `07_reports/stage_01b_final_vv_report.md` |
| Stage 01C | C1_PASS_C2_PASS_C3_PASS_C4_PASS | 四项静态重资格门通过。 | 不是动态V2。 | `06_experiments/stage_01c_operator_candidates/results/stage01c_gate_status.txt` |
| Stage 01D | V2_FAIL | N32 smoke资源门失败；后续多门NOT_RUN。 | 资源增长机制未明。 | `06_experiments/stage_01d_fixed_physics_tgv/results/stage01d_v2_status.txt` |
| Stage 01D-R | RESOURCE_FAIL_LINEAR_GROWTH | 资源重资格仍失败。 | 不能据此直接称memory leak。 | `06_experiments/stage_01dr_memory_diagnosis/results/stage01dr_resource_status.txt` |
| Stage 01D-R2 | ATTRIBUTION_UNRESOLVED | storage归因未唯一解析。 | cutoff topology与生命周期混杂。 | `06_experiments/stage_01dr2_storage_attribution/results/stage01dr2_attribution_status.txt` |
| Stage 01D-R3 | R3_CONFIRMATION_UNRESOLVED | 证据仍未解析。 | weakref语义待核。 | `06_experiments/stage_01dr3_topology_confirmation/results/stage01dr3_status.txt` |
| Stage 01D-R4 | R4_RETENTION_REDETECTED | retention被重新检测。 | GC时序未定位。 | `06_experiments/stage_01dr4_weakref_semantics/results/stage01dr4_status.txt` |
| Stage 01D-R5 | R5_BOUNDED_GC_DELAY_CONFIRMED | GC-disabled线性；default-GC 2000步有界。 | 不能把旧资源失败改写为假阳性。 | `06_experiments/stage_01dr5_gc_cycle_localization/results/stage01dr5_status.txt` |
| Stage 01D-P | POLICY_PASS_ISOLATED_DEFAULT_GC | 3/3 canary通过；政策资格化。 | 仅资源政策，不是V2数据。 | `06_experiments/stage_01dp_resource_policy/results/stage01dp_status.txt` |
| Stage 01D2 | STAGE01D2_V2_REQUALIFICATION_FAIL | 时间可解释，但空间非单调、jitter/资源门失败。 | 不能进入V3。 | `06_experiments/stage_01d2_v2_requalification/results/stage01d2_evaluation.json` |
| Stage 01E | E_MODEL_FORM_ALIGNMENT_DOMINANT | EOS初始化残差主导；两项渐近拟合不可识别。 | 不改变V2失败。 | `06_experiments/stage_01e_error_decomposition/results/stage01e_evaluation.json` |
| Stage 01F | MMS_SPECIFICATION_PASS | MMS规格通过。 | 规格不等于实现/收敛。 | `06_experiments/stage_01f_mms_design/results/stage01f_evaluation.json` |
| Stage 01F2 | MMS_IMPLEMENTATION_VERIFIED_PASS | 实现验证通过。 | 未建立收敛资格。 | `06_experiments/stage_01f2_mms_implementation/results/stage01f2_evaluation_v2.json` |
| Stage 01F3 | MMS_CONVERGENCE_VERIFICATION_FAIL | reference/topology identity硬门前停止或收敛门失败。 | 需reference资格化。 | `06_experiments/stage_01f3_mms_convergence/results/stage01f3_evaluation.json` |
| Stage 01F3-R | SEMIDISCRETE_REFERENCE_QUALIFIED_DENSE_EQUIVALENT | reference资格化。 | 不修复原F3失败。 | `06_experiments/stage_01f3r_reference_qualification/results/stage01f3r_evaluation.json` |
| Stage 01F3B | MMS_CONVERGENCE_VERIFICATION_FAIL | 仍为收敛资格失败；GCI不成立。 | plateau/cancellation影响门设计。 | `06_experiments/stage_01f3b_mms_convergence/results/stage01f3b_evaluation.json` |
| Stage 01F3C | CT2_MIXED_OR_UNRESOLVED | 时间阶接近2但抵消门失败，混合/未解析。 | 严格单点门不稳健。 | `06_experiments/stage_01f3c_ct2_adjudication/results/stage01f3c_evaluation.json` |
| Stage 01F4 | PLATEAU_AWARE_PROTOCOL_APPROVED | 新协议批准；旧失败保持。 | 尚未执行。 | `06_experiments/stage_01f4_protocol_adjudication/results/stage01f4_evaluation.json` |
| Stage 01F5 | PLATEAU_AWARE_REQUALIFICATION_DESIGN_APPROVED | 设计批准。 | 执行清单分支不全。 | `06_experiments/stage_01f5_requalification_design/results/stage01f5_evaluation.json` |
| Stage 01F5-P | EXECUTION_MANIFEST_INCOMPLETE | 执行清单不完整。 | 空间horizon参数未绑定。 | `06_experiments/stage_01f5p_branch_completeness/results/stage01f5p_evaluation.json` |
| Stage 01F5-Q | FORMAL_SPACE_EXECUTION_BUNDLE_READY | 正式执行bundle就绪。 | 尚未产生资格。 | `06_experiments/stage_01f5q_space_horizon_amendment/results/stage01f5q_evaluation.json` |
| Stage 01F5B | PLATEAU_AWARE_MMS_REQUALIFICATION_PASS | 一次性重资格通过；基础设施retry单独保留。 | 不等于V2 physical validation。 | `06_experiments/stage_01f5b_requalification_execution/results/stage01f5b_evaluation.json` |
| Stage 01G design | INDEPENDENT_VALIDATION_AND_V2_DESIGN_APPROVED | 设计通过但未执行。 | 需独立授权。 | `06_experiments/stage_01g_validation_design/results/stage01g_design_evaluation.json` |
| Stage 01G-P | INDEPENDENT_VALIDATION_EXECUTION_READY | preexecution audit通过。 | evaluator尚需资格化。 | `06_experiments/stage_01gp_preexecution_audit/results/stage01gp_evaluation.json` |
| Stage 01G-E | INDEPENDENT_VALIDATION_EVALUATOR_READY | evaluator就绪。 | 执行基础设施仍需授权。 | `06_experiments/stage_01ge_evaluator_qualification/results/stage01ge_evaluation.json` |
| Stage 01G preflight V2 | INDEPENDENT_VALIDATION_EXECUTION_AUTHORIZED | 执行获授权；未生成V2状态。 | 需基础设施成功。 | `06_experiments/stage_01g_execution_preflight_v2/results/stage01gv2_evaluation.json` |
| Stage 01G-R | EXECUTION_INFRA_READY_FOR_BENCHMARK | 修复后基础设施就绪。 | 科学门仍待执行。 | `06_experiments/stage_01gr_execution_infrastructure_repair/results/stage01gr_evaluation.json` |
| Stage 01G execution | V2_QUALIFICATION_FAIL | acoustic通过；shear N48门失败；V2失败。 | SHEAR3衰减误差。 | `06_experiments/stage_01g_validation_execution/results/stage01g_evaluation_reapplication_01.json` |
| Stage 01H | VISCOSITY_DIAGNOSIS_COMPLETE | 分类FINITE_RESOLUTION_DOMINANT；算子形式失败未确认。 | 支持尺度与分辨率共变。 | `06_experiments/stage_01h_viscous_decay_diagnosis/results/stage01h_evaluation.json` |

## 5. Stage 02：PIO 理论、数据、架构和静态训练全过程

### 5.1 Stage 02A：PIO 理论资格

【项目证据】 PIO 被定义为 additive correction，而非替换 SPH kernel。node residual 必须可分解为 pair-force；K1/K2 用反对称 pair basis 约束线动量，zero fallback 保留基线；reference hierarchy 区分解析、Fourier、semidiscrete 与候选 SPH。理论资格只授权合同与后续数据工作，不授权训练或性能。

### 5.2 Stage 02B：数据与 target 资格合同

【项目证据】 schema 同时保存 state、pair geometry、target、eligibility、uncertainty、source ancestry 与 family lineage。split 的独立单位是 lineage component/family，而不是粒子、边或 patch；normalization 只能从 train 统计量获得。该设计把 leakage 与 target validity 置于模型之前。

### 5.3 Stage 02C–02G：target 构造的连续失败与修正

【项目证据】 Stage 02C 得到 0 eligible，说明直接从候选 high-resolution SPH 形成教师标签不可接受；02D attribution 尚未闭合；02E 证明非零 target 主要含时间导数误差；02F 转为 R2S spatial target；02G 又识别 WLS reference bias。因果链是 `reference artifact → spatial reference redesign → reference bias diagnosis → Fourier/analytic reference`，而不是通过放宽 eligibility 强行生成数据。

### 5.4 Stage 02H：reference fidelity 突破

【项目证据】 QWLS2、CWLS3、Fourier2 与 analytic 路径被交叉比较；在冻结作用域内形成 reference fidelity qualification。各 reference 有不同角色：same-semidiscrete/数值 reference 用于离散归因，Fourier/analytic 用于避免同族偏差；该突破不把任何高分辨率 SPH 宣称为 universal truth。

### 5.5 Stage 02I 与 02I-R：空间 target 与守恒作用域

【项目证据】 Stage 02I 的 7/7 attribution 支持 spatial target，但 regular/jitter 结果显示 particle quadrature contamination 与 pair-force conservation compatibility 不能同时在原全域声明，故 pool 为 NOT_READY。02I-R 将可资格范围收窄为 pair-only regular scope，状态 `CONSERVATION_COMPATIBILITY_RESOLVED_PAIR_ONLY`；这是一项作用域修正，不是隐藏 jitter 失败。

### 5.6 Stage 02J 系列：数据集、泄漏与 regularity hard-gate

【项目证据】 初始 5 graph records 无法形成独立 family split；02J-R 扩展 multifamily 后仍不满足合同。02J-S/T/V 前瞻评估 regularity hard gate：PCG64 null、magnitude/direction decomposition 与 sign-flip false positive 表明 regularity 不是必要且充分的 eligibility 门，路线最终 `REGULARITY_HARD_GATE_ROUTE_TERMINATED`，其角色降为 diagnostic。02J-W 在不使用该 hard gate 的条件下形成 20 records、4 leakage components、10/5/5 train/validation/test blind split，并采用 train-only normalization，状态 `BLIND_MULTIFAMILY_DATASET_READY`。

### 5.7 Stage 02K：守恒型架构资格

【项目证据】 K0 是 central representability/torque diagnostic；K1、K2 资格化；KNEG 用于证明违反结构合同的 negative control 可被门识别。pair basis/antisymmetry 保证线动量，O(2)、Galilean、periodic、zero fallback、differentiability 与 negative tests 均在冻结范围检查。`qualified_architecture_count=2`，同时 `training_runs=0`、`optimizer_steps=0`；所以架构正确不等于可学习，attention superiority 未建立。

### 5.8 Stage 02L–02M：静态训练 v0.1

【项目证据】 Stage 02L 冻结 protocol、seed、预算与 sealed test。02M 执行 9 runs；K1、K2 的 train-fit seed pass 均为 0，validation/test 也不足；postfit structure 与资源通过。最终 `STATIC_PAIR_FORCE_FITTING_NOT_QUALIFIED`。sealed test 的存在不允许把 transfer 子结果替代 train hard gate。

### 5.9 Stage 02M-R：优化条件化归因

【项目证据】 失败模式为 NEVER_FIT_TRAIN。head tangent、AdamW epsilon、weight decay、feature identifiability 与 loss scale 审计表明 supervision scale 太小，优化更新被 epsilon/regularization 条件化。结论 `STATIC_FITTING_FAILURE_ATTRIBUTED_OPTIMIZATION_CONDITIONING` 只解释冻结 protocol，不证明所有 static tasks 一般不可学。

### 5.10 Stage 02M-P/M-Q：静态训练 v0.2

【项目证据】 v0.2 以 `a_sup=0.392220124168075 m s^-2` 重标监督，使用新 blind validation/test、AdamW epsilon=1e-12、weight decay=0，并冻结 9-run protocol。结果 K1 train gate 0/3、K2 1/3；K0/K1/K2 validation 与 sealed test 均 3/3，守恒均 PASS，但 A–E 总门全部 FAIL。故状态 `STATIC_PAIR_FORCE_FITTING_V02_NOT_QUALIFIED`，static route TERMINATED，Stage 02N、rollout 与 solver-in-the-loop 未授权。

### 5.11 Stage 02 最终结论

【项目证据】 dataset ready、architecture qualified；static learning not qualified；attention superiority not established；dynamic solver 在 Stage 02 未评价。可发表价值来自 reference/target governance、blind lineage split、hard conservation architecture 与两轮完整负结果；不能发表 static correction 性能或 rollout 结论。

| 阶段 | 冻结最终状态 | 执行/输出 | 阻断与边界 | 机器/冻结来源 |
|---|---|---|---|---|
| Stage 02A | PIO_THEORY_QUALIFICATION_COMPLETE | 理论合同完整；未生成数据或模型。 | 尚无可训练 target/dataset。 | `07_reports/stage02a_pio_theory_report.md` |
| Stage 02B | DATASET_QUALIFICATION_COMPLETE | 数据资格协议与 schema 完成。 | 未生成数据，完成协议不授权生成或训练。 | `07_reports/stage02b_final_report.md` |
| Stage 02C | DATASET_GENERATION_AUDIT_COMPLETE | 3 reference records、6 samples；4 diagnostic、2 topology rejected。 | eligible_for_future_training=0。 | `07_reports/stage02c_final_report.md` |
| Stage 02D | TARGET_ATTRIBUTION_QUALIFICATION_COMPLETE | 6/6 完成分解；4 diagnostic、2 rejected。 | 0 attribution PASS；resolution/disorder 混杂。 | `07_reports/stage02d_final_report.md` |
| Stage 02E | TARGET_CONSTRUCTION_COMPLETE | 8/8 非零且 reference audit 完整。 | 空间 assembly 为零/roundoff，时间/reference derivative 主导；0 qualified。 | `07_reports/stage02e_final_report.md` |
| Stage 02F | SPATIAL_TARGET_QUALIFICATION_COMPLETE | 5 个非零 same-state spatial candidates；support 与 reference gates 完成。 | resolution smoothness 仍 diagnostic；0 qualified。 | `07_reports/stage02f_final_report.md` |
| Stage 02G | SPATIAL_ATTRIBUTION_CLOSURE_COMPLETE | R2S bias、refinement、4/6 attribution 完整。 | R2S bias relative to target 可测但未受控；仍 diagnostic。 | `07_reports/stage02g_final_report.md` |
| Stage 02H | REFERENCE_FIDELITY_QUALIFICATION_COMPLETE | Fourier 与 analytic 在受控 periodic-vortex scope 内独立一致并 PASS。 | 不授权 dataset；QWLS2/CWLS3 仍 diagnostic。 | `07_reports/stage02h_final_report.md` |
| Stage 02I | QUALIFIED_SPATIAL_TARGET_POOL_NOT_READY | 7/7 six-component attribution PASS；5 pair-compatible、2 node-residual-only。 | 守恒兼容性不完整，Stage 02J 未授权。 | `07_reports/stage02i_final_report.md` |
| Stage 02I-R | CONSERVATION_COMPATIBILITY_RESOLVED_PAIR_ONLY | 五个 regular targets 确认 pair-only；jitter 保留诊断。 | 未形成 versioned dataset/split/normalization。 | `07_reports/stage02ir_final_report.md` |
| Stage 02J | CONTROLLED_REGULAR_DATASET_NOT_READY | 5 records schema/canonical/QC 完整。 | 单一 leakage component，无法合法切分；0 eligible。 | `07_reports/stage02j_final_report.md` |
| Stage 02J-R | MULTIFAMILY_CONTROLLED_DATASET_NOT_READY | 15 candidates reference/conservation PASS，lineages 分离。 | regularity attribution 5/6 diagnostic，未物化；split/normalization blocked。 | `07_reports/stage02jr_final_report.md` |
| Stage 02J-S | VERSIONED_MULTIFAMILY_DATASET_NOT_READY | structured development paths PASS；80 invariance checks PASS。 | negative-control false-positive gate failed；held-out 未释放。 | `07_reports/stage02js_final_report.md` |
| Stage 02J-T | REGULARITY_GATE_V03_NOT_QUALIFIED | 30 control combinations与 invariance 完成。 | CROSSMODE N12 magnitude gate failure；blind gate未开启。 | `07_reports/stage02jt_final_report.md` |
| Stage 02J-V | REGULARITY_HARD_GATE_ROUTE_TERMINATED | positive/hard-negative controls 与 real targets 完整。 | 9/192 invariance rows失败；禁止 v0.5。 | `07_reports/stage02jv_final_report.md` |
| Stage 02J-W | BLIND_MULTIFAMILY_DATASET_READY | 20/20 reference/target/conservation/QC PASS；4 lineage components；10/5/5 split；train-only normalization。 | 仅静态 pair-scope 数据；不含 solver/rollout evidence。 | `07_reports/stage02jw_final_report.md` |
| Stage 02K | PAIR_FORCE_PIO_ARCHITECTURE_QUALIFIED | K1/K2 antisymmetry、momentum、O(2)、periodicity、differentiability、O(E d) PASS。 | 未训练；结构正确性不证明 learnability。 | `07_reports/stage02k_final_report.md` |
| Stage 02L | STATIC_FITTING_PROTOCOL_READY | 协议、loss、optimizer、checkpoint、test seal 完整。 | 尚无训练结果。 | `07_reports/stage02l_final_report.md` |
| Stage 02M | STATIC_PAIR_FORCE_FITTING_NOT_QUALIFIED | 9/9 runs、sealed test、postfit、resources 完整。 | K1/K2 未满足冻结 A-E，训练拟合失败。 | `07_reports/stage02m_final_report.md` |
| Stage 02M-R | STATIC_FITTING_FAILURE_ATTRIBUTED_OPTIMIZATION_CONDITIONING | loss scale、Adam epsilon/weight decay、梯度/更新尺度证据一致。 | 归因是 diagnostic contribution，不证明改参必成功。 | `07_reports/stage02mr_final_report.md` |
| Stage 02M-P | STATIC_FITTING_PROTOCOL_V02_READY | v0.2 protocol、a_sup、9-run matrix、v1.1 collection、test seal READY。 | 无训练；仅授权一次 02M-Q。 | `07_reports/stage02mp_final_report.md` |
| Stage 02M-Q | STATIC_PAIR_FORCE_FITTING_V02_NOT_QUALIFIED | 9/9 conditioning/terminal/closure/test/postfit/resource evidence完整；C/D/E gates PASS。 | K1 train gate 0/3、K2 train gate 1/3；均未达 B 的2/3。 | `07_reports/stage02mq_final_report.md` |

## 6. Stage 03：动态混合求解器全过程

### 6.1 Stage 03A：动态新假设

【项目证据】 Stage 03 建立 correction-only dynamics 与 D0–D3 公平合同：D0 baseline，D1 instantaneous correction，D2 recurrent state，D3 causal history/temporal attention。RK2 每步在 start 和 midpoint 重建 graph，只在 accepted step 提交 history；Stage 02 checkpoint 禁止继承，避免把未资格 static fit 带入动态资格。

### 6.2 Stage 03B：动态 reference trajectory

【项目证据】 D-R1 manufactured/source trajectories、D-R2 same-semidiscrete high-accuracy time reference、D-R3 independent source-free references 形成 18 trajectories。两个 D-R1 family 与六个 D-R2 cases 通过；oblique shear A/B 通过；acoustic 仅 linear-regime conditional；periodic vortex 被拒绝为 exact source-free reference；D-R4 physical validation 不可用。reference role separation 由此固定。

### 6.3 Stage 03C：动态求解器实现

【项目证据】 D0–D3 interface、wrapped/unwrapped coordinates、source API、start/midpoint graph rebuild、accepted-only history commit、checkpoint/resume 和 one-step autograd 被验证。D0 implementation 48/48、zero correction 288/288 bitwise、结构/历史测试 72/72；资源门通过。`training_runs=0`、`optimizer_steps=0`、`multistep_AD_FD_runs=0`，因此状态只到 `DYNAMIC_RK2_HYBRID_IMPLEMENTATION_VERIFIED`。

### 6.4 Stage 03D：多步梯度与 topology

【项目证据】 360 required probes 中 216 找到 stable adjacent epsilon windows，144 失败；history gradient 0/6；per-stage conservation 540/540。TE1 cutoff birth/death 记录 1 birth、1 death，6/6 replay、12/12 fixed-side event AD/FD 通过，force jump finite/bounded，形成 `TOPOLOGY_EVENT_COMPONENT_QUALIFIED`。总体因 fixed-topology AD/FD 和 history gates 失败而为 `DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED`。

### 6.5 Stage 03D-R：失败归因

【项目证据】 same-math reverse/JVP 60/60 通过，排除基本 reverse implementation inconsistency；historical backend vs math JVP 仍有 sensitivity；extended FD 对 60 项中的 30 项找到稳定路径，共 2,640 paths；horizon scaling 90 项 bounded/nonmonotone；history 中 1 项 conditioning-limited、5 项低于 FD resolution；19/144 仍 unresolved。最终是 `DYNAMIC_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED`，不能压缩为单一“AD 错误”或“history 无效”。

### 6.6 Stage 03D-S：路线暂停

【项目证据】 因多步梯度未资格化，Stage 03E authorization=false；training、optimizer、rollout、solver-in-the-loop 均未执行。路线状态 `STAGE03_ROUTE_PAUSED_GRADIENT_BOUNDARY_COMPLETE`，不是 dynamic training failure。topology PASS 与 overall NOT_QUALIFIED 可并存，因为前者只覆盖确定性 event semantics 与 fixed-side derivatives，不覆盖 membership change 的全局可微性。

### 6.7 Stage 03 最终结论

【项目证据】 dynamic implementation verified；topology component qualified；multistep gradient not qualified；dynamic training not executed；rollout not tested。可发表的是实现合同、zero-correction、梯度矩阵、失败归因与 topology 边界；不可发表的是 trainability、性能、稳定 rollout 或 Transformer 优越性。

| 阶段 | 冻结最终状态 | 执行/输出 | 阻断与边界 | 机器/冻结来源 |
|---|---|---|---|---|
| Stage 03A | DYNAMIC_HYBRID_SOLVER_SPECIFICATION_COMPLETE | 45/45 contract hash checks；20/20 historical freeze checks；55/55 required files。 | 尚无动态实现、trajectory payload 或计算资格化。 | `stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03a_final_manifest.json` |
| Stage 03B | DYNAMIC_REFERENCE_TRAJECTORY_QUALIFICATION_COMPLETE | D-R1 两族、D-R2 六例、D-R3 两族 PASS；18/18 canonical trajectories；4302 RHS/rebuilds。 | acoustic 仅 linear-regime conditional；periodic vortex 不是 exact source-free reference；D-R4 不可用。 | `stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03b_final_manifest.json` |
| Stage 03C | DYNAMIC_RK2_HYBRID_IMPLEMENTATION_VERIFIED | D0 48/48；zero correction 288/288 bitwise；checkpoint 6/6；one-step autograd 6/6；全部结构/资源门 PASS。 | 未执行 multistep AD/FD、训练或 rollout 性能评价。 | `stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03c_final_manifest.json` |
| Stage 03D | DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED | 216/360 stable windows；540/540 stage conservation；TE1 birth/death、6/6 replay、12/12 event-side gradients PASS。 | 144/360 probes failure；history gradient 0/6；固定拓扑 AD/FD 与 history gate 未通过。 | `stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03d_final_manifest.json` |
| Stage 03D-R | DYNAMIC_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED | reverse/JVP 60/60；extended FD 2640 paths、30/60 stable；90 个 horizon 均 bounded/nonmonotone；topology status preserved。 | 19 unresolved；多类 FD conditioning/non-smooth/structural-zero 贡献并存；history rollout influence strongly attenuated。 | `stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03dr_final_manifest.json` |
| Stage 03D-S | STAGE03_ROUTE_PAUSED_GRADIENT_BOUNDARY_COMPLETE | 路线暂停；Stage03E=false。 | 多步梯度未资格。 | `stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03ds_final_manifest.json` |

## 7. 跨阶段因果链

【基于证据的推断】 项目方法进步的基本单位不是“成功阶段”，而是 `Failure → Diagnosis → Contract correction → New evidence → Remaining boundary`。每次修正都通过新阶段前瞻授权，旧 verdict 保持不可变。

| 失败/限制 | 诊断 | 合同修正 | 新证据 | 剩余边界 |
|---|---|---|---|---|
| 高分辨率教师假设 | 同族 SPH 含离散/模型误差 | V&V-first 与 candidate reference | reference hierarchy | 无 universal truth |
| TGV model mismatch | WCSPH EOS residual 主导 | WCSPH-compatible MMS | MMS spec/implementation/requalification | GCI 仍不成立 |
| 严格单调误差门失败 | plateau/cross-term cancellation | plateau-aware protocol | T/P/H/S PASS | 独立 V2 仍失败 |
| 独立 shear failure | dt-halving 小、随 N 改善 | finite-resolution diagnosis | Stage 01H 完成 | operator-form failure 未确认 |
| temporal target contamination | 时间导数误差进入标签 | spatial target redesign | R2S spatial target | reference bias 仍需处理 |
| WLS bias | 同族离散 reference 偏差 | Fourier/analytic reference | cross-reference agreement | 作用域限制 |
| jitter nonconservation | particle quadrature contamination | pair-only regular scope | conservation compatibility resolved | 不覆盖 jitter 全域 |
| single-family leakage | 5 records 不独立 | blind multifamily lineage split | 20 records; 4 components; 10/5/5 | 规模有限 |
| regularity hard-gate failure | false positive/必要性不足 | diagnostic-only regularity | route terminated with evidence | 不能作 eligibility |
| static fitting failure | optimization conditioning | v0.2 scale/optimizer/new blind families | transfer+conservation PASS | train-fit 仍失败 |
| static route termination | 架构正确不等于 static learnability | dynamic correction-only Stage 03 | D0–D3 implementation verified | gradient 未资格 |
| multistep gradient failure | FD conditioning/non-smooth/structural zero/history attenuation mixed | Stage 03 pause | 216/360 stable + topology component PASS | training 未授权 |
| Stage 03 pause | 现有 history 影响衰减 | Stage 04 local-causal task-aligned hypothesis | 未来增量接口 | 无 Stage 04 结果 |

## 8. 失败原因总论

【项目证据】 下表保留 A–R 类别，不把所有问题压缩成“失败”。基础设施/资源类可能被修复，但旧失败仍保留；科学假设、门设计与未执行事项分别处理。

| ID | 类别 | 代表阶段 | 冻结状态 | 直接原因 | 解决情况 | 论文意义 |
|---|---|---|---|---|---|---|
| F-A01 | A 环境与依赖问题 | Stage 00/01G-R | CONDITIONAL / EXECUTION_INFRA_READY_FOR_BENCHMARK | 平台/依赖边界而非科学模型失败。 | 已修复 | 工程可复现性 |
| F-B01 | B 数值实现错误 | Stage 01B | V1_FAIL | 上游接口和执行栈缺陷。 | 已修复 | 代码验证方法 |
| F-C01 | C 守恒/对称结构问题 | Stage 01B | V1_FAIL | 离散作用结构不是事后数值噪声。 | 已修复 | 结构保持贡献 |
| F-D01 | D 资源和内存问题 | Stage 01D–D-P | V2_FAIL → POLICY_PASS_ISOLATED_DEFAULT_GC | retired对象受GC延迟、topology与fixture语义共同影响。 | 已修复 | 资源资格化方法 |
| F-E01 | E 模型形式不一致 | Stage 01E | E_MODEL_FORM_ALIGNMENT_DOMINANT | 不可压TGV压力与WCSPH EOS初始化不一致。 | 未修复/不适用 | 模型形式辨识 |
| F-F01 | F reference specification问题 | Stage 01F3 | MMS_CONVERGENCE_VERIFICATION_FAIL | continuum truth、semidiscrete time truth与spatial truth角色混淆。 | 已修复 | reference治理 |
| F-G01 | G solution verification问题 | Stage 01D2/01F3B/01G | V2_QUALIFICATION_FAIL | 有限分辨率、支持尺度共变与门设计敏感性。 | 未修复/不适用 | V&V负结果 |
| F-H01 | H target attribution问题 | Stage 02D–I | QUALIFIED_SPATIAL_TARGET_POOL_NOT_READY | 高分辨率SPH并非自动truth。 | 已修复 | target资格链 |
| F-I01 | I dataset lineage/leakage问题 | Stage 02J | CONTROLLED_REGULAR_DATASET_NOT_READY | 粒子/边/patch随机切分会泄漏。 | 已修复 | 数据治理 |
| F-J01 | J regularity contract问题 | Stage 02J-S/T/V | REGULARITY_HARD_GATE_ROUTE_TERMINATED | regularity统计量不足以作为必要且稳定的资格硬门。 | 未修复/不适用 | 前瞻证伪 |
| F-K01 | K architecture representability问题 | Stage 02K | PAIR_FORCE_PIO_ARCHITECTURE_QUALIFIED | 此类别未观察架构硬失败，但representability不等于learnability。 | 已修复 | 结构/学习分离 |
| F-L01 | L optimization conditioning问题 | Stage 02M-R | STATIC_FITTING_FAILURE_ATTRIBUTED_OPTIMIZATION_CONDITIONING | 优化conditioning与尺度影响训练门。 | 未修复/不适用 | 失败归因 |
| F-M01 | M static learnability问题 | Stage 02M/M-Q | STATIC_PAIR_FORCE_FITTING_V02_NOT_QUALIFIED | train-fit硬门未满足，即使validation/test transfer与守恒通过。 | 未修复/不适用 | 负结果论文 |
| F-N01 | N dynamic implementation问题 | Stage 03C | DYNAMIC_RK2_HYBRID_IMPLEMENTATION_VERIFIED | 未观察实现硬失败；多步问题属于后续资格层。 | 已修复 | 动态实现合同 |
| F-O01 | O multistep differentiability问题 | Stage 03D/03D-R | DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED | 固定拓扑AD/FD稳定窗及history门失败。 | 未修复/不适用 | 梯度验证负结果 |
| F-P01 | P topology-event问题 | Stage 03D | TOPOLOGY_EVENT_COMPONENT_QUALIFIED | 拓扑分量是piecewise-smooth边界，不代表可微neighbor search。 | 已修复 | 拓扑验证 |
| F-Q01 | Q evidence/provenance问题 | Stage 01F5-P/P1/P2 | EXECUTION_MANIFEST_INCOMPLETE → repaired | 复杂工作流中合同完整性本身是资格前置。 | 已修复 | 证据治理 |
| F-R01 | R 未执行或未授权事项 | Stage 02/03 | NOT_AUTHORIZED / NOT_EXECUTED | 上游static fit和multistep gradient未资格。 | 未修复/不适用 | 发表边界 |

【基于证据的推断】 代码实现失败主要集中在 Stage 01B upstream backward 与早期结构；基础设施失败包括 evaluator 缺失、launch/retry 与 manifest incomplete；资源问题最终归因为 bounded GC delay 并转化为隔离政策。物理模型不一致促成 WCSPH MMS；reference/target 偏差促成 role separation；泄漏与 regularity 失败促成 blind split 与 diagnostic-only contract；优化条件化未挽救 static train-fit；multistep gradient 仍未解析。dynamic training 和 rollout 是 NOT_AUTHORIZED/NOT_EXECUTED，不能放入失败类别的科学结论。

## 9. 项目创新性与突破

### 9.1 已有强证据支持的创新

【项目证据】 项目内强证据支持 reference qualification hierarchy、hard pair-force conservation、blind lineage split、bitwise zero correction、RK2 graph rebuild/history commit、360-probe stable-window audit 与 topology birth/death component qualification。这里的“支持”指冻结合同内的实现或方法证据，不等于外部新颖性裁决。

### 9.2 方法学潜在创新，但需外部文献核验

【需外部文献核验】 verification-first PIO pipeline、plateau-aware V&V、联合 reverse/JVP/extended-FD/history/backend diagnosis、negative-evidence governance 的最接近前序与新颖性范围需以 P2 文献矩阵继续核验；不得使用“首次”“突破性”“显著领先”。

### 9.3 项目内部工程创新

【项目证据】 包括 trajectory-per-process/default-GC policy、sealed test、source identity/hash freeze、accepted-only history commit、bitwise zero correction、checkpoint/resume、delta manifest 与 claim audit。它们可以作为 reproducibility 与 implementation integrity 证据，不能直接升级为科学性能主张。

### 9.4 负结果与资格认定创新

【项目证据】 关键贡献是 architecture correctness 与 learnability 分离、component PASS 与 overall NOT_QUALIFIED 分层、regularity hard gate 前瞻证伪、旧失败不可变、NOT_EXECUTED 不写成 FAIL。这些机制使负结果成为方法边界而不是被删除的“无效工作”。

### 9.5 尚未得到结果支持的预期创新

【项目证据】 attention superiority、短历史改善 closure、dynamic training qualification、autonomous rollout、solver improvement、equal-error cost/utility、D-R4 physical validation 均无结果支持。

| ID | 类别 | 贡献 | 项目内证据强度 | 文献状态 | 限制 |
|---|---|---|---|---|---|
| I01 | A 科学认识 | 不把高分辨率SPH自动称为真值 | PROJECT_EVIDENCE_STRONG_INTERNAL | POTENTIAL_NOVELTY_REQUIRES_LITERATURE_VERIFICATION | 仅限冻结SPH-PIO-PoC合同与case scope |
| I02 | D reference治理 | 候选reference资格认定链 | PROJECT_EVIDENCE_STRONG_INTERNAL | POTENTIAL_NOVELTY_REQUIRES_LITERATURE_VERIFICATION | 仅限冻结SPH-PIO-PoC合同与case scope |
| I03 | B 数值方法 | WCSPH-compatible MMS与双路径闭合审计 | PROJECT_EVIDENCE_STRONG_INTERNAL | POTENTIAL_NOVELTY_REQUIRES_LITERATURE_VERIFICATION | 仅限冻结SPH-PIO-PoC合同与case scope |
| I04 | C V&V方法 | same-semidiscrete DOP853角色分离 | PROJECT_EVIDENCE_STRONG_INTERNAL | POTENTIAL_NOVELTY_REQUIRES_LITERATURE_VERIFICATION | 仅限冻结SPH-PIO-PoC合同与case scope |
| I05 | C V&V方法 | plateau-aware temporal/spatial verification | PROJECT_EVIDENCE_STRONG_INTERNAL | POTENTIAL_NOVELTY_REQUIRES_LITERATURE_VERIFICATION | 仅限冻结SPH-PIO-PoC合同与case scope |
| I06 | A 科学认识 | source-free shear/acoustic验证边界 | PROJECT_EVIDENCE_SCOPED | POTENTIAL_NOVELTY_REQUIRES_LITERATURE_VERIFICATION | 仅限冻结SPH-PIO-PoC合同与case scope |
| I07 | E 守恒神经架构 | pair-force antisymmetry硬保证线动量守恒 | PROJECT_EVIDENCE_STRONG_INTERNAL | POTENTIAL_NOVELTY_REQUIRES_LITERATURE_VERIFICATION | 仅限冻结SPH-PIO-PoC合同与case scope |
| I08 | D 数据治理 | family-lineage leakage graph与blind split | PROJECT_EVIDENCE_STRONG_INTERNAL | POTENTIAL_NOVELTY_REQUIRES_LITERATURE_VERIFICATION | 仅限冻结SPH-PIO-PoC合同与case scope |
| I09 | C V&V方法 | regularity hard-gate前瞻校准和证伪 | PROJECT_EVIDENCE_STRONG_INTERNAL | POTENTIAL_NOVELTY_REQUIRES_LITERATURE_VERIFICATION | 仅限冻结SPH-PIO-PoC合同与case scope |
| I10 | I 负结果治理 | static learnability与architecture correctness分离 | PROJECT_EVIDENCE_SCOPED | POTENTIAL_NOVELTY_REQUIRES_LITERATURE_VERIFICATION | 仅限冻结SPH-PIO-PoC合同与case scope |
| I11 | G 梯度验证 | optimization conditioning量化归因 | PROJECT_EVIDENCE_SCOPED | POTENTIAL_NOVELTY_REQUIRES_LITERATURE_VERIFICATION | 仅限冻结SPH-PIO-PoC合同与case scope |
| I12 | F 动态求解器 | bitwise zero-correction equivalence | PROJECT_EVIDENCE_STRONG_INTERNAL | SUPPORTED_NOVELTY_GAP | 仅限冻结SPH-PIO-PoC合同与case scope |
| I13 | F 动态求解器 | RK2 start/midpoint graph rebuild与accepted-only history commit | PROJECT_EVIDENCE_STRONG_INTERNAL | SUPPORTED_NOVELTY_GAP | 仅限冻结SPH-PIO-PoC合同与case scope |
| I14 | E 守恒神经架构 | D0/D1/D2/D3公平比较合同 | PROJECT_EVIDENCE_STRONG_INTERNAL | PARTIAL_PRECEDENT | 仅限冻结SPH-PIO-PoC合同与case scope |
| I15 | D reference治理 | D-R1/D-R2/D-R3/D-R4 reference hierarchy | PROJECT_EVIDENCE_STRONG_INTERNAL | SUPPORTED_NOVELTY_GAP | 仅限冻结SPH-PIO-PoC合同与case scope |
| I16 | G 梯度验证 | 360-probe multistep AD/FD stable-window qualification | PROJECT_EVIDENCE_STRONG_INTERNAL | SUPPORTED_NOVELTY_GAP | 仅限冻结SPH-PIO-PoC合同与case scope |
| I17 | G 梯度验证 | reverse/JVP、extended FD、history attenuation、backend sensitivity联合诊断 | PROJECT_EVIDENCE_STRONG_INTERNAL | PARTIAL_PRECEDENT | 仅限冻结SPH-PIO-PoC合同与case scope |
| I18 | H 拓扑事件 | deterministic cutoff birth/death与fixed-side gradient资格 | PROJECT_EVIDENCE_STRONG_INTERNAL | POTENTIAL_NOVELTY_REQUIRES_LITERATURE_VERIFICATION | 仅限冻结SPH-PIO-PoC合同与case scope |
| I19 | H 拓扑事件 | topology component PASS与overall gradient NOT_QUALIFIED分层 | PROJECT_EVIDENCE_STRONG_INTERNAL | POTENTIAL_NOVELTY_REQUIRES_LITERATURE_VERIFICATION | 仅限冻结SPH-PIO-PoC合同与case scope |
| I20 | J 工程可复现性 | 全程保留失败并禁止结果后改门 | PROJECT_EVIDENCE_STRONG_INTERNAL | POTENTIAL_NOVELTY_REQUIRES_LITERATURE_VERIFICATION | 仅限冻结SPH-PIO-PoC合同与case scope |

## 10. 论文工作过程论述素材

### 10.1 研究路线形成过程

【基于证据的推断】 本研究并非从预设的 neural-SPH 性能优势出发，而是从“可学习局部相互作用能否在保持 SPH 物理与数值合同的条件下进入求解链”出发。早期 V0 证明执行可行后，V1 立即暴露 kernel、Laplacian、守恒与 backward 缺陷，使项目把 V&V 置于训练之前。此后每一级 reference、target、dataset、architecture 与 gradient 都成为显式资格层。

### 10.2 方法不断修正的原因

【基于证据的推断】 修正来自不同类型的证据：实现错误需要算子替换；资源增长需要生命周期归因和运行政策；TGV 错配需要制造解；严格误差门需要 plateau-aware 但不回写旧失败；target contamination 需要重建 reference；leakage 需要 family split；static fit 需要 conditioning audit；gradient failure 需要 stable-window 与联合诊断。方法演化因此是因果链，而非事后叙事美化。

### 10.3 V&V-first 方法的形成

【基于证据的推断】 V&V-first 的核心是把 L0 specification、L1 implementation、L2 code verification、L3 solution verification、L4 reference、L5 data、L6 structural model、L7 training、L8 rollout、L9 physical validation、L10 cost/utility 分开。上游局部 PASS 只能授权下一级，不允许越级生成性能 claim。

### 10.4 PIO 架构的形成

【基于证据的推断】 PIO 从“Transformer 替代 SPH”收敛为“受约束 pair correction”。pair antisymmetry、O(2)/Galilean/periodic、zero fallback 与 KNEG 将结构正确性变成可验证合同；D0–D3 再把瞬时、递归、历史模型置于同一 solver/interface 下比较。

### 10.5 静态路线为何终止

【项目证据】 v0.1 与 v0.2 各执行 9 runs；v0.2 已修正监督尺度、optimizer conditioning 与 blind families，且 validation/test/conservation 通过，但 K1 train 0/3、K2 1/3，未满足 2-of-3 train gate。继续 v0.3 会违反冻结停止规则，故 static route TERMINATED。

### 10.6 动态路线为何暂停

【项目证据】 动态实现本身通过，但 360-probe 多步梯度只有 216 stable windows、history 0/6，归因仍 mixed/unresolved。没有可资格化的 task-aligned gradient，训练不会产生可解释证据，因此 Stage 03E 未授权，路线 PAUSED。

### 10.7 Stage 04 新假设如何合理产生

【基于证据的推断】 Stage 04 local-causal hypothesis 来自两条已知边界：static global mapping 未资格化，长历史梯度影响强衰减。合理的新问题是更局部、更 task-aligned、更短因果路径是否改善 trainability；它是未来待证假设，不是 Stage 00–03 的结果。

## 11. 可发表内容分层

| 层级 | 内容 | 允许的主张 | 边界 |
|---|---|---|---|
| MAIN_TEXT_CANDIDATE | Stage 01 V&V 因果链；Stage 02 reference/target；blind dataset；hard-conservative architecture；Stage 03 implementation/AD-FD/topology | 冻结状态、关键正负结果、方法演化 | 不得隐藏 V2/static/gradient failure |
| SUPPLEMENT_CANDIDATE | 全 run/probe matrix、seed/checkpoint/hash、reference QC、资源与 retry、完整门表 | 可复现细节与完整不利证据 | 正文必须保留总体结论 |
| INTERNAL_AUDIT_ONLY | launch logs、private seals、冗长 debug trace、访问控制记录 | 不作科学主张 | 仅审计与 provenance |
| NOT_PUBLISHABLE_WITHOUT_NEW_EVIDENCE | dynamic training、rollout、solver improvement、Transformer superiority、D-R4 physical validation、cost/utility | 只能写未执行/未测试 | 需 Stage 04 或新授权证据 |

## 12. 合并一篇方案

【论文建议】 仅当 Stage 04C/E/F/G 全部强通过，D3 相较 D1/D2 具有稳定、独立、等误差优势，且 independent validation、refinement 和 cost 完整时，才形成 Stage 00–04 整合论文。研究问题可写为“如何以分层 V&V 和守恒合同建立可训练、可验证的 dynamic neural-SPH correction”。标题候选：*Verification-first conservative particle interaction operators for dynamic SPH correction*；章节依次为 V&V、reference/data、conservative PIO、dynamic implementation、gradient qualification、training/rollout/validation/cost。

【论文建议】 主图可包括证据层级、reference chain、pair architecture、D0–D3/RK2 graph-history、360-probe matrix、Stage04 learning/rollout/refinement/cost；表格包括 gate ledger、dataset split、ablation/equal-error cost。Stage 02 static failure 与 Stage 03 gradient failure必须作为方法演化和边界保留，完整矩阵入 Supplement。CMAME 优势是从 verification 到 solver consequence 的完整链；致命风险是任一 Stage04 关键门弱、篇幅过长或 performance claim 缺独立验证。

## 13. 拆分两篇方案

### Paper 1

【论文建议】 独立问题：在训练之前，如何资格化 SPH correction 的 reference、守恒结构、动态实现、多步梯度与 topology，并保存负结果？独立主结果归属 Stage 00–03：V&V-first chain、reference/target governance、blind dataset、hard conservation、zero correction、360-probe/gradient limits、TE1 topology。期刊定位为计算力学方法/V&V 层；最低证据已存在，但外部文献定位和稿件压缩仍需完成。

### Paper 2

【论文建议】 独立问题：在 Paper 1 冻结合同上，local-causal dynamic model 是否获得 training、autonomous rollout、independent validation、refinement 与 equal-error cost 优势？主要图表只使用 Stage04 新结果。Paper 1 的方程、reference、architecture 仅作交叉引用或背景；不得再次把 zero correction、同一 AD/FD 或 topology 结果作为主创新。最低证据是 Stage04C/E/F/G strong PASS 与公平 D0/D1/D2/D3 comparison。

【论文建议】 重复发表风险通过 `cross_paper_overlap_matrix` 与 anti-salami rules 控制：同一结果只能有一个 primary owner；相同图表不得重复；共享方程需压缩并交叉引用；负结果也不得在两篇中分别冒充不同主贡献。

## 14. Stage 04 后决策问题

1. Stage 04C task-aligned gradient 是否资格化？
2. Stage 04E 是否完成训练资格？
3. D3 相较 D1/D2 是否稳定、独立且在等误差条件下改善？
4. Autonomous rollout 是否通过？
5. Independent D-R3 validation 是否通过？
6. 时间/空间加密是否完整？
7. Equal-error cost 是否具有优势？
8. Stage 02–03 是否保持脱离 Stage 04 的独立方法价值？
9. 两篇论文的主结果是否足够不重叠？
10. 哪种方案符合 CMAME 所需证据强度与篇幅？

## 15. 一页式决策摘要

# Stage 04 后合并/拆分决策摘要

【项目证据】 当前可独立发表资产：Stage 01 V&V/失败修正链；Stage 02 reference-target-data-architecture 与 static negative result；Stage 03 dynamic implementation、zero correction、AD/FD matrix、failure attribution、topology component；全程 hash/provenance/claim boundary。

【项目证据】 当前不能发表的 claim：Stage 01 V2 restored；static correction qualified；attention/Transformer superior；multistep gradient qualified；dynamic training completed；autonomous rollout stable；solver more accurate/faster/cheaper；D-R4 physical validation complete。

【论文建议】 Stage 04 核心证据：task-aligned gradient、training gates、D3 vs D1/D2、autonomous rollout、independent validation、time/space refinement、equal-error cost、完整失败与 hash。合并条件是全链强通过且篇幅可控；拆分条件是 Stage 00–03 方法价值独立、Stage04 形成不重叠性能问题；Stage04 失败时 fallback 为 verification-first/gradient-limit/topology/negative-result methodology paper。最终合并/拆分决定暂缓，不以预期结果替代证据。

## 附录 A：Stage 00–03 完整状态账本

| 阶段 | 冻结最终状态 | 执行/输出 | 阻断与边界 | 机器/冻结来源 |
|---|---|---|---|---|
| Stage 00 | CONDITIONAL | CPU/MPS操作检查通过；diffSPH仅安装/导入/邻域预检。 | 完整diffSPH求解器未在该阶段运行。 | `07_reports/stage_00_summary.md` |
| Stage 01 | CONDITIONAL PASS (V0 only) | V0工程可执行；V1部分；V2未完成；V3未开始。 | 不可作fixed-physics truth。 | `07_reports/stage_01_scope_reclassification.md` |
| Stage 01B | V1_FAIL | kernel/Laplacian/AD及结构门触发停止。 | V2/TGV未授权。 | `07_reports/stage_01b_final_vv_report.md` |
| Stage 01C | C1_PASS_C2_PASS_C3_PASS_C4_PASS | 四项静态重资格门通过。 | 不是动态V2。 | `06_experiments/stage_01c_operator_candidates/results/stage01c_gate_status.txt` |
| Stage 01D | V2_FAIL | N32 smoke资源门失败；后续多门NOT_RUN。 | 资源增长机制未明。 | `06_experiments/stage_01d_fixed_physics_tgv/results/stage01d_v2_status.txt` |
| Stage 01D-R | RESOURCE_FAIL_LINEAR_GROWTH | 资源重资格仍失败。 | 不能据此直接称memory leak。 | `06_experiments/stage_01dr_memory_diagnosis/results/stage01dr_resource_status.txt` |
| Stage 01D-R2 | ATTRIBUTION_UNRESOLVED | storage归因未唯一解析。 | cutoff topology与生命周期混杂。 | `06_experiments/stage_01dr2_storage_attribution/results/stage01dr2_attribution_status.txt` |
| Stage 01D-R3 | R3_CONFIRMATION_UNRESOLVED | 证据仍未解析。 | weakref语义待核。 | `06_experiments/stage_01dr3_topology_confirmation/results/stage01dr3_status.txt` |
| Stage 01D-R4 | R4_RETENTION_REDETECTED | retention被重新检测。 | GC时序未定位。 | `06_experiments/stage_01dr4_weakref_semantics/results/stage01dr4_status.txt` |
| Stage 01D-R5 | R5_BOUNDED_GC_DELAY_CONFIRMED | GC-disabled线性；default-GC 2000步有界。 | 不能把旧资源失败改写为假阳性。 | `06_experiments/stage_01dr5_gc_cycle_localization/results/stage01dr5_status.txt` |
| Stage 01D-P | POLICY_PASS_ISOLATED_DEFAULT_GC | 3/3 canary通过；政策资格化。 | 仅资源政策，不是V2数据。 | `06_experiments/stage_01dp_resource_policy/results/stage01dp_status.txt` |
| Stage 01D2 | STAGE01D2_V2_REQUALIFICATION_FAIL | 时间可解释，但空间非单调、jitter/资源门失败。 | 不能进入V3。 | `06_experiments/stage_01d2_v2_requalification/results/stage01d2_evaluation.json` |
| Stage 01E | E_MODEL_FORM_ALIGNMENT_DOMINANT | EOS初始化残差主导；两项渐近拟合不可识别。 | 不改变V2失败。 | `06_experiments/stage_01e_error_decomposition/results/stage01e_evaluation.json` |
| Stage 01F | MMS_SPECIFICATION_PASS | MMS规格通过。 | 规格不等于实现/收敛。 | `06_experiments/stage_01f_mms_design/results/stage01f_evaluation.json` |
| Stage 01F2 | MMS_IMPLEMENTATION_VERIFIED_PASS | 实现验证通过。 | 未建立收敛资格。 | `06_experiments/stage_01f2_mms_implementation/results/stage01f2_evaluation_v2.json` |
| Stage 01F3 | MMS_CONVERGENCE_VERIFICATION_FAIL | reference/topology identity硬门前停止或收敛门失败。 | 需reference资格化。 | `06_experiments/stage_01f3_mms_convergence/results/stage01f3_evaluation.json` |
| Stage 01F3-R | SEMIDISCRETE_REFERENCE_QUALIFIED_DENSE_EQUIVALENT | reference资格化。 | 不修复原F3失败。 | `06_experiments/stage_01f3r_reference_qualification/results/stage01f3r_evaluation.json` |
| Stage 01F3B | MMS_CONVERGENCE_VERIFICATION_FAIL | 仍为收敛资格失败；GCI不成立。 | plateau/cancellation影响门设计。 | `06_experiments/stage_01f3b_mms_convergence/results/stage01f3b_evaluation.json` |
| Stage 01F3C | CT2_MIXED_OR_UNRESOLVED | 时间阶接近2但抵消门失败，混合/未解析。 | 严格单点门不稳健。 | `06_experiments/stage_01f3c_ct2_adjudication/results/stage01f3c_evaluation.json` |
| Stage 01F4 | PLATEAU_AWARE_PROTOCOL_APPROVED | 新协议批准；旧失败保持。 | 尚未执行。 | `06_experiments/stage_01f4_protocol_adjudication/results/stage01f4_evaluation.json` |
| Stage 01F5 | PLATEAU_AWARE_REQUALIFICATION_DESIGN_APPROVED | 设计批准。 | 执行清单分支不全。 | `06_experiments/stage_01f5_requalification_design/results/stage01f5_evaluation.json` |
| Stage 01F5-P | EXECUTION_MANIFEST_INCOMPLETE | 执行清单不完整。 | 空间horizon参数未绑定。 | `06_experiments/stage_01f5p_branch_completeness/results/stage01f5p_evaluation.json` |
| Stage 01F5-Q | FORMAL_SPACE_EXECUTION_BUNDLE_READY | 正式执行bundle就绪。 | 尚未产生资格。 | `06_experiments/stage_01f5q_space_horizon_amendment/results/stage01f5q_evaluation.json` |
| Stage 01F5B | PLATEAU_AWARE_MMS_REQUALIFICATION_PASS | 一次性重资格通过；基础设施retry单独保留。 | 不等于V2 physical validation。 | `06_experiments/stage_01f5b_requalification_execution/results/stage01f5b_evaluation.json` |
| Stage 01G design | INDEPENDENT_VALIDATION_AND_V2_DESIGN_APPROVED | 设计通过但未执行。 | 需独立授权。 | `06_experiments/stage_01g_validation_design/results/stage01g_design_evaluation.json` |
| Stage 01G-P | INDEPENDENT_VALIDATION_EXECUTION_READY | preexecution audit通过。 | evaluator尚需资格化。 | `06_experiments/stage_01gp_preexecution_audit/results/stage01gp_evaluation.json` |
| Stage 01G-E | INDEPENDENT_VALIDATION_EVALUATOR_READY | evaluator就绪。 | 执行基础设施仍需授权。 | `06_experiments/stage_01ge_evaluator_qualification/results/stage01ge_evaluation.json` |
| Stage 01G preflight V2 | INDEPENDENT_VALIDATION_EXECUTION_AUTHORIZED | 执行获授权；未生成V2状态。 | 需基础设施成功。 | `06_experiments/stage_01g_execution_preflight_v2/results/stage01gv2_evaluation.json` |
| Stage 01G-R | EXECUTION_INFRA_READY_FOR_BENCHMARK | 修复后基础设施就绪。 | 科学门仍待执行。 | `06_experiments/stage_01gr_execution_infrastructure_repair/results/stage01gr_evaluation.json` |
| Stage 01G execution | V2_QUALIFICATION_FAIL | acoustic通过；shear N48门失败；V2失败。 | SHEAR3衰减误差。 | `06_experiments/stage_01g_validation_execution/results/stage01g_evaluation_reapplication_01.json` |
| Stage 01H | VISCOSITY_DIAGNOSIS_COMPLETE | 分类FINITE_RESOLUTION_DOMINANT；算子形式失败未确认。 | 支持尺度与分辨率共变。 | `06_experiments/stage_01h_viscous_decay_diagnosis/results/stage01h_evaluation.json` |
| Stage 02A | PIO_THEORY_QUALIFICATION_COMPLETE | 理论合同完整；未生成数据或模型。 | 尚无可训练 target/dataset。 | `07_reports/stage02a_pio_theory_report.md` |
| Stage 02B | DATASET_QUALIFICATION_COMPLETE | 数据资格协议与 schema 完成。 | 未生成数据，完成协议不授权生成或训练。 | `07_reports/stage02b_final_report.md` |
| Stage 02C | DATASET_GENERATION_AUDIT_COMPLETE | 3 reference records、6 samples；4 diagnostic、2 topology rejected。 | eligible_for_future_training=0。 | `07_reports/stage02c_final_report.md` |
| Stage 02D | TARGET_ATTRIBUTION_QUALIFICATION_COMPLETE | 6/6 完成分解；4 diagnostic、2 rejected。 | 0 attribution PASS；resolution/disorder 混杂。 | `07_reports/stage02d_final_report.md` |
| Stage 02E | TARGET_CONSTRUCTION_COMPLETE | 8/8 非零且 reference audit 完整。 | 空间 assembly 为零/roundoff，时间/reference derivative 主导；0 qualified。 | `07_reports/stage02e_final_report.md` |
| Stage 02F | SPATIAL_TARGET_QUALIFICATION_COMPLETE | 5 个非零 same-state spatial candidates；support 与 reference gates 完成。 | resolution smoothness 仍 diagnostic；0 qualified。 | `07_reports/stage02f_final_report.md` |
| Stage 02G | SPATIAL_ATTRIBUTION_CLOSURE_COMPLETE | R2S bias、refinement、4/6 attribution 完整。 | R2S bias relative to target 可测但未受控；仍 diagnostic。 | `07_reports/stage02g_final_report.md` |
| Stage 02H | REFERENCE_FIDELITY_QUALIFICATION_COMPLETE | Fourier 与 analytic 在受控 periodic-vortex scope 内独立一致并 PASS。 | 不授权 dataset；QWLS2/CWLS3 仍 diagnostic。 | `07_reports/stage02h_final_report.md` |
| Stage 02I | QUALIFIED_SPATIAL_TARGET_POOL_NOT_READY | 7/7 six-component attribution PASS；5 pair-compatible、2 node-residual-only。 | 守恒兼容性不完整，Stage 02J 未授权。 | `07_reports/stage02i_final_report.md` |
| Stage 02I-R | CONSERVATION_COMPATIBILITY_RESOLVED_PAIR_ONLY | 五个 regular targets 确认 pair-only；jitter 保留诊断。 | 未形成 versioned dataset/split/normalization。 | `07_reports/stage02ir_final_report.md` |
| Stage 02J | CONTROLLED_REGULAR_DATASET_NOT_READY | 5 records schema/canonical/QC 完整。 | 单一 leakage component，无法合法切分；0 eligible。 | `07_reports/stage02j_final_report.md` |
| Stage 02J-R | MULTIFAMILY_CONTROLLED_DATASET_NOT_READY | 15 candidates reference/conservation PASS，lineages 分离。 | regularity attribution 5/6 diagnostic，未物化；split/normalization blocked。 | `07_reports/stage02jr_final_report.md` |
| Stage 02J-S | VERSIONED_MULTIFAMILY_DATASET_NOT_READY | structured development paths PASS；80 invariance checks PASS。 | negative-control false-positive gate failed；held-out 未释放。 | `07_reports/stage02js_final_report.md` |
| Stage 02J-T | REGULARITY_GATE_V03_NOT_QUALIFIED | 30 control combinations与 invariance 完成。 | CROSSMODE N12 magnitude gate failure；blind gate未开启。 | `07_reports/stage02jt_final_report.md` |
| Stage 02J-V | REGULARITY_HARD_GATE_ROUTE_TERMINATED | positive/hard-negative controls 与 real targets 完整。 | 9/192 invariance rows失败；禁止 v0.5。 | `07_reports/stage02jv_final_report.md` |
| Stage 02J-W | BLIND_MULTIFAMILY_DATASET_READY | 20/20 reference/target/conservation/QC PASS；4 lineage components；10/5/5 split；train-only normalization。 | 仅静态 pair-scope 数据；不含 solver/rollout evidence。 | `07_reports/stage02jw_final_report.md` |
| Stage 02K | PAIR_FORCE_PIO_ARCHITECTURE_QUALIFIED | K1/K2 antisymmetry、momentum、O(2)、periodicity、differentiability、O(E d) PASS。 | 未训练；结构正确性不证明 learnability。 | `07_reports/stage02k_final_report.md` |
| Stage 02L | STATIC_FITTING_PROTOCOL_READY | 协议、loss、optimizer、checkpoint、test seal 完整。 | 尚无训练结果。 | `07_reports/stage02l_final_report.md` |
| Stage 02M | STATIC_PAIR_FORCE_FITTING_NOT_QUALIFIED | 9/9 runs、sealed test、postfit、resources 完整。 | K1/K2 未满足冻结 A-E，训练拟合失败。 | `07_reports/stage02m_final_report.md` |
| Stage 02M-R | STATIC_FITTING_FAILURE_ATTRIBUTED_OPTIMIZATION_CONDITIONING | loss scale、Adam epsilon/weight decay、梯度/更新尺度证据一致。 | 归因是 diagnostic contribution，不证明改参必成功。 | `07_reports/stage02mr_final_report.md` |
| Stage 02M-P | STATIC_FITTING_PROTOCOL_V02_READY | v0.2 protocol、a_sup、9-run matrix、v1.1 collection、test seal READY。 | 无训练；仅授权一次 02M-Q。 | `07_reports/stage02mp_final_report.md` |
| Stage 02M-Q | STATIC_PAIR_FORCE_FITTING_V02_NOT_QUALIFIED | 9/9 conditioning/terminal/closure/test/postfit/resource evidence完整；C/D/E gates PASS。 | K1 train gate 0/3、K2 train gate 1/3；均未达 B 的2/3。 | `07_reports/stage02mq_final_report.md` |
| Stage 03A | DYNAMIC_HYBRID_SOLVER_SPECIFICATION_COMPLETE | 45/45 contract hash checks；20/20 historical freeze checks；55/55 required files。 | 尚无动态实现、trajectory payload 或计算资格化。 | `stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03a_final_manifest.json` |
| Stage 03B | DYNAMIC_REFERENCE_TRAJECTORY_QUALIFICATION_COMPLETE | D-R1 两族、D-R2 六例、D-R3 两族 PASS；18/18 canonical trajectories；4302 RHS/rebuilds。 | acoustic 仅 linear-regime conditional；periodic vortex 不是 exact source-free reference；D-R4 不可用。 | `stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03b_final_manifest.json` |
| Stage 03C | DYNAMIC_RK2_HYBRID_IMPLEMENTATION_VERIFIED | D0 48/48；zero correction 288/288 bitwise；checkpoint 6/6；one-step autograd 6/6；全部结构/资源门 PASS。 | 未执行 multistep AD/FD、训练或 rollout 性能评价。 | `stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03c_final_manifest.json` |
| Stage 03D | DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED | 216/360 stable windows；540/540 stage conservation；TE1 birth/death、6/6 replay、12/12 event-side gradients PASS。 | 144/360 probes failure；history gradient 0/6；固定拓扑 AD/FD 与 history gate 未通过。 | `stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03d_final_manifest.json` |
| Stage 03D-R | DYNAMIC_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED | reverse/JVP 60/60；extended FD 2640 paths、30/60 stable；90 个 horizon 均 bounded/nonmonotone；topology status preserved。 | 19 unresolved；多类 FD conditioning/non-smooth/structural-zero 贡献并存；history rollout influence strongly attenuated。 | `stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03dr_final_manifest.json` |
| Stage 03D-S | STAGE03_ROUTE_PAUSED_GRADIENT_BOUNDARY_COMPLETE | 路线暂停；Stage03E=false。 | 多步梯度未资格。 | `stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03ds_final_manifest.json` |

## 附录 B：关键数字与机器位置

| ID | 值 | 单位 | 阶段 | 状态 | 机器来源/键 | 含义 |
|---|---|---|---|---|---|---|
| KF001 | Apple M2; 16 GB unified memory; 8-core Metal GPU | hardware identity | Stage 00 | CONDITIONAL | `07_reports/stage_00_summary.md`<br>`table rows 11–16` | 保守规模 PoC 环境身份 |
| KF002 | 1024 | particles | Stage 00 | CONDITIONAL | `07_reports/stage_00_summary.md`<br>`lines 64–67` | Stage 00 实测建议上限，不可外推 |
| KF003 | [256, 576, 1024] | particles | Stage 01 | CONDITIONAL | `07_reports/stage_01_scope_reclassification.md`<br>`lines 25–33` | CPU canonical cases；MPS 为 CPU-neighbor hybrid |
| KF004 | 3 | complete SPH steps | Stage 01 | CONDITIONAL | `07_reports/stage_01_scope_reclassification.md`<br>`lines 32–33` | initial-velocity-amplitude value-path AD/FD |
| KF005 | C1_PASS_C2_PASS_C3_PASS_C4_PASS | gate status | Stage 01C | PASS | `06_experiments/stage_01c_operator_candidates/results/stage01c_gate_status.txt`<br>`entire file` | 静态算子重资格，不是动态 V2 |
| KF006 | 2000 | steps | Stage 01D-R5 | DIAGNOSTIC | `06_experiments/stage_01dp_resource_policy/results/analysis_summary.json`<br>`/r5_default_gc_evidence_steps` | default-GC 长窗有界；disabled-GC 线性增长 |
| KF007 | 3/3 | observed/pass canaries | Stage 01D-P | PASS | `06_experiments/stage_01dp_resource_policy/results/campaign_summary.json`<br>`/observed_processes; /pass_processes` | 隔离进程/default-GC 资源政策 |
| KF008 | 20 | AD cases | Stage 01D2 | QUALIFIED_COMPONENT | `06_experiments/stage_01d2_v2_requalification/results/stage01d2_evaluation.json`<br>`/ad_completed_cases` | AD 子门通过但总体失败 |
| KF009 | 9.337695248846364 | multiplier | Stage 01D2 | FAIL | `06_experiments/stage_01d2_v2_requalification/results/stage01d2_evaluation.json`<br>`/jitter10_median_velocity_error_multiplier` | 10% jitter 速度误差中位放大 |
| KF010 | [0.5115416951943935, 1.1113178279945766] | observed slope | Stage 01D2 | NOT_QUALIFIED | `06_experiments/stage_01d2_v2_requalification/results/stage01d2_evaluation.json`<br>`/space_slope_velocity; /space_slope_modal` | 空间趋势仍不足以支持 GCI |
| KF011 | [210, 21] | static cases; short trajectories | Stage 01E | DIAGNOSTIC | `06_experiments/stage_01e_error_decomposition/results/stage01e_evaluation.json`<br>`/static_cases; /short_trajectories` | 模型形式归因样本规模 |
| KF012 | [144.05253207786865, 1621.690538799039] | ratio | Stage 01E | DIAGNOSTIC | `06_experiments/stage_01e_error_decomposition/results/stage01e_evaluation.json`<br>`/EOS_to_pressure_operator_ratio; /EOS_to_viscosity_ratio` | EOS 初始化残差相对算子项占优 |
| KF013 | 69 | effective PASS runs | Stage 01F5B | PASS | `06_experiments/stage_01f5b_requalification_execution/results/stage01f5b_evaluation.json`<br>`/postexecution_evaluator_amendment/registry_at_amendment/pass` | plateau-aware 一次性重资格矩阵 |
| KF014 | False | all 8 GCI qualified fields | Stage 01F5B | NOT_QUALIFIED | `06_experiments/stage_01f5b_requalification_execution/results/stage01f5b_evaluation.json`<br>`/gci/MMS_A/density/qualified; /gci/MMS_A/position/qualified; /gci/MMS_A/pressure/qualified; /gci/MMS_A/velocity/qualified; /gci/MMS_B/density/qualified; /gci/MMS_B/position/qualified; /gci/MMS_B/pressure/qualified; /gci/MMS_B/velocity/qualified` | T/P/H/S 通过不等于 GCI 成立 |
| KF015 | 12 | executed runs | Stage 01G | FAIL | `06_experiments/stage_01g_validation_execution/results/stage01g_evaluation_reapplication_01.json`<br>`/executed_run_count` | 独立 shear/acoustic 矩阵完整执行 |
| KF016 | 0.027949503268503754 | relative decay-rate error | Stage 01G | FAIL | `06_experiments/stage_01g_validation_execution/results/stage01g_shear_gates_reapplication_01.json`<br>`/gates/SHEAR3/evidence` | 唯一决定性 SHEAR3 失败 |
| KF017 | 6.407461957919563e-08 | maximum relative change | Stage 01H | DIAGNOSTIC | `06_experiments/stage_01h_viscous_decay_diagnosis/results/stage01h_operator_diagnosis.json`<br>`/classification_evidence/maximum_dt_halving_relative_change` | dt-halving 贡献很小 |
| KF018 | [20, 4, 10, 5, 5] | records/components/train/validation/test | Stage 02J-W | PASS | `stage_02_Particle_Interaction_Operator/05_dataset/blind_multifamily_pair_scope_v1_0/manifests/stage02jw_dataset_manifest.json`<br>`/record_count; /leakage_component_count; /split_counts` | blind multifamily dataset |
| KF019 | [2, 0, 0] | qualified architectures/training runs/optimizer steps | Stage 02K | PASS | `stage_02_Particle_Interaction_Operator/06_model/pair_force_pio_architecture_v0_1/results/stage02k_qualification_summary.json`<br>`/qualified_architecture_count; /training_runs; /optimizer_steps` | 架构资格与学习资格分离 |
| KF020 | 9 | runs | Stage 02M | NOT_QUALIFIED | `stage_02_Particle_Interaction_Operator/06_model/pair_force_pio_static_fitting_v0_1/results/stage02m_qualification_summary.json`<br>`/run_count` | static fitting v0.1 |
| KF021 | [0, 1, 3, 3] | K1 train; K2 train; validation; test pass seeds | Stage 02M-Q | NOT_QUALIFIED | `stage_02_Particle_Interaction_Operator/06_model/pair_force_pio_static_fitting_v0_2/results/stage02mq_qualification_summary.json`<br>`/K1/B_train_fit_pass_seed_count; /K2/B_train_fit_pass_seed_count; /K2/C_validation_transfer_pass_seed_count; /K2/D_test_transfer_pass_seed_count` | v0.2 transfer PASS 不能覆盖 train-fit FAIL |
| KF022 | 0.392220124168075 | m s^-2 | Stage 02M-P/Q | PROJECT_EVIDENCE | `stage_02_Particle_Interaction_Operator/06_model/pair_force_pio_static_fitting_v0_2/results/stage02mq_qualification_summary.json`<br>`/a_sup` | 监督尺度 |
| KF023 | 18 | trajectories | Stage 03B | PASS | `stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03b_trajectory_manifest.json`<br>`/expected_record_count` | D-R1/D-R2/D-R3 trajectory inventory |
| KF024 | [48, 288, 72] | D0 tests; zero-correction tests; structural cases | Stage 03C | PASS | `stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03c_test_manifest.json`<br>`/counts/independent_RK2; /counts/zero_correction; /counts/structural_stage_audits` | 实现、bitwise baseline 与结构测试 |
| KF025 | [360, 216, 144] | required probes; stable windows; failures | Stage 03D | NOT_QUALIFIED | `stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03ds_final_manifest.json`<br>`/evidence_summary/multistep_probes; /evidence_summary/stable_windows; /evidence_summary/failures` | 多步梯度资格 |
| KF026 | [540, 540] | conservation checks/pass | Stage 03D | QUALIFIED_COMPONENT | `stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03d/qualification/stage03d_qualification_summary.json`<br>`/counts/per_stage_conservation_count; /counts/per_stage_conservation_pass_count` | 守恒分量通过 |
| KF027 | [6, 12] | replay pass; fixed-side AD/FD pass | Stage 03D | QUALIFIED_COMPONENT | `stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03d/qualification/stage03d_qualification_summary.json`<br>`/counts/event_replay_pass_count; /counts/fixed_side_event_adfd_pass_count` | TE1 topology component |
| KF028 | [60, 60, 30, 60, 2640, 19] | reverse/JVP passed/required; extended-FD stable/required/paths; unresolved | Stage 03D-R | DIAGNOSTIC | `stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03dr/results/stage03dr_summary.json`<br>`/ad_crosscheck; /extended_fd; /failure_reason_counts/UNRESOLVED` | mixed/unresolved 失败归因 |
| KF029 | [0, 0, 0] | dynamic training; autonomous rollout; full performance evaluations | Stage 02–03 | NOT_EXECUTED | `stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03ds_final_manifest.json`<br>`/evidence_summary/training_runs; /evidence_summary/rollouts; /evidence_summary/performance_evaluations` | 不得改写为 FAIL 或性能结论 |
| KF030 | [0, 6] | history-gradient passes; required rows | Stage 03D | NOT_QUALIFIED | `stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03d/history_gradients/reference_prehistory_results.json`<br>`/history_gradient_pass_count; length(/rows)` | history-gradient audit 0/6 |

## 附录 C：完整来源索引

| 相对路径 | 类型 | 阶段 | 状态 | SHA-256 | 支撑内容 |
|---|---|---|---|---|---|
| project_wide_synthesis/12_reports/project_wide_synthesis_final_report.md | human-readable report | Cross-stage dossier | SOURCE / COMPLETED DOSSIER | 6ee0a400a5f33ef237dd97661e5ddbd59f3c8efd97c81c5c701c4db3d3c18b53 | 跨阶段叙事、证据边界、选项或研究记录交叉核验 |
| project_wide_synthesis/13_manifests/project_wide_synthesis_final_manifest.json | machine JSON / manifest | Cross-stage dossier | SOURCE / COMPLETED DOSSIER | 88b4cfc108bb58cfb0d5452c6d21b78afe8d00079bea1781cb44290e5bb67429 | 跨阶段叙事、证据边界、选项或研究记录交叉核验 |
| project_wide_synthesis/12_reports/project_wide_research_synthesis.md | human-readable report | Cross-stage dossier | SOURCE / COMPLETED DOSSIER | decce15f90f1e8c5acd74a8b0bf34a8d7ef20c72e8233d6676c0c5ab89eb55d2 | 跨阶段叙事、证据边界、选项或研究记录交叉核验 |
| project_wide_synthesis/02_stage_timeline/complete_stage_timeline.json | machine JSON / manifest | Cross-stage dossier | SOURCE / COMPLETED DOSSIER | 54373f683a9c10e726892ff983c1f3b9405bb751c8ea615e28465e0b9a248ba3 | 跨阶段叙事、证据边界、选项或研究记录交叉核验 |
| project_wide_synthesis/03_hypothesis_register/complete_hypothesis_register.json | machine JSON / manifest | Cross-stage dossier | SOURCE / COMPLETED DOSSIER | 1f238987dfe1dc6957ab35477c1bd6c088e074a8d4d1ef81ffbd3c505687a424 | 跨阶段叙事、证据边界、选项或研究记录交叉核验 |
| project_wide_synthesis/04_failure_register/complete_failure_register.json | machine JSON / manifest | Cross-stage dossier | SOURCE / COMPLETED DOSSIER | cc52cea0023dabebe087430bddb49003f4120c5693e38188f6c14a11bbc06fdc | 跨阶段叙事、证据边界、选项或研究记录交叉核验 |
| project_wide_synthesis/04_failure_register/failure_causal_tree.json | machine JSON / manifest | Cross-stage dossier | SOURCE / COMPLETED DOSSIER | 12041a0c963cc2a5f2a7971b7a5fd8b0511f0ecfd2a80f0efd03c98b15df7bb6 | 跨阶段叙事、证据边界、选项或研究记录交叉核验 |
| project_wide_synthesis/05_innovation_register/complete_innovation_register.json | machine JSON / manifest | Cross-stage dossier | SOURCE / COMPLETED DOSSIER | 0a386f961d30f7ea276529efaf4086f236f288ac849ffad4379f35365c80331c | 跨阶段叙事、证据边界、选项或研究记录交叉核验 |
| project_wide_synthesis/05_innovation_register/innovation_evidence_map.json | machine JSON / manifest | Cross-stage dossier | SOURCE / COMPLETED DOSSIER | 681ff3b7cc5d0acab14c39bd8dd38fe5eee79c047add0f7ea0a6ed9b66269801 | 跨阶段叙事、证据边界、选项或研究记录交叉核验 |
| project_wide_synthesis/06_evidence_hierarchy/project_wide_evidence_matrix.json | machine JSON / manifest | Cross-stage dossier | SOURCE / COMPLETED DOSSIER | 8e3fb25efc528667169fb0ad87e194b807bd875a80684936e6b762eee3f78cef | 跨阶段叙事、证据边界、选项或研究记录交叉核验 |
| project_wide_synthesis/07_claim_boundary/project_wide_claim_boundary.json | machine JSON / manifest | Cross-stage dossier | SOURCE / COMPLETED DOSSIER | 1a75f6da594a3ed90d372d122cc1eda72a52a8aa1ecc8e5e0968237c4e328033 | 跨阶段叙事、证据边界、选项或研究记录交叉核验 |
| project_wide_synthesis/12_reports/how_failures_generated_methodological_progress.md | human-readable report | Cross-stage dossier | SOURCE / COMPLETED DOSSIER | f50892d7a99b94934eb805a479edb66f26010f13b976a4c66dbd7190665a87a3 | 跨阶段叙事、证据边界、选项或研究记录交叉核验 |
| project_wide_synthesis/12_reports/project_wide_publication_decision_dossier.md | human-readable report | Cross-stage dossier | SOURCE / COMPLETED DOSSIER | ffb3afb3c7b121e8558d2e4e01e27232672667f501cb3b2184a23b33e1447286 | 跨阶段叙事、证据边界、选项或研究记录交叉核验 |
| project_wide_synthesis/09_publication_options/publication_option_A_single_integrated_paper.md | human-readable report | Cross-stage dossier | SOURCE / COMPLETED DOSSIER | 6e9fecb22fe2c0621913238f18fa8905cdd290a789eb24b93043a081c62373e8 | 跨阶段叙事、证据边界、选项或研究记录交叉核验 |
| project_wide_synthesis/09_publication_options/publication_option_B_two_paper_split.md | human-readable report | Cross-stage dossier | SOURCE / COMPLETED DOSSIER | cd507b6eb801e48495f04266d26053181d58699ca9d944f1158916cb404c11a3 | 跨阶段叙事、证据边界、选项或研究记录交叉核验 |
| project_wide_synthesis/09_publication_options/publication_option_C_verification_only_fallback.md | human-readable report | Cross-stage dossier | SOURCE / COMPLETED DOSSIER | 37ebf6dad84ff37a8f94255a4cbcf6cdf4ac8f40ff607976487dbdfd0690ec96 | 跨阶段叙事、证据边界、选项或研究记录交叉核验 |
| project_wide_synthesis/10_merge_split_decision/post_stage04_merge_split_decision_tree.json | machine JSON / manifest | Cross-stage dossier | SOURCE / COMPLETED DOSSIER | f245104672a2a478f71aef5a1962a615d994d7c03a16771c9b673c46be4090ac | 跨阶段叙事、证据边界、选项或研究记录交叉核验 |
| stage_01_verification/documents/Stage_01_Research_Record.docx | research record DOCX | Stage 01 | SOURCE / COMPLETED DOSSIER | c42f13f04ca5b36d341f54d6eef285285446aad64459c2dca5934dd145c9ef8e | 跨阶段叙事、证据边界、选项或研究记录交叉核验 |
| stage_02_Particle_Interaction_Operator/documents/Stage_02_Research_Record.docx | research record DOCX | Stage 02 | SOURCE / COMPLETED DOSSIER | 5d947e347562cee3c7583d8fd0a16407ac4bf78fafdb4fbc78bbd2c1e708016a | 跨阶段叙事、证据边界、选项或研究记录交叉核验 |
| stage_03_Dynamic_SPH_Transformer_Hybrid/documents/Stage_03_Research_Record.docx | research record DOCX | Stage 03 | SOURCE / COMPLETED DOSSIER | 28afc7ba1061f7a3afbef2a524f24a37efcd87b510620cd98c6fd71787b57f64 | 跨阶段叙事、证据边界、选项或研究记录交叉核验 |
| 07_reports/stage_00_summary.md | human-readable report | Stage 00 | CONDITIONAL | 5b5cb55a885b66e211f29628acef5b0ed2cc1fb379eb01a74313549934cab948 | CPU/MPS操作检查通过；diffSPH仅安装/导入/邻域预检。 |
| 07_reports/stage_01_scope_reclassification.md | human-readable report | Stage 01 | CONDITIONAL PASS (V0 only) | e16fb922e66993057aa5dd7d20f529be8d24ed3ae72d2042a2b53bbbc3611e56 | V0工程可执行；V1部分；V2未完成；V3未开始。 |
| 07_reports/stage_01b_final_vv_report.md | human-readable report | Stage 01B | V1_FAIL | 06e8f848e1a749406fd419d92c54da784ab64c3ec87da2b183ad43f604ca4e95 | kernel/Laplacian/AD及结构门触发停止。 |
| 06_experiments/stage_01c_operator_candidates/results/stage01c_gate_status.txt | machine status text | Stage 01C | C1_PASS_C2_PASS_C3_PASS_C4_PASS | b8ca179abb637e75affaf8010149468eca984e1d21524a9f68b5ed49f107c8d7 | 四项静态重资格门通过。 |
| 06_experiments/stage_01d_fixed_physics_tgv/results/stage01d_v2_status.txt | machine status text | Stage 01D | V2_FAIL | 7bd1685c7a729a27af2b89caf66a1a5fbaecaa951ae47f26406b58636df0dc1e | N32 smoke资源门失败；后续多门NOT_RUN。 |
| 06_experiments/stage_01dr_memory_diagnosis/results/stage01dr_resource_status.txt | machine status text | Stage 01DR | RESOURCE_FAIL_LINEAR_GROWTH | 11935afa1196493662fb86c9c037d21cf7ba7e883370aa274ef56d02f8109e8f | 资源重资格仍失败。 |
| 06_experiments/stage_01dr2_storage_attribution/results/stage01dr2_attribution_status.txt | machine status text | Stage 01DR2 | ATTRIBUTION_UNRESOLVED | 685009884205f96255875045c59380437b4d3b2c8b12036d11c29344bb433ab9 | storage归因未唯一解析。 |
| 06_experiments/stage_01dr3_topology_confirmation/results/stage01dr3_status.txt | machine status text | Stage 01DR3 | R3_CONFIRMATION_UNRESOLVED | adb879f5b9099c7ff59f7862e5da4f4782cbd6d0fc565dfb74414273902610bb | 证据仍未解析。 |
| 06_experiments/stage_01dr4_weakref_semantics/results/stage01dr4_status.txt | machine status text | Stage 01DR4 | R4_RETENTION_REDETECTED | 737e6a0d9db70184e0cac35dc6cb2e1c445ef0ad42e11601fbfbbc93bef15df3 | retention被重新检测。 |
| 06_experiments/stage_01dr5_gc_cycle_localization/results/stage01dr5_status.txt | machine status text | Stage 01DR5 | R5_BOUNDED_GC_DELAY_CONFIRMED | 2d69c898fc0d42618b605d2bcf4a47d39715e981336e15313a586319aee3b3f7 | GC-disabled线性；default-GC 2000步有界。 |
| 06_experiments/stage_01dp_resource_policy/results/stage01dp_status.txt | machine status text | Stage 01DP | POLICY_PASS_ISOLATED_DEFAULT_GC | 0ca7cdd036635e044a828afe6100b5af1d28db5177bdb2ad26444c9419b4667f | 3/3 canary通过；政策资格化。 |
| 06_experiments/stage_01d2_v2_requalification/results/stage01d2_evaluation.json | machine JSON / manifest | Stage 01D2 | STAGE01D2_V2_REQUALIFICATION_FAIL | e6f1cb6e7bcd9cdebb628e0196c3dd99a0314efe219bcff5f176f2fff3f3f8ab | 时间可解释，但空间非单调、jitter/资源门失败。 |
| 06_experiments/stage_01e_error_decomposition/results/stage01e_evaluation.json | machine JSON / manifest | Stage 01E | E_MODEL_FORM_ALIGNMENT_DOMINANT | 0b4e81ad673c9367e038327efd98045f39abd933226bb7368fa1343fb6dbc225 | EOS初始化残差主导；两项渐近拟合不可识别。 |
| 06_experiments/stage_01f_mms_design/results/stage01f_evaluation.json | machine JSON / manifest | Stage 01F | MMS_SPECIFICATION_PASS | 544b22e885ca8cf34a59006ff5123136c68131452b3e183b68c65ed3899f55ad | MMS规格通过。 |
| 06_experiments/stage_01f2_mms_implementation/results/stage01f2_evaluation_v2.json | machine JSON / manifest | Stage 01F2 | MMS_IMPLEMENTATION_VERIFIED_PASS | 8bf690e614a235cee9e66962969c56f676afac4b5cc8dab79e79a2dd74d16922 | 实现验证通过。 |
| 06_experiments/stage_01f3_mms_convergence/results/stage01f3_evaluation.json | machine JSON / manifest | Stage 01F3 | MMS_CONVERGENCE_VERIFICATION_FAIL | ee2be10daaaba6f8b9b8a3698254cce80992646e750d90ee312948152489c982 | reference/topology identity硬门前停止或收敛门失败。 |
| 06_experiments/stage_01f3r_reference_qualification/results/stage01f3r_evaluation.json | machine JSON / manifest | Stage 01F3R | SEMIDISCRETE_REFERENCE_QUALIFIED_DENSE_EQUIVALENT | 6364c022f38aa40acd384ce933488037802f383aa61d1e2f34f811f13ea9b260 | reference资格化。 |
| 06_experiments/stage_01f3b_mms_convergence/results/stage01f3b_evaluation.json | machine JSON / manifest | Stage 01F3B | MMS_CONVERGENCE_VERIFICATION_FAIL | 1834e3ac2b735f7baea7a8cff0de7c4d0f4e9287bef79ae2054524bf306c1032 | 仍为收敛资格失败；GCI不成立。 |
| 06_experiments/stage_01f3c_ct2_adjudication/results/stage01f3c_evaluation.json | machine JSON / manifest | Stage 01F3C | CT2_MIXED_OR_UNRESOLVED | 94f65147edda831bf50feae25b19ce02bfd9619026859ec438a64ee783609d1c | 时间阶接近2但抵消门失败，混合/未解析。 |
| 06_experiments/stage_01f4_protocol_adjudication/results/stage01f4_evaluation.json | machine JSON / manifest | Stage 01F4 | PLATEAU_AWARE_PROTOCOL_APPROVED | 0eb8df3703d6d9c52b36b05b344f9820cbc3f379aac07b663a4d7f641bd13e49 | 新协议批准；旧失败保持。 |
| 06_experiments/stage_01f5_requalification_design/results/stage01f5_evaluation.json | machine JSON / manifest | Stage 01F5 | PLATEAU_AWARE_REQUALIFICATION_DESIGN_APPROVED | e13cff6cf3439f9bbb66d0c8a4584f303eac5f8813bbf7ce9f968b017ae4c251 | 设计批准。 |
| 06_experiments/stage_01f5p_branch_completeness/results/stage01f5p_evaluation.json | machine JSON / manifest | Stage 01F5P | EXECUTION_MANIFEST_INCOMPLETE | 8e104f5ef0782fdfefae8ac09526a8553832cbf5fbaa6fb0b2aa50abc65fd52b | 执行清单不完整。 |
| 06_experiments/stage_01f5q_space_horizon_amendment/results/stage01f5q_evaluation.json | machine JSON / manifest | Stage 01F5Q | FORMAL_SPACE_EXECUTION_BUNDLE_READY | f51ce237011b3af2e96ffc030a4cd6cf38982278bc166f506b42a60136e88e3d | 正式执行bundle就绪。 |
| 06_experiments/stage_01f5b_requalification_execution/results/stage01f5b_evaluation.json | machine JSON / manifest | Stage 01F5B | PLATEAU_AWARE_MMS_REQUALIFICATION_PASS | 4b3eec7d6283049c9873bb2e8416adb734442bdc77fa3c2cf97fabf89dbeea32 | 一次性重资格通过；基础设施retry单独保留。 |
| 06_experiments/stage_01g_validation_design/results/stage01g_design_evaluation.json | machine JSON / manifest | Stage 01G | INDEPENDENT_VALIDATION_AND_V2_DESIGN_APPROVED | 24d3af87fd4c95870fcc26cd59cd0a72e98ebacedca24ff874b9dcdf3bf5d981 | 设计通过但未执行。 |
| 06_experiments/stage_01gp_preexecution_audit/results/stage01gp_evaluation.json | machine JSON / manifest | Stage 01GP | INDEPENDENT_VALIDATION_EXECUTION_READY | 5040409add4487fc5a12f5c27ae736f6a1e34f716c49d4c479d582bd975741ad | preexecution audit通过。 |
| 06_experiments/stage_01ge_evaluator_qualification/results/stage01ge_evaluation.json | machine JSON / manifest | Stage 01GE | INDEPENDENT_VALIDATION_EVALUATOR_READY | 8563924af367f7a2c456c542c6c6528767fd26921e47ebd31c70cdbf254936fa | evaluator就绪。 |
| 06_experiments/stage_01g_execution_preflight_v2/results/stage01gv2_evaluation.json | machine JSON / manifest | Stage 01G | INDEPENDENT_VALIDATION_EXECUTION_AUTHORIZED | 48fb4ef3ff58ab0520159dcd5bf9c2855526ec6df90ed3ead43b7a2aa1f27d8a | 执行获授权；未生成V2状态。 |
| 06_experiments/stage_01gr_execution_infrastructure_repair/results/stage01gr_evaluation.json | machine JSON / manifest | Stage 01GR | EXECUTION_INFRA_READY_FOR_BENCHMARK | 55dfdc617e5f6ba5ed1fa911315ab12a664259ef3c102e4cd0c0132968608c95 | 修复后基础设施就绪。 |
| 06_experiments/stage_01g_validation_execution/results/stage01g_evaluation_reapplication_01.json | machine JSON / manifest | Stage 01G | V2_QUALIFICATION_FAIL | 021676f88cb1d251e280f18b1eac58a4aa0447980b4249920df3722cbb64c45f | acoustic通过；shear N48门失败；V2失败。 |
| 06_experiments/stage_01h_viscous_decay_diagnosis/results/stage01h_evaluation.json | machine JSON / manifest | Stage 01H | VISCOSITY_DIAGNOSIS_COMPLETE | 6c40c9e95a65983c7dfb4c6e9afa5b64266a106cd4847fd54c1b8c2a383b838c | 分类FINITE_RESOLUTION_DOMINANT；算子形式失败未确认。 |
| stage_02_Particle_Interaction_Operator/07_reports/stage02a_pio_theory_report.md | human-readable report | Stage 02 | PIO_THEORY_QUALIFICATION_COMPLETE | 893c2d5741e174cf2514112e8d872eaaa6b59957ba2696445a4b24e5ac2d80c5 | 理论合同完整；未生成数据或模型。 |
| stage_02_Particle_Interaction_Operator/07_reports/stage02b_final_report.md | human-readable report | Stage 02 | DATASET_QUALIFICATION_COMPLETE | 08c5d063534cc01bf79b18c68da4f285da687b448e4db460c4b6c4e5b06302e8 | 数据资格协议与 schema 完成。 |
| stage_02_Particle_Interaction_Operator/07_reports/stage02c_final_report.md | human-readable report | Stage 02 | DATASET_GENERATION_AUDIT_COMPLETE | 1e330a51b545fbaaebb4188d20e08c396f7b18e3637979ec85eb849778f1fd5f | 3 reference records、6 samples；4 diagnostic、2 topology rejected。 |
| stage_02_Particle_Interaction_Operator/07_reports/stage02d_final_report.md | human-readable report | Stage 02 | TARGET_ATTRIBUTION_QUALIFICATION_COMPLETE | d52f03a026ee936d91c3e3dd9d3825981e45cc0a0cf792154ded680f48a31ac8 | 6/6 完成分解；4 diagnostic、2 rejected。 |
| stage_02_Particle_Interaction_Operator/07_reports/stage02e_final_report.md | human-readable report | Stage 02 | TARGET_CONSTRUCTION_COMPLETE | 18d8e327da81633801a9c668c460c8e0547f4b754ad0b8f552a943cbcc02317a | 8/8 非零且 reference audit 完整。 |
| stage_02_Particle_Interaction_Operator/07_reports/stage02f_final_report.md | human-readable report | Stage 02 | SPATIAL_TARGET_QUALIFICATION_COMPLETE | 8fe0235718ae56c5c5a32905bc6e3e77de04a377320c9bc83b9e20825a174b0b | 5 个非零 same-state spatial candidates；support 与 reference gates 完成。 |
| stage_02_Particle_Interaction_Operator/07_reports/stage02g_final_report.md | human-readable report | Stage 02 | SPATIAL_ATTRIBUTION_CLOSURE_COMPLETE | 6031fe8233397aeca3d51abd818334bbe141f43c1a028e997f5847cafeba4e9e | R2S bias、refinement、4/6 attribution 完整。 |
| stage_02_Particle_Interaction_Operator/07_reports/stage02h_final_report.md | human-readable report | Stage 02 | REFERENCE_FIDELITY_QUALIFICATION_COMPLETE | d0086d056b1e7f47fe4e2ed310b84a508c3832c79747160b42b0689aaa583ccc | Fourier 与 analytic 在受控 periodic-vortex scope 内独立一致并 PASS。 |
| stage_02_Particle_Interaction_Operator/07_reports/stage02i_final_report.md | human-readable report | Stage 02 | QUALIFIED_SPATIAL_TARGET_POOL_NOT_READY | 2fdd1d45b81b074d2f2a1ff49a60c77d0a131c1b542923d6ed4f9e2111ddf89d | 7/7 six-component attribution PASS；5 pair-compatible、2 node-residual-only。 |
| stage_02_Particle_Interaction_Operator/07_reports/stage02ir_final_report.md | human-readable report | Stage 02 | CONSERVATION_COMPATIBILITY_RESOLVED_PAIR_ONLY | cdf34e6d282f5bad84af9b6d94f015c8bdcabd601738681729597e61611784f6 | 五个 regular targets 确认 pair-only；jitter 保留诊断。 |
| stage_02_Particle_Interaction_Operator/07_reports/stage02j_final_report.md | human-readable report | Stage 02 | CONTROLLED_REGULAR_DATASET_NOT_READY | 3f36ab2851890fd554c52460768248229788609369a75096b3f7d02e31f8b8de | 5 records schema/canonical/QC 完整。 |
| stage_02_Particle_Interaction_Operator/07_reports/stage02jr_final_report.md | human-readable report | Stage 02 | MULTIFAMILY_CONTROLLED_DATASET_NOT_READY | 5e5ad48cfdd12018135a6ec268336a7274b618527f8960554ad7d170d0ffd18f | 15 candidates reference/conservation PASS，lineages 分离。 |
| stage_02_Particle_Interaction_Operator/07_reports/stage02js_final_report.md | human-readable report | Stage 02 | VERSIONED_MULTIFAMILY_DATASET_NOT_READY | 27061a9b075d71e815695bc3fd56b6f0cf9f835b78a3f186edd3f4647a4e40b7 | structured development paths PASS；80 invariance checks PASS。 |
| stage_02_Particle_Interaction_Operator/07_reports/stage02jt_final_report.md | human-readable report | Stage 02 | REGULARITY_GATE_V03_NOT_QUALIFIED | de34f2b6ac4ba2d27da4a72339c3dadba907ba6540fbc5051a6b5e4e54f0a787 | 30 control combinations与 invariance 完成。 |
| stage_02_Particle_Interaction_Operator/07_reports/stage02jv_final_report.md | human-readable report | Stage 02 | REGULARITY_HARD_GATE_ROUTE_TERMINATED | 1f6bf082a95ace38f47f6f74ccd9c115173024ef7014b17b0fa54e7a9d03287a | positive/hard-negative controls 与 real targets 完整。 |
| stage_02_Particle_Interaction_Operator/07_reports/stage02jw_final_report.md | human-readable report | Stage 02 | BLIND_MULTIFAMILY_DATASET_READY | a35161d0fcf8ac43edd21694414f2778936165b589cd21e5205483e042d67c83 | 20/20 reference/target/conservation/QC PASS；4 lineage components；10/5/5 split；train-only normalization。 |
| stage_02_Particle_Interaction_Operator/07_reports/stage02k_final_report.md | human-readable report | Stage 02 | PAIR_FORCE_PIO_ARCHITECTURE_QUALIFIED | bc713e08c3b3f0bd34e50fb3b296a9dd5f0db4540cf4b5392336e6a41887de15 | K1/K2 antisymmetry、momentum、O(2)、periodicity、differentiability、O(E d) PASS。 |
| stage_02_Particle_Interaction_Operator/07_reports/stage02l_final_report.md | human-readable report | Stage 02 | STATIC_FITTING_PROTOCOL_READY | 3f31a94d4de2bafdd09f2f1bc8375a042cdb33e8a7a34ee8f6ca42322e526eaf | 协议、loss、optimizer、checkpoint、test seal 完整。 |
| stage_02_Particle_Interaction_Operator/07_reports/stage02m_final_report.md | human-readable report | Stage 02 | STATIC_PAIR_FORCE_FITTING_NOT_QUALIFIED | 888d128a2208a7ac041df5174362790c9602e74b24ea8f7abd113755af0ccba4 | 9/9 runs、sealed test、postfit、resources 完整。 |
| stage_02_Particle_Interaction_Operator/07_reports/stage02mr_final_report.md | human-readable report | Stage 02 | STATIC_FITTING_FAILURE_ATTRIBUTED_OPTIMIZATION_CONDITIONING | 8dc07f364d91bb730f1687fe49b21c4226399ef9c42f00a8203ad6c9c82917dc | loss scale、Adam epsilon/weight decay、梯度/更新尺度证据一致。 |
| stage_02_Particle_Interaction_Operator/07_reports/stage02mp_final_report.md | human-readable report | Stage 02 | STATIC_FITTING_PROTOCOL_V02_READY | e1db308805e5f698acfbfa13800a806509816ad9537590c751d7bb85f2229f5a | v0.2 protocol、a_sup、9-run matrix、v1.1 collection、test seal READY。 |
| stage_02_Particle_Interaction_Operator/07_reports/stage02mq_final_report.md | human-readable report | Stage 02 | STATIC_PAIR_FORCE_FITTING_V02_NOT_QUALIFIED | a21a184bb59c25b31bb0487251b9be109158fe5434e8c00cd064d13794ac3c36 | 9/9 conditioning/terminal/closure/test/postfit/resource evidence完整；C/D/E gates PASS。 |
| stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03a_final_manifest.json | machine JSON / manifest | Stage 03 | DYNAMIC_HYBRID_SOLVER_SPECIFICATION_COMPLETE | d4ed848abd0ab4b48449228d2c43b6b3464f076d613c4ddc825dfa6cb4ec492c | 45/45 contract hash checks；20/20 historical freeze checks；55/55 required files。 |
| stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03b_final_manifest.json | machine JSON / manifest | Stage 03 | DYNAMIC_REFERENCE_TRAJECTORY_QUALIFICATION_COMPLETE | c3bef0df24f373fe2eff33b0cfeb078768ebd502227a725b9911470306c86f41 | D-R1 两族、D-R2 六例、D-R3 两族 PASS；18/18 canonical trajectories；4302 RHS/rebuilds。 |
| stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03c_final_manifest.json | machine JSON / manifest | Stage 03 | DYNAMIC_RK2_HYBRID_IMPLEMENTATION_VERIFIED | bf5e0e3f1ac68e4b2df8ed847a1cf9a0cb0290c158b3813b1d4fa65a74abb5af | D0 48/48；zero correction 288/288 bitwise；checkpoint 6/6；one-step autograd 6/6；全部结构/资源门 PASS。 |
| stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03d_final_manifest.json | machine JSON / manifest | Stage 03 | DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED | c0862a16d0a43e283e80df2edc08cd6123b18f16bdcea6645564ea99146b32f3 | 216/360 stable windows；540/540 stage conservation；TE1 birth/death、6/6 replay、12/12 event-side gradients PASS。 |
| stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03dr_final_manifest.json | machine JSON / manifest | Stage 03 | DYNAMIC_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED | ad5ef80137ec6aa2e27b22cb51c46bc0f79629ae7c392d9a6f6cd6a6e493bb21 | reverse/JVP 60/60；extended FD 2640 paths、30/60 stable；90 个 horizon 均 bounded/nonmonotone；topology status preserved。 |
| stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03ds_final_manifest.json | machine JSON / manifest | Stage 03 | STAGE03_ROUTE_PAUSED_GRADIENT_BOUNDARY_COMPLETE | f13c6adfac8f83b7a0b009c9c7f052a685d446294d9fff01c27683c18239807d | 路线暂停；Stage03E=false。 |
| 06_experiments/stage_01dp_resource_policy/results/analysis_summary.json | machine JSON / manifest | Stage 01DP | SOURCE / COMPLETED DOSSIER | 16049e8ddb4c68b8dd4c90d8e2a2506f6cdba1acbbaac1563c340b864fe85809 | 跨阶段叙事、证据边界、选项或研究记录交叉核验 |
| 06_experiments/stage_01dp_resource_policy/results/campaign_summary.json | machine JSON / manifest | Stage 01DP | SOURCE / COMPLETED DOSSIER | 10758f6ec3c7d6d4ae63f40b07f9fcab0ffa54a864db3b595cb2997abad3558f | 跨阶段叙事、证据边界、选项或研究记录交叉核验 |
| 06_experiments/stage_01g_validation_execution/results/stage01g_shear_gates_reapplication_01.json | machine JSON / manifest | Stage 01G | SOURCE / COMPLETED DOSSIER | e162c2bf2ae31dbd87c2ee5048a538efa6e22362f81192dcc6b2502c940add61 | 跨阶段叙事、证据边界、选项或研究记录交叉核验 |
| 06_experiments/stage_01h_viscous_decay_diagnosis/results/stage01h_operator_diagnosis.json | machine JSON / manifest | Stage 01H | SOURCE / COMPLETED DOSSIER | df5eae9b4be6ac98447f4ef6f8c152c122e050e164ef751379a6c82ff7da5ddf | 跨阶段叙事、证据边界、选项或研究记录交叉核验 |
| stage_02_Particle_Interaction_Operator/05_dataset/blind_multifamily_pair_scope_v1_0/manifests/stage02jw_dataset_manifest.json | machine JSON / manifest | Stage 02 | SOURCE / COMPLETED DOSSIER | 902154cdd2aff77ecdfb0fc853f7d8b7befb515a891adfc2701dfd895edf90ce | 跨阶段叙事、证据边界、选项或研究记录交叉核验 |
| stage_02_Particle_Interaction_Operator/06_model/pair_force_pio_architecture_v0_1/results/stage02k_qualification_summary.json | machine JSON / manifest | Stage 02 | SOURCE / COMPLETED DOSSIER | 75dea2a8e4ae90d200b202f0f43b075d4ae2700de5ceb60f66c43e44cdc06eef | 跨阶段叙事、证据边界、选项或研究记录交叉核验 |
| stage_02_Particle_Interaction_Operator/06_model/pair_force_pio_static_fitting_v0_1/results/stage02m_qualification_summary.json | machine JSON / manifest | Stage 02 | SOURCE / COMPLETED DOSSIER | 8b3113fec5f890a58e97fd4416a47438be27c726e23a89a859f4dfa1dde878c0 | 跨阶段叙事、证据边界、选项或研究记录交叉核验 |
| stage_02_Particle_Interaction_Operator/06_model/pair_force_pio_static_fitting_v0_2/results/stage02mq_qualification_summary.json | machine JSON / manifest | Stage 02 | SOURCE / COMPLETED DOSSIER | ad8ed993759afb3ce0037988129d119b9d3b3a82865fa98647510be0c28e4f29 | 跨阶段叙事、证据边界、选项或研究记录交叉核验 |
| stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03b_trajectory_manifest.json | machine JSON / manifest | Stage 03 | SOURCE / COMPLETED DOSSIER | 92974b660461a01ba1a326be8b2fedc31929a319aa97e2f5bc3418bd45435aac | 跨阶段叙事、证据边界、选项或研究记录交叉核验 |
| stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03c_test_manifest.json | machine JSON / manifest | Stage 03 | SOURCE / COMPLETED DOSSIER | 57530669791188ddeef66f77fb7683675643b15edd207a0d4c3994a279429133 | 跨阶段叙事、证据边界、选项或研究记录交叉核验 |
| stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03d/qualification/stage03d_qualification_summary.json | machine JSON / manifest | Stage 03 | SOURCE / COMPLETED DOSSIER | 08fb6260b6963daefaf3262c3c7ca54b3ccb7cac6e9b1f7f8ee5deb164ab70e7 | 跨阶段叙事、证据边界、选项或研究记录交叉核验 |
| stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03dr/results/stage03dr_summary.json | machine JSON / manifest | Stage 03 | SOURCE / COMPLETED DOSSIER | 7cbb89e4ea568ad3407c7dc9d56ae7c6b395c28d7c16c6e7c500b5cfa9b6c2e2 | 跨阶段叙事、证据边界、选项或研究记录交叉核验 |
| stage_03_Dynamic_SPH_Transformer_Hybrid/05_dynamic_solver_implementation/stage03d/history_gradients/reference_prehistory_results.json | machine JSON / manifest | Stage 03 | SOURCE / COMPLETED DOSSIER | b5be39b2bdd9a796c667da41c23b08eafd545615d811f981db5c91ff13665415 | 跨阶段叙事、证据边界、选项或研究记录交叉核验 |
