# Stage 02 Research Plan — Particle Interaction Operator

**阶段状态：Preparation / Initialization only**  
**冻结日期：2026-08-04**  
**当前执行边界：仅研究计划、数学表述草案、Stage 01 知识迁移与数据集设计；不执行训练或数值数据生成。**

## 1. 研究定位

Stage 02 的目标不是替代 SPH 求解器，也不是学习一个脱离守恒结构的端到端流场预测器。SPH 继续承担状态推进、邻域构造、密度/EOS、压力、黏性和时间积分等物理计算。Particle Interaction Operator（PIO）只研究一个附加的粒子相互作用修正算子，用于估计冻结 SPH 离散在给定粒子状态上的加速度误差。

基线 SPH 加速度定义为

\[
\mathbf a_{\mathrm{SPH},i}=\mathcal A_{\mathrm{SPH}}(\mathcal S,\mathcal G)_i,
\]

参考加速度定义为

\[
\mathbf a_{\mathrm{ref},i}=\mathcal A_{\mathrm{ref}}(\mathcal S)_i,
\]

学习目标冻结为

\[
\Delta\mathbf a_i=\mathbf a_{\mathrm{ref},i}-\mathbf a_{\mathrm{SPH},i}.
\]

未来的 Transformer / PIO 学习映射为

\[
\widehat{\Delta\mathbf a}_i=\mathcal C_\theta(\mathcal S,\mathcal G)_i,
\qquad
\mathbf a_{\mathrm{corr},i}=\mathbf a_{\mathrm{SPH},i}+\widehat{\Delta\mathbf a}_i.
\]

其中 \(\mathcal S\) 是同一物理时刻的粒子状态，\(\mathcal G\) 是由冻结 SPH 邻域规则得到的粒子相互作用图。当前阶段不定义可执行网络，也不估计参数 \(\theta\)。

## 2. 核心科学问题

1. 在不破坏 SPH 基线可解释性和可回退性的前提下，局部粒子邻域能否预测加速度离散误差？
2. 修正是否可在粒子置换、周期平移及坐标旋转下保持一致或等变？
3. 修正是否可用 pairwise antisymmetry 或显式投影维持总内力守恒？
4. 在规则、轻度无序、不同分辨率和不同支撑尺度之间，修正能否泛化，而不是记忆单条轨迹或单一网格？
5. 如何区分离散误差、时间积分误差、参考误差和连续模型不一致，避免把不可归因误差错误地写入标签？

## 3. 冻结研究假设

- H1：在光滑、低马赫、周期、弱可压缩的已验证范围内，主要离散误差包含可由有限邻域状态解释的局部成分。
- H2：把输出限制为基线加速度的残差修正，比直接预测全加速度更利于保持物理基线、可审计性和零修正回退。
- H3：pairwise 消息与反对称力参数化能够在表达能力和线动量守恒之间建立可验证约束。
- H4：若训练/验证切分以整条轨迹、初始化族和分辨率族为单位，可显著降低时序相邻样本泄漏。
- H5：只有参考不确定性显著小于 \(\|\Delta\mathbf a\|\) 的样本才具备标签资格。

这些是假设而非结论；Stage 02 preparation phase 不验证它们。

## 4. 研究范围

### 4.1 当前允许范围

- 冻结研究问题、符号、目标与不变量；
- 起草 PIO 数学表述；
- 汇总 Stage 01 可迁移知识与失败约束；
- 设计未来数据结构、标签合同、切分策略和质量门；
- 定义未来阶段的准入条件，但不触发后续阶段。

### 4.2 当前禁止范围

- training；
- dataset generation 或任何标签物化；
- Transformer、attention、MLP 或其他模型实现；
- parameter tuning 或超参数搜索；
- benchmark modification；
- 修改任何 Stage 01 结果、报告、标签、阈值或状态；
- 修改或重新解释冻结的 V2 FAIL；
- 运行 SPH、RK2、DOP853、MMS、shear 或 acoustic 数值矩阵。

## 5. 工作包与后续门控

### WP0 — Initialization（本次完成）

产物：研究计划、PIO 数学表述草案、Stage 01 知识迁移、数据集设计、独立目录结构。准入判据是所有文件隔离、Stage 01 只读、无训练和无数据生成。

### WP1 — Theory qualification（未来，未授权）

需冻结参考加速度定义、pairwise 守恒形式、对称性/等变性合同、可辨识性和误差分解。不得编写训练代码。

### WP2 — Dataset protocol qualification（未来，未授权）

需冻结教师/参考来源、样本矩阵、分割单位、参考不确定性门、源代码和配置身份。完成协议不等于允许生成数据。

### WP3 — Dataset generation（未来，未授权）

只有 WP1/WP2 分别通过后才可另行申请。必须一次性运行、保留失败样本状态，并确保基线和参考在同一粒子状态上评价。

### WP4 — Model implementation and training（未来，未授权）

必须在数据集质量审计通过后另行申请。模型实现、训练、调参和性能比较均不属于当前阶段。

## 6. 成功标准与失败标准

未来科学成功至少需要同时满足：校正后加速度误差下降；未见分辨率/布局泄漏；守恒和对称性门通过；独立 benchmark 上不劣化；资源与确定性合格；报告参考和标签不确定性。

以下任一情况均应判定失败或证据不完整：参考误差与标签同量级；训练/验证共享轨迹片段；校正依赖粒子索引；守恒残差显著恶化；只在训练分辨率有效；通过修改 benchmark 或 Stage 01 阈值得到表面改善；缺少失败样本或 provenance。

## 7. 风险登记

- **模型形式混入标签**：连续参考与 WCSPH 基线不一致时，差值不再是纯离散误差。应由标签资格门排除或单独分类。
- **空间平台误判为时间误差**：应在半离散参考或严格时间步隔离下构造标签。
- **拓扑不连续**：cutoff crossing 合法但会造成消息集合变化；需记录事件并检查结构缺陷，而非强制 edge identity 恒定。
- **无序分布偏移**：规则与 jitter 数据须按布局族分层，并保留整族 held-out。
- **参考 inverse crime**：参考不能调用待评估 PIO，也不能用校正后残差回灌标签。
- **资源放大**：邻域 Transformer 的复杂度与边数相关；未来必须在模型执行前冻结粒子数、邻居数和内存停止线。

## 8. 预期论文贡献边界

若后续证据支持，本阶段研究可以贡献：一种不替代 SPH 的 residual particle-interaction correction formulation；一个带参考不确定性和防泄漏合同的数据协议；一套守恒、对称性、泛化和独立验证门。当前仅完成研究框架，不能声称精度提升、泛化能力或模型有效性。

## 9. 当前唯一状态

`STAGE02_INITIALIZATION_COMPLETE`

该状态仅表示目录和准备文档完整、Stage 01 历史状态保持、且未执行训练或数据生成；它不是 PIO 理论、数据集或模型资格。
