# PIO Reference Hierarchy 合同

## 1. 总则

Reference class 是每个候选 \(a_{\mathrm{ref}}\) 的必填身份，不是质量排名。不同层级回答不同问题，不能混合成
无类别标签池，也不能因数值更精细就默认具有训练资格。

## 2. 冻结层级

| 类别 | 定义与来源 | 允许用途 | 训练标签地位 | 必要资格检查 |
|---|---|---|---|---|
| R1 `continuum_compatible` | analytic solution 或 MMS；连续方程、EOS、forcing 与冻结 WCSPH 合同可对齐 | verification；在严格归因后形成候选空间离散目标 | 条件性候选，不自动合格 | model-form alignment、同状态评价、forcing/time/reference uncertainty |
| R2 `semidiscrete_qualified` | qualified high-order temporal reference；沿冻结半离散系统提供时间基准 | 隔离时间误差、状态漂移与空间平台 | 默认用于误差分解；不自动产生空间修正标签 | RHS/状态/config identity、时间收敛与 reference uncertainty |
| R3 `independent_benchmark` | 与 MMS/训练构造隔离的 shear/acoustic benchmark 或独立证据 | validation、短 rollout 与外部科学检查 | 默认禁止训练；任何例外需新阶段显式批准且另留独立 benchmark | independence、provenance、未见参数/分辨率、资源与确定性 |
| RX `model_form_misaligned` | continuous model 与冻结 SPH contract 不一致 | diagnostic only | 硬禁止 | 标记具体不一致来源并防止进入标签集合 |

## 3. R1 的 WCSPH 对齐问题

解析解或 MMS 只有在连续闭合与冻结 weakly-compressible/EOS 路线一致时，才可支持 discretization
归因。Stage 01E 已表明不可压 TGV exact field 与冻结 WCSPH 路线可能模型形式不对齐；因此“解析”不等于
“可训练”。无法证明对齐时必须分类 RX，而不是降低 uncertainty 后继续使用。

## 4. R2 的作用边界

R2 的核心作用是把时间推进误差从空间/粒子离散问题中分离。若 R2 使用相同的瞬时半离散 RHS，
它并不会凭自身生成不同的瞬时空间加速度真值；其价值在于产生 qualified state/time reference 和误差界。
任何从 trajectory 差异推回加速度的操作都需要独立的可识别性证明。

## 5. R3 的独立性

Stage 01G 的 acoustic 通过与 shear 失败是独立验证事实，不是标签授权。Shear/acoustic 数据、初始化族、
参数范围或衍生统计不得默认进入训练。未来若改变其独立地位，必须预先冻结新的 held-out 独立 benchmark，
且不得改写 Stage 01G 的 `V2_QUALIFICATION_FAIL`。

## 6. 冲突解决与升级规则

- 类别由 model-form 与生成机制决定，不由误差大小决定；
- 同一 reference 可在不同配置下具有不同类别，类别必须逐 configuration 记录；
- R1/R2 证据冲突时，不选择“更有利”的结果；候选标签降级为 unresolved；
- RX 不能通过统计过滤升级为 R1；必须先修复/证明模型形式对齐并生成新的 provenance；
- R3 默认隔离规则的例外属于未来范围变更，Stage 02A 不授权。
