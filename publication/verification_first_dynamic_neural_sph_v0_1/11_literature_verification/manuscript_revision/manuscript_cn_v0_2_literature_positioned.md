# 守恒型动态神经–SPH耦合的验证优先资格：零修正、拓扑事件与多步梯度边界

英文工作标题：Verification-first development of a conservative dynamic neural–SPH solver: zero-correction equivalence, topology events, and limits of multistep gradient qualification

P2中文稿 v0.2｜Literature-positioned verification manuscript｜非投稿定稿

## 摘要

动态神经–SPH耦合把时间积分、动态图重建、历史状态提交和多步自动微分置于同一计算链。已发表研究已覆盖learnable SPH、Neural SPH、可微SPH、solver-in-the-loop和硬守恒粒子网络 [V001,V002,V003,V004,V022,V028]；因此，本文不以SPH–ML结合或可微实现本身作为新颖性，而定位于verification-first资格合同。我们构建D0基线、D1瞬时MLP、D2循环模型与D3因果时间注意力模型的统一动态框架，并审计动态参考、独立RK2、zero correction、反对称reciprocal pair-force、多步AD/FD与确定性拓扑事件。独立RK2的48/48检查、zero correction的288/288 bitwise等价、结构smoke的72/72、checkpoint/resume的6/6与one-step autograd的6/6均通过；冻结多阶段测试中540/540守恒检查通过。完整360-probe矩阵中216个probe获得stable AD/FD window，144个失败，history门为0/6。因此Stage 03D保持`DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED`。TE1记录一次edge birth与一次death，6/6 replay和12/12 event-side gradients通过，但cutoff edge membership仍为离散事件。本文没有执行动态训练、自主rollout或性能验证。结果支持一种有限定位：在当前已核验文献集合内，zero fallback、多步stable-window与topology-event联合审计仍存在方法学证据空缺；该结论不等同于首次性声明。 <!-- CLAIM:C07,C08,C09,C10,C11,C13,C15,C20,C21,C22,C23,C26,C27 -->

## 关键词

光滑粒子流体动力学；物理机器学习；验证与确认；守恒型神经修正；多步可微性；拓扑事件；负证据

# 1. 引言

## 1.1 SPH的数值背景与学习型粒子求解器

光滑粒子流体动力学（SPH）以随体粒子和紧支核近似连续介质方程，适合自由表面、大变形和复杂耦合，但其误差与收敛同时受核一致性、邻域尺度、粒子分布、边界、耗散项和时间步约束影响；相关综述与验证研究持续把一致性、收敛、稳定性和边界条件列为核心问题 [V042,V056,V058,V076,V018]。因此，SPH benchmark的通过不自动等同于代码验证、解验证或面向应用的物理确认。

学习型Lagrangian模拟器已从连续卷积、动态图消息传递和多尺度交互发展为可进行自回归rollout的粒子代理 [V010,V011,V013,V021,V024]。这些方法通常把传统模拟器作为数据源，并由网络直接预测粒子更新；它们应与“保留SPH时间推进、只学习局部修正”的hybrid correction严格区分。Neural SPH在完全学习GNN的训练与推理阶段加入压力、黏性和外力等SPH分量 [V003]；另一条路线则直接参数化SPH项或平滑核 [V001]。这两类工作均说明“SPH与学习结合”本身不是本文可主张的新颖点。

## 1.2 保守/等变架构与直接竞争工作

几何等变网络可把平移、旋转或反射对称编码进消息传递，但等变性并不自动等于线动量、角动量或能量守恒 [V017,V023]。面向粒子流体，反对称连续卷积已经被用于硬保证线动量 [V022]；面向6-DoF多体系统，DYNAMI-CAL GRAPHNET进一步以edge-local反对称参考框架同时保持线动量与角动量 [V028]。这些工作构成本稿reciprocal pair-force的直接方法比较，也要求本文避免把soft loss、equivariance与hard conservation混写。

更接近本文的是可学习或可微SPH。JAX-SPH实现了JAX中的可微WCSPH，报告了5个求解步的AD/FD比较、100步逆问题和SPH solver-in-the-loop [V002]；diffSPH则在PyTorch中覆盖多类SPH形式、逆问题、优化、混合corrector和跨数百步的梯度传播 [V004]。因此，本稿不能以“首个可微SPH”或“首个SPH solver-in-the-loop”为定位。可辩护的区别只可能来自资格合同、证据粒度与负结果的完整保留。

## 1.3 动态solver-in-the-loop的可微性与可信度问题

solver-in-the-loop已经证明学习corrector可以通过可微PDE求解器接受多步训练信号，并在若干Eulerian PDE上形成长期rollout [V016]；可扩展可微物理也已用于学习与控制 [V015]。然而，“代码由AD框架实现”只说明导数路径可构造，不等于该路径在给定步长、时间跨度、状态历史和离散事件下经过外部梯度核验。AD-CFD文献长期使用tangent/adjoint checking、有限差分或相关一致性试验来核验导数实现 [V005,V006,V007,V008]；JAX-SPH提供了粒子求解器中的直接五步先例 [V002]。

动态图进一步引入分支边界：近邻关系通常随粒子位置每步重建 [V002,V013]，而离散建边事件不能仅凭连续edge weight直觉处理。现有核验文献中可以找到动态图rollout、可微SPH和非光滑物理模拟的相邻证据，但在本次verified集合内，未发现将SPH cutoff birth/death、事件两侧fixed-topology gradients与piecewise-smooth边界作为独立资格分支的同构报告。该判断仅限当前94篇已核验集合，不能表述为“从未有人做过”。

## 1.4 verification-first定位、研究问题与有限贡献

Scientific ML的可信度讨论正在把传统计算科学中的verification、validation、calibration、uncertainty和适用域重新引入ML增强求解器 [V020,V029]；REFORMS则强调主张、数据、评估与可复现性的透明报告 [V025]。与通常以训练误差、rollout稳定性或加速比为主的论文不同，本研究在训练前先冻结可执行合同，并允许资格链以NOT_QUALIFIED结束。这里的“verification-first”是研究顺序和证据边界，不是对既有性能研究价值的否定。

本文提出三个研究问题：RQ1，如何把守恒、RK2阶段语义、动态图重建和accepted-only history commit转化为可执行合同；RQ2，zero correction、结构守恒与离散拓扑事件能否分别资格认定；RQ3，固定拓扑多步路径中，AD/FD资格在何种冻结条件下不能形成完整证据。相应贡献限于：（1）reference–implementation–gradient–topology分层资格链；（2）zero correction相对D0的288/288 bitwise等价与540/540阶段线动量守恒检查；（3）完整360-probe稳定窗矩阵及216通过、144失败；（4）TE1 edge birth/death、replay和event-side gradient审计；（5）将失败、未决归因与Stage 03E未授权共同保留。本文不回答训练是否成功、模型是否改善SPH或D3是否优于D1/D2。 <!-- CLAIM:C03,C06,C08,C13,C20,C21,C25,C26,C27,C29 -->
# 2. 控制方程与模型形式

## 2.1 WCSPH基线

冻结的半离散系统以粒子状态S={x_i, v_i, ρ_i}为基本变量。位置、密度和速度的演化写为：

$$ dx_i/dt = v_i $$

$$ dρ_i/dt = C_SPH,i(S) $$

$$ dv_i/dt = a_SPH,i(S) + a_θ,i(S_history, H_history, G_history) $$

压力采用冻结的弱可压EOS：

$$ p_i = c_s²(ρ_i - ρ₀) $$

本文不重新资格认定基线黏性算子，也不把Stage 03结果解释为Stage 01 V2恢复。基线方程、图和时间步选择仍由SPH求解器控制。

## 2.2 additive momentum correction

神经模块只产生加性加速度修正：

$$ a_θ,i = (1/m_i) Σ_{j:{i,j}∈G} f_θ,ij $$

这一接口把网络约束在动量修正层，不允许其直接预测粒子位置、替代EOS、改变邻域membership或覆盖baseline加速度。zero correction时，a_θ,i严格为零，从而定义可执行的baseline退化合同。

## 2.3 reciprocal antisymmetric pair-force

成对修正力写为：

$$ f_θ,ij = F⁰_ij [ α_ij r̂_ij + β_ij t_ij ] $$

其中α_ij=α_ji、β_ij=β_ji，且r̂_ji=-r̂_ij、t_ji=-t_ij，因此f_θ,ji=-f_θ,ij。该硬反对称构造在图上直接消去成对内力和；它建立结构守恒，不建立非零修正的准确性、必要性或性能优势。[V022,V028]

## 2.4 D0–D3架构

D0为无修正baseline；D1使用瞬时局部token与MLP；D2引入循环hidden state；D3使用因果temporal attention处理accepted history。D1–D3共享tokenization、reciprocal head、RK2、graph rebuild与安全拒绝语义。D0–D3的作用是控制结构复杂度，不是经过训练的性能排序。冻结实现合同在Stage 03C通过，但不证明D3优于D1/D2。 <!-- CLAIM:C06 -->

**图2设计。** D0–D3统一动态架构：并列展示baseline、instantaneous MLP、recurrent state与causal temporal attention，共享RK2、graph rebuild、history semantics与reciprocal head；图形不编码模型优越性。

## 2.5 不允许的替代与软守恒方式

合同禁止网络改变edge membership、使用单向非reciprocal边、以损失惩罚替代硬反对称、在midpoint提交history、把wrapped position用于动力学推进，或将topology事件通过未登记的soft edge规避。本文不评价这些替代设计的普遍有效性，只说明它们不属于本次冻结证据。

# 3. 验证与资格框架

## 3.1 状态等级

资格链按时间顺序包含Stage 03A specification、Stage 03B reference qualification、Stage 03C implementation verification、Stage 03D multistep gradient/topology campaign、Stage 03D-R attribution和Stage 03D-S route closure。每一状态只回答本层问题，不继承为后续层的自动PASS。 <!-- CLAIM:C03 -->

**表1 Stage 03状态账本。**

| 阶段 | 唯一状态 | 主要通过证据 | 主要边界 |
|---|---|---|---|
| Stage 03A | `DYNAMIC_HYBRID_SOLVER_SPECIFICATION_COMPLETE` | 45/45 contract hash checks；20/20 historical freeze checks；55/55 required files。 | 尚无动态实现、trajectory payload 或计算资格化。 |
| Stage 03B | `DYNAMIC_REFERENCE_TRAJECTORY_QUALIFICATION_COMPLETE` | D-R1 两族、D-R2 六例、D-R3 两族 PASS；18/18 canonical trajectories；4302 RHS/rebuilds。 | acoustic 仅 linear-regime conditional；periodic vortex 不是 exact source-free reference；D-R4 不可用。 |
| Stage 03C | `DYNAMIC_RK2_HYBRID_IMPLEMENTATION_VERIFIED` | D0 48/48；zero correction 288/288 bitwise；checkpoint 6/6；one-step autograd 6/6；全部结构/资源门 PASS。 | 未执行 multistep AD/FD、训练或 rollout 性能评价。 |
| Stage 03D | `DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED` | 216/360 stable windows；540/540 stage conservation；TE1 birth/death、6/6 replay、12/12 event-side gradients PASS。 | 144/360 probes failure；history gradient 0/6；固定拓扑 AD/FD 与 history gate 未通过。 |
| Stage 03D-R | `DYNAMIC_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED` | reverse/JVP 60/60；extended FD 2640 paths、30/60 stable；90 个 horizon 均 bounded/nonmonotone；topology status preserved。 | 19 unresolved；多类 FD conditioning/non-smooth/structural-zero 贡献并存；history rollout influence strongly attenuated。 |

## 3.2 reference hierarchy

D-R1用于解析/MMS verification，D-R2用于同半离散时间参考，D-R3用于source-free exact/independent validation，D-R4要求外部V&V-qualified reference。层级越高，允许的确认性解释越强；但任何一层都不等于训练或性能数据。D-R4当前不可用，是投稿证据缺口而不是被低层级参考替代的空位。

## 3.3 FAIL、NOT_QUALIFIED与NOT_EXECUTED区别

FAIL表示执行了冻结门且不满足；NOT_QUALIFIED表示整体所需证据未满足，可能同时包含局部PASS；NOT_EXECUTED表示相关工作没有被授权或运行。Stage 03D属于NOT_QUALIFIED，因为144/360失败且history为0/6；动态训练属于NOT_EXECUTED，不能写为“训练失败”。

## 3.4 claim boundary

SUPPORTED claim可以直接由冻结证据支持；CONDITIONAL claim必须保留选择范围和限定词；UNSUPPORTED claim不得进入可提交稿。每条事实性结果句在P1源稿中以不可见CLAIM标记映射到`claim_to_evidence_matrix.json`，未映射语句在审计中标记`UNSUPPORTED_DRAFT_STATEMENT`。 <!-- CLAIM:C30 -->

# 4. 动态参考轨迹

## 4.1 D-R1 Lagrangian MMS

D-R1包含Lagrangian compression与coupled deformation两族，通过解析闭包与符号定义检查。其作用是验证控制方程、源项和Lagrangian状态演化的一致性；MMS不构成无源物理验证，也不允许作为模型性能数据。[V018,V035]

## 4.2 D-R2 semidiscrete DOP853

D-R2对两族、N=8/12/16共六个case建立同半离散算子的高精度DOP853时间参考，6/6通过。该层隔离时间积分误差，但空间离散与核误差仍在两条轨迹中共享，因此DOP853不是连续方程真值。[V005,V006]

## 4.3 D-R3 oblique shear

D-R3采用oblique shear A/B两族source-free exact reference，并在N=8/12/16形成六条精确轨迹。结合D-R1与D-R2，Stage 03B最终形成18条canonical trajectories；这些轨迹只用于资格化与后续冻结probe，不用于训练、normalization或阈值选择。 <!-- CLAIM:C04 -->

## 4.4 acoustic conditional boundary

声学候选仅被分类为`DR3_ACOUSTIC_LINEAR_REGIME_CONDITIONAL`。因此正文只能将其视为线性区间的条件性参考，不能外推为任意振幅或长期声学传播的精确D-R3。 <!-- CLAIM:C05 -->

## 4.5 periodic-vortex rejection

periodic vortex被拒绝为exact source-free reference。拒绝结果被保留，因为reference qualification的价值包括排除角色不匹配的候选，而不是只展示通过家族。该候选不进入性能比较，也不被重新命名为外部独立验证。 <!-- CLAIM:C05 -->

**图4设计。** D-R1/D-R2/D-R3参考层级：分层显示MMS verification、semidiscrete time reference与source-free validation，并在侧栏标记acoustic conditional、periodic-vortex rejection与D-R4缺口。

**表2 动态参考轨迹清单。**

| 层级 | 冻结对象 | 结果 | 证据角色与边界 |
|---|---|---|---|
| D-R1 | Lagrangian compression；coupled deformation | 两族PASS | 解析/MMS verification，不等于物理验证 |
| D-R2 | 同半离散DOP853 time reference | 6/6 PASS | 时间参考，不是空间真值 |
| D-R3 | oblique shear A/B | 两族PASS；6条exact trajectories | source-free independent validation |
| Acoustic | acoustic candidate | linear-regime conditional | 不外推为无限制精确D-R3 |
| Vortex | periodic vortex candidate | rejected as exact source-free | 不作为D-R3精确参考 |
| D-R4 | 外部V&V-qualified reference | NOT_AVAILABLE | 当前独立验证缺口 |

# 5. 动态求解器实现

## 5.1 unwrapped/wrapped position

动力学状态保存unwrapped position以保持时间连续性；wrapped position仅用于周期邻域搜索与最小镜像表示。该分离避免粒子跨越周期边界时在积分状态中引入人为跳跃，同时使graph construction保持确定。

## 5.2 RK2 start/midpoint/accept

显式midpoint/RK2采用：

$$ k₁ = F(Sⁿ, historyⁿ) $$

$$ Sⁿ⁺¹ᐟ² = Sⁿ + (Δt/2) k₁ $$

$$ k₂ = F(Sⁿ⁺¹ᐟ², historyⁿ + ephemeral token) $$

$$ Sⁿ⁺¹ = Sⁿ + Δt k₂ $$

start与midpoint是独立RHS evaluation。accepted state必须通过finite与safety checks，拒绝步同时回滚state和history。

## 5.3 graph rebuild

每次RHS evaluation从对应state重建reciprocal graph，禁止固定整步topology。该语义保证midpoint的邻域由midpoint位置决定；同时，Stage 03D的fixed-topology AD/FD会显式筛选graph sequence identity，以免将edge change混入连续路径的梯度比较。

## 5.4 temporal history commit

start和midpoint只读committed snapshot；midpoint token为ephemeral，不得append、evict或覆盖accepted history。只有Sⁿ⁺¹被接受后，才在物理时刻tₙ₊₁原子提交一个token。该事务语义是D2/D3可复现与checkpoint一致性的必要条件。

**图3设计。** RK2 graph rebuild与history commit：Sⁿ→start RHS/rebuild→midpoint/ephemeral token→midpoint RHS/rebuild→accept checks→一次accepted commit；拒绝路径回滚state与cache。

## 5.5 checkpoint/resume

checkpoint记录state、graph、history、模型参数与RNG语义。冻结6种配置的resume结果为6/6通过，说明指定执行路径可复现；这里不存在训练checkpoint，不能把该结果解释为训练过程可恢复。 <!-- CLAIM:C10 -->

# 6. 结构验证

## 6.1 independent RK2 48/48

独立functional RK2与主实现的48/48冻结检查全部通过，覆盖指定状态、时间和graph语义。该结果支持实现一致性，但不覆盖长时间稳定性或自主rollout。 <!-- CLAIM:C07 -->

## 6.2 zero correction 288/288

zero correction在288/288检查中与D0 baseline bitwise相同，且没有使用事后容差。该结果是D1–D3接口的退化极限验证：当神经修正严格为零时，动态框架不改变baseline；它不证明非零修正准确。 <!-- CLAIM:C08 -->

## 6.3 pair-force conservation

反对称reciprocal pair-force使每条无序边的修正内力成对抵消。结构smoke包含72/72通过，多步campaign的540/540 stage conservation检查也通过。两者共同支持冻结实现中的离散线动量结构保持，但不支持长期稳定性或误差收敛主张。 <!-- CLAIM:C09,C20 -->

## 6.4 O(2)、Galilean与周期性

冻结structural smoke同时覆盖O(2)变换、粒子置换、Galilean与周期一致性。这里的PASS表示特定变换合同通过，不表示神经表示已经学习出一般物理规律。[V017,V023,V028]

## 6.5 one-step autograd

one-step autograd共6/6运行返回预期的有限非零梯度，证明基础计算图连接存在。Stage 03C没有运行finite difference或multistep AD/FD，因此该PASS不能用于推导完整多步可微性。 <!-- CLAIM:C11 -->

## 6.6 resource boundary

Stage 03C和Stage 03D的正式执行采用CPU float64以降低数值路径歧义；资源记录只服务复现，不构成速度、成本或加速比较。优化器对象、参数更新和训练运行均为0。 <!-- CLAIM:C12,C27 -->

**图5设计。** Zero-correction与结构资格矩阵：展示48/48、288/288、72/72、6/6、6/6，并以独立灰色栏标记training/performance为NOT EXECUTED，禁止把结构PASS解释为性能PASS。

**表3 实现与结构资格门。**

| 资格门 | 结果 | 状态 | 允许解释 |
|---|---:|---|---|
| Independent RK2 | 48/48 | PASS | 冻结RK2实现一致 |
| Zero correction | 288/288 | PASS | 与D0 bitwise等价 |
| Structural smoke | 72/72 | PASS | 结构守恒/等变等冻结门通过 |
| Checkpoint/resume | 6/6 | PASS | state/graph/history/RNG可复现 |
| One-step autograd | 6/6 | PASS | 一步梯度通路有限非零 |
| Dynamic training / performance | 0 / 0 | NOT_EXECUTED | 不可写为训练失败或性能不足 |

# 7. 多步可微性资格

## 7.1 frozen 360-probe design

正式合同包含D1–D3、四个固定拓扑case、三个seed、K=1/2/4/8 horizon及参数、初值和history probe，合计360 rows。每个probe保存AD重复、四个冻结epsilon的FD值、graph sequence identity和stable-window verdict，形成2880次历史AD/FD比较。矩阵在结果前冻结，不允许根据结果增加epsilon或删probe。 <!-- CLAIM:C13 -->

## 7.2 AD/FD stable-window rule

资格门要求相邻epsilon形成稳定窗口，并同时满足方向、相对/绝对误差和确定性条件。单个epsilon的偶然接近不足以PASS；导数接近结构零时，需要结合绝对误差和尺度分类。该规则的目的是把roundoff、truncation与非光滑影响暴露出来，而不是优化通过率。[V002,V005,V007]

## 7.3 complete results：216/360

360个probe中216个获得stable window，144个未通过，总体通过率不被用作模型排名。按horizon，K=1/2/4/8分别为60/57/51/48个PASS；按arm，D1、D2、D3分别为65/96、75/120、76/144。完整结果意味着正负证据必须共同出现，Stage 03D据此保持NOT_QUALIFIED。冻结多阶段守恒同时为540/540通过，说明结构守恒可以在梯度资格失败时独立成立。 <!-- CLAIM:C13,C20,C26 -->

**图6设计。** 完整360-probe AD/FD outcome matrix：按arm/case/horizon/probe组织全部360格，216个PASS与144个failure同时显示；附七类failure taxonomy及19 unresolved，不允许筛选最佳子集。

## 7.4 failure taxonomy

144个失败按唯一主因分为：方向/符号不一致5、接近结构零29、FD非单调且无相邻窗69、roundoff主导3、truncation主导3、固定图数值非光滑16和UNRESOLVED 19。分类覆盖所有失败，但“唯一主因”是账本规则，不意味着每个失败只有一个物理贡献。19个未决row必须保留在主文和补充材料。 <!-- CLAIM:C14 -->

**表4 AD/FD失败分类。**

| 主因 | 数量 | 解释边界 |
|---|---:|---|
| AD/FD方向或符号不一致 (`AD_FD_DIRECTION_OR_SIGN_MISMATCH`) | 5 | 归因诊断，不代表合同已修复 |
| 导数接近结构零 (`DERIVATIVE_NEAR_STRUCTURAL_ZERO`) | 29 | 归因诊断，不代表合同已修复 |
| FD非单调且无相邻稳定窗 (`FD_NONMONOTONE_NO_ADJACENT_WINDOW`) | 69 | 归因诊断，不代表合同已修复 |
| FD舍入误差主导 (`FD_ROUNDOFF_DOMINATED`) | 3 | 归因诊断，不代表合同已修复 |
| FD截断误差主导 (`FD_TRUNCATION_DOMINATED`) | 3 | 归因诊断，不代表合同已修复 |
| 固定图数值非光滑 (`NUMERICAL_NONSMOOTHNESS_WITH_FIXED_GRAPH`) | 16 | 归因诊断，不代表合同已修复 |
| 未决 (`UNRESOLVED`) | 19 | 归因诊断，不代表合同已修复 |

## 7.5 reverse/JVP crosscheck

在统一数学attention后端上，reverse-mode与JVP的60/60选择比较通过。这支持两条AD实现路径的一致性，却不能替代FD或使360矩阵整体转为PASS。 <!-- CLAIM:C16 -->

## 7.6 extended FD

extended FD扩展至2640条路径；60个选择路径中30个显示扩展稳定性，另30个呈U形conditioning特征。该诊断支持“FD conditioning对部分失败有贡献”，但不支持“全部失败都是FD伪影”。 <!-- CLAIM:C17 -->

## 7.7 history attenuation

history资格门0/6通过；在reference-prehistory追踪中，一条路径被归为conditioning limited，五条低于FD resolution。该结果表示当前冻结路径中的history influence在rollout传播中强烈衰减，而不是证明temporal memory无用，更不是训练失败。 <!-- CLAIM:C15 -->

## 7.8 backend sensitivity

历史默认后端reverse与math JVP在60个选择诊断中匹配48个，12个不匹配，且不匹配集中在选定D3路径。正文只能写为“冻结选择诊断中存在backend sensitivity”；不能写为D3内在不可微，也不能在P1切换后端后重新资格化。 <!-- CLAIM:C18 -->

**图7设计。** History attenuation与backend sensitivity多面板：history 0/6、reverse/JVP 60/60、extended FD 30/60与historical-backend match 48/60；标题和图例均使用diagnostic限定。

## 7.9 mixed/unresolved attribution

90条horizon traces均被分类为bounded或nonmonotone，没有检测到系统性vanish/explode；该结果不证明训练梯度健康。综合AD crosscheck、extended FD、history attenuation、backend sensitivity与19个未决row，Stage 03D-R的唯一结论为`DYNAMIC_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED`。D-R是归因而非修复，不覆盖Stage 03D。 <!-- CLAIM:C19,C26 -->

# 8. 拓扑事件资格

## 8.1 TE1设计

TE1_TAGGED_PAIR_OSCILLATION使用两粒子确定性路径穿越cutoff Rc，在s=0.25附近发生birth、s=0.75附近发生death。4097点dense scan、三次bitwise重复及reciprocity/duplicate检查共同锁定事件语义。TE1是kinematic audit family，不代表任意动态图问题。（与可微模拟中的事件敏感性相邻，但本TE1合同由项目证据定义）[V015,V019]

## 8.2 birth/death

dense scan记录恰好一次edge birth和一次death，顺序、bracket、margin、minimum-image及reciprocity门均通过。edge existence从0跳到1或从1跳到0，故该变量本身不是连续可微映射。 <!-- CLAIM:C21 -->

## 8.3 stage replay

D1、D2、D3在birth/death两侧的topology-stage replay共6/6通过，重复构造得到一致graph和pair语义。该结果仅资格认定冻结TE1实现。 <!-- CLAIM:C22 -->

## 8.4 fixed-side gradients

在事件前后各自固定edge membership，D1–D3的12/12 event-side gradient检查通过。允许的主张是事件两侧分支内piecewise-smooth；禁止的主张是跨cutoff membership存在普通导数。 <!-- CLAIM:C23 -->

## 8.5 force jump

事件两侧的修正力跳被登记为有限、有界、确定且满足成对守恒；连续性不是该离散事件的资格要求。跨事件中心差分随epsilon呈离散图变化特征，不能归因为网络梯度本身失败。 <!-- CLAIM:C24 -->

## 8.6 empty graph

edge absent侧保留canonical self records但不制造synthetic self pair；非self pair聚合为exact zero，token保持finite。D1–D3在两侧共6条empty-graph记录确定。 <!-- CLAIM:C24 -->

## 8.7 piecewise-smooth boundary

TE1组件状态为`TOPOLOGY_EVENT_COMPONENT_QUALIFIED`，因为birth/death、replay、fixed-side gradients、finite jumps和empty graph语义均满足；该组件PASS与Stage 03D整体NOT_QUALIFIED同时成立。 <!-- CLAIM:C25,C26 -->

**图8设计。** TE1 edge birth/death与piecewise-smooth boundary：显示s=0.25 birth、s=0.75 death、两侧固定拓扑梯度、有限力跳与空图语义；edge membership以阶跃呈现，不画成连续可微曲线。

**表5 拓扑事件证据。**

| TE1证据 | 结果 | 状态 | 禁止外推 |
|---|---:|---|---|
| edge birth | 1/1 | PASS | 非任意拓扑族 |
| edge death | 1/1 | PASS | 非连续edge membership |
| stage replay | 6/6 | PASS | 仅冻结TE1语义 |
| fixed-side gradients | 12/12 | PASS | 不穿过cutoff事件求导 |
| force jump | finite and bounded | PASS | 不声称事件处连续 |
| empty graph | deterministic | PASS | 不构造合成非物理pair |

# 9. 讨论

## 9.1 与learned SPH correction和fully learned particle simulator的区别

与Neural SPH相比，本项目不是在已训练GNN rollout上加入SPH压力、黏性或外力分量；它保留冻结SPH基线，并把未训练神经项限制为加性reciprocal pair-force，同时要求zero correction严格退化到D0 [V003]。与参数化SPH湍流模型相比，本项目没有训练平滑核或闭合项，也没有DNS性能证据 [V001]。与JAX-SPH和diffSPH相比，本项目的主要增量不是“可微SPH平台”，而是把zero fallback、RK2阶段图重建、history事务、多步AD/FD和topology event拆成独立门；后两项工作已经建立了可微SPH、逆问题和solver-in-the-loop的强直接先例 [V002,V004]。

GNS、continuous-convolution模拟器和LagrangeBench基线主要直接学习粒子动力学并自回归rollout [V011,V013,V024]。本项目则不允许网络直接替代位置推进、EOS或邻域membership。这个区别决定了“zero correction”在本项目中具有可执行的基线身份意义，而在完全学习模拟器中通常没有同一语义。它也意味着他人的rollout性能不能被用来暗示本模型会提高精度、稳定性或成本。

## 9.2 与conservative/equivariant GNN的区别

DMCF通过反对称连续卷积硬保证线动量，并已完成训练与大规模粒子rollout [V022]；DYNAMI-CAL GRAPHNET同时编码线、角动量交换，并在颗粒动力学上评估长期rollout [V028]。本项目的reciprocal head同样属于hard architectural constraint，而不是守恒罚项；但当前冻结证据只支持指定阶段检查中的离散线动量消去，不支持角动量、能量、训练稳定性或长时守恒。EGNN/SEGNN等工作进一步说明，几何等变应与守恒结论分开陈述 [V017,V023]。

## 9.3 与differentiable CFD/physics solver的区别

传统AD-CFD与tangent/adjoint文献把导数检查视为实现核验的一部分 [V005,V007,V008]，solver-in-the-loop则将多步求解器梯度用于训练corrector [V016]。JAX-SPH已报告5步AD/FD比较，但采用单一epsilon；diffSPH报告更长梯度链和广泛应用 [V002,V004]。本项目的差异是使用冻结的多epsilon stable-window、完整360 probes、reverse/JVP、extended FD、history attenuation与backend sensitivity进行资格和归因。由于216/360通过而144/360失败，该差异目前形成的是更严格的负资格结论，不是优于前述框架的性能结论。

## 9.4 zero-correction evidence与216/360、144 failures的含义

288/288 bitwise zero-correction等价证明，关闭神经修正时D1–D3接口不会改变指定D0执行路径。这对混合求解器很重要，因为它把后续差异限定到显式修正路径，而不是隐藏的图、缓存或积分分叉。该证据仍然不证明非零修正准确、必要或可训练。

完整360-probe矩阵中216个stable windows说明部分固定拓扑多步方向导数可被AD与FD共同支持；144个失败以及history门0/6使Stage 03D整体保持NOT_QUALIFIED。reverse/JVP 60/60一致只排除了若干AD模式实现分歧，extended FD、horizon scaling和backend sensitivity又表明失败来源混合，不能被压缩成单一“FD噪声”或单一“AD错误”。保留这些负结果的价值在于阻止训练授权建立在选择性成功probe上，这与Scientific ML可信度和透明报告的方向一致 [V025,V029]。

## 9.5 topology piecewise smoothness的意义

TE1把离散edge membership与事件两侧连续分支分开：birth/death、6/6 replay、12/12 fixed-side gradients、有限力跳和empty-graph语义可以分别通过，而edge existence本身仍是阶跃。该结果避免两种相反误读：跨事件中心差分异常不应自动归因于网络梯度失败；event-side PASS也不应写成cutoff membership可微。当前证据仅覆盖冻结TE1与本实现，尚不能证明任意粒子数、邻域算法、边界处理或并行后端下的一般性。

## 9.6 为什么未训练既合理又构成限制

Stage 03E authorization=false，因此不执行训练是预注册资格链的结果，不是训练失败或性能回避。若在多步梯度门未通过时继续训练，将难以区分优化失败、梯度实现问题和离散非光滑性。另一方面，未训练也使本文缺少直接竞争工作通常提供的rollout误差、长期稳定性、外推和成本数据 [V003,V022,V024]。因此，本稿可作为verification methods论文继续修订，但不具备完整solver性能论文的证据等级。

## 9.7 与Scientific ML V&V框架的关系及未来证据

本研究把代码/算法verification、参考层级、validation和未执行performance显式分开，符合SciML可信度框架所强调的适用域与持续证据积累 [V020,V029]。但一般性仍需通过至少两种独立SPH实现、更多动态拓扑家族、不同边界/粒子分辨率、公开可复现实验以及D-R4或等价外部参考证明。若未来要升级为完整CMAME solver论文，还必须在重新授权后完成训练资格、自主rollout、精度–成本曲线、长期守恒/稳定性、跨问题外推与独立验证；任何新增证据都应作为新阶段，不得回写现有Stage 01–03 verdict。

## 9.8 保留的历史边界

Stage 01保持`V2_QUALIFICATION_FAIL`，Stage 01H为`FINITE_RESOLUTION_DOMINANT`，黏性算子形式仍为`NOT_CONFIRMED`；Stage 02静态路线保持关闭。Stage 03没有恢复这些状态。当前仍有mixed/unresolved梯度归因、无D-R4、无训练和无性能，这些弱点必须在摘要、讨论与投稿层级判断中主动可见。 <!-- CLAIM:C01,C02,C14,C27,C28 -->
# 10. 结论

本文建立了守恒型动态神经–SPH耦合的verification-first资格链。D0–D3统一接口、独立RK2、zero correction、结构守恒、checkpoint与one-step autograd形成正实现证据；完整360-probe矩阵则使多步梯度总体保持NOT_QUALIFIED。TE1证明离散edge birth/death可与事件两侧fixed-topology gradients分开资格认定，但不能把edge membership写成可微。Stage 03D-R保留mixed/unresolved边界，Stage 03E未授权。 <!-- CLAIM:C03,C06,C07,C08,C09,C10,C11,C13,C21,C22,C23,C25,C26 -->

因此，本稿的贡献是验证架构及其证据边界，而不是证明训练成功、rollout改进或Transformer优越性。P1可以形成带严格claim limitation的方法/验证中文稿；完整求解器主张仍需训练资格、rollout性能/稳定性和独立验证三类新证据。 <!-- CLAIM:C27,C28,C29 -->

# Data availability

本文v0.2使用的全部项目数值结果均来自`publication_input_freeze_manifest.json`登记的项目内部机器artifact，并由hash锁定。360-row matrix、AD/FD comparisons、extended FD、history、horizon、TE1与manifest拟作为补充数据组织；公开仓库、持久标识和许可将在投稿前核验后填写。[AUTHOR-TODO: 投稿前填写公开仓库、持久标识与许可；当前不作外部可用性主张。]

# Code availability

本文涉及的Stage 01–03实现与审计代码当前保存在项目工作区。P2不修改历史代码，也不产生新的数值计算。投稿前需确定可公开代码范围、版本标签、环境文件与许可，并填写持久链接。[AUTHOR-TODO: 投稿前填写代码版本、持久链接与软件引用；当前不作公开性主张。]

# Author contributions

[AUTHOR-TODO: 按CRediT taxonomy核验并填写作者贡献，不在P1虚构作者角色。]

# Conflict of interest

[AUTHOR-TODO: 投稿前由全体作者核验并填写竞争利益声明。]

# References

[V001] Michael Woodward; Yifeng Tian; Criston Hyett; Chris Fryer; Mikhail Stepanov; Daniel Livescu; Michael Chertkov (2023). Physics-informed machine learning with smoothed particle hydrodynamics: Hierarchy of reduced Lagrangian models of turbulence. Physical Review Fluids, 8, 5, 054602. https://doi.org/10.1103/physrevfluids.8.054602

[V002] Artur P. Toshev; Harish Ramachandran; Jonas A. Erbesdobler; Gianluca Galletti; Johannes Brandstetter; Nikolaus A. Adams (2024). JAX-SPH: A Differentiable Smoothed Particle Hydrodynamics Framework. ICLR 2024 Workshop on AI4DifferentialEquations in Science. https://openreview.net/forum?id=8X5PXVmsHW

[V003] Artur Toshev; Jonas A. Erbesdobler; Nikolaus A. Adams; Johannes Brandstetter (2024). Neural SPH: Improved Neural Modeling of Lagrangian Fluid Dynamics. Proceedings of the 41st International Conference on Machine Learning, 235, 48428–48452. https://proceedings.mlr.press/v235/toshev24a.html

[V004] Rene Winchenbach; Nils Thuerey (2026). diffSPH: Differentiable smoothed particle hydrodynamics for hybrid machine learning solutions in fluid mechanics. Journal of Computational Physics, 555, 114769. https://doi.org/10.1016/j.jcp.2026.114769

[V005] Eugenia Kalnay (2002). Coding and checking the tangent linear and the adjoint models. Atmospheric Modeling, Data Assimilation and Predictability, 264-275. https://doi.org/10.1017/cbo9780511802270.009

[V006] Adrian Sandu (2008). Reverse Automatic Differentiation of Linear Multistep Methods. Lecture Notes in Computational Science and Engineering Advances in Automatic Differentiation, 1-12. https://doi.org/10.1007/978-3-540-68942-3_1

[V007] Faidon Christakopoulos; Dominic Jones; Jens-Dominik Müller (2011). Pseudo-timestepping and verification for automatic differentiation derived CFD codes. Computers &amp; Fluids, 46, 1, 174-179. https://doi.org/10.1016/j.compfluid.2011.01.039

[V008] Emre Özkaya; Anil Nemili; Nicolas R. Gauger (2012). Application of Automatic Differentiation to an Incompressible URANS Solver. Lecture Notes in Computational Science and Engineering Recent Advances in Algorithmic Differentiation, 35-45. https://doi.org/10.1007/978-3-642-30023-3_4

[V009] Sam Greydanus; Misko Dzamba; Jason Yosinski (2019). Hamiltonian Neural Networks. Advances in Neural Information Processing Systems, 32. https://proceedings.neurips.cc/paper/2019/hash/26cd8ecadce0d4efd6cc8a8725cbd1f8-Abstract.html

[V010] Yunzhu Li; Jiajun Wu; Russ Tedrake; Joshua B. Tenenbaum; Antonio Torralba (2019). Learning Particle Dynamics for Manipulating Rigid Bodies, Deformable Objects, and Fluids. International Conference on Learning Representations. https://openreview.net/forum?id=rJgbSn09Ym

[V011] Benjamin Ummenhofer; Lukas Prantl; Nils Thuerey; Vladlen Koltun (2020). Lagrangian Fluid Simulation with Continuous Convolutions. International Conference on Learning Representations. https://openreview.net/forum?id=B1lDoJSYDH

[V012] Miles Cranmer; Sam Greydanus; Stephan Hoyer; Peter Battaglia; David Spergel; Shirley Ho (2020). Lagrangian Neural Networks. ICLR 2020 Workshop on Integration of Deep Neural Models and Differential Equations. https://openreview.net/forum?id=iE8tFa4Nq

[V013] Alvaro Sanchez-Gonzalez; Jonathan Godwin; Tobias Pfaff; Rex Ying; Jure Leskovec; Peter Battaglia (2020). Learning to Simulate Complex Physics with Graph Networks. Proceedings of the 37th International Conference on Machine Learning, 119, 8459–8468. https://proceedings.mlr.press/v119/sanchez-gonzalez20a.html

[V014] Kenneth I. Aycock; Nuno Rebelo; Brent A. Craven (2020). Method of manufactured solutions code verification of elastostatic solid mechanics problems in a commercial finite element solver. Computers &amp; Structures, 229, 106175. https://doi.org/10.1016/j.compstruc.2019.106175

[V015] Yi-Ling Qiao; Junbang Liang; Vladlen Koltun; Ming C. Lin (2020). Scalable Differentiable Physics for Learning and Control. Proceedings of the 37th International Conference on Machine Learning, 119, 7847–7856. https://proceedings.mlr.press/v119/qiao20a.html

[V016] Kiwon Um; Robert Brand; Yun Fei; Philipp Holl; Nils Thuerey (2020). Solver-in-the-Loop: Learning from Differentiable Physics to Interact with Iterative PDE-Solvers. Advances in Neural Information Processing Systems, 33, 6111–6122. https://proceedings.neurips.cc/paper/2020/hash/43e4e6a6f341e00671e123714de019a8-Abstract.html

[V017] Victor Garcia Satorras; Emiel Hoogeboom; Max Welling (2021). E(n) Equivariant Graph Neural Networks. Proceedings of the 38th International Conference on Machine Learning, 139, 9323–9332. https://proceedings.mlr.press/v139/satorras21a.html

[V018] Pawan Negi; Prabhu Ramachandran (2021). How to train your solver: A method of manufactured solutions for weakly compressible smoothed particle hydrodynamics. Physics of Fluids, 33, 12, 127108. https://doi.org/10.1063/5.0072383

[V019] Tobias Pfaff; Meire Fortunato; Alvaro Sanchez-Gonzalez; Peter W. Battaglia (2021). Learning Mesh-Based Simulation with Graph Networks. International Conference on Learning Representations. https://openreview.net/forum?id=roNqYL0_XP

[V020] Erin Acquesta (2022). Adapting Verification and Validation Principles to a Credibility Process for Scientific Machine Learning.. Proposed for presentation at the SIAM UQ 2022 held April 12-15, 2022 in Atlanta , GA. https://doi.org/10.2172/2002271

[V021] Zijie Li; Amir Barati Farimani (2022). Graph neural network-accelerated Lagrangian fluid simulation. Computers &amp; Graphics, 103, 201-211. https://doi.org/10.1016/j.cag.2022.02.004

[V022] Lukas Prantl; Benjamin Ummenhofer; Vladlen Koltun; Nils Thuerey (2022). Guaranteed Conservation of Momentum for Learning Particle-Based Fluid Dynamics. Advances in Neural Information Processing Systems 35, 6901-6913. https://doi.org/10.52202/068431-0500

[V023] Johannes Brandstetter; Rob Hesselink; Elise van der Pol; Erik J. Bekkers; Max Welling (2022). SE(3)-Equivariant and Steerable Graph Networks. International Conference on Learning Representations. https://openreview.net/forum?id=_xwr8gOBeV1

[V024] Artur Toshev; Gianluca Galletti; Fabian Fritz; Stefan Adami; Nikolaus Adams (2023). LagrangeBench: A Lagrangian Fluid Mechanics Benchmarking Suite. Advances in Neural Information Processing Systems 36, 36, 64857-64884. https://doi.org/10.52202/075280-2830

[V025] Sayash Kapoor; Emily M. Cantrell; Kenny Peng; Thanh Hien Pham; Christopher A. Bail; Odd Erik Gundersen; Jake M. Hofman; Jessica Hullman; Michael A. Lones; Momin M. Malik; Priyanka Nanayakkara; Russell A. Poldrack; Inioluwa Deborah Raji; Michael Roberts; Matthew J. Salganik; Marta Serra-Garcia; Brandon M. Stewart; Gilles Vandewiele; Arvind Narayanan (2024). REFORMS: Consensus-based Recommendations for Machine-learning-based Science. Science Advances, 10, 18, eadk3452. https://doi.org/10.1126/sciadv.adk3452

[V026] Olav Møyner (2025). JutulDarcy.jl - a fully differentiable high-performance reservoir simulator based on automatic differentiation. Computational Geosciences, 29, 4, 30. https://doi.org/10.1007/s10596-025-10366-6

[V027] Takefumi Higaki; Yuki Tanabe; Hirotada Hashimoto; Takahito Iida (2025). Step-by-step enhancement of a graph neural network-based surrogate model for Lagrangian fluid simulations with flexible time step sizes. Applied Ocean Research, 154, 104424. https://doi.org/10.1016/j.apor.2025.104424

[V028] Vinay Sharma; Olga Fink (2026). A physics-informed graph neural network conserving linear and angular momentum for dynamical systems. Nature Communications, 17, 1, 1045. https://doi.org/10.1038/s41467-025-67802-5

[V029] John D Jakeman; Lorena A Barba; Joaquim R R A Martins; Thomas O’Leary-Roseberry (2026). Verification and validation for trustworthy scientific machine learning. Machine Learning: Science and Technology, 7, 2, 025055. https://doi.org/10.1088/2632-2153/ae59ec

[V035] Patrick J. Roache (2002). Code Verification by the Method of Manufactured Solutions. Journal of Fluids Engineering, 124, 1, 4-10. https://doi.org/10.1115/1.1436090

[V042] M.B. Liu; G.R. Liu (2006). Restoring particle consistency in smoothed particle hydrodynamics. Applied Numerical Mathematics, 56, 1, 19-36. https://doi.org/10.1016/j.apnum.2005.02.012

[V049] Mostafa Safdari Shadloo; Amir Zainali; Mehmet Yildiz; Afzal Suleman (2012). A robust weakly compressible SPH method and its comparison with an incompressible SPH. International Journal for Numerical Methods in Engineering, 89, 8, 939-956. https://doi.org/10.1002/nme.3267

[V053] M. Antuono; A. Colagrossi; S. Marrone (2012). Numerical diffusive terms in weakly-compressible SPH schemes. Computer Physics Communications, 183, 12, 2570-2580. https://doi.org/10.1016/j.cpc.2012.07.006

[V054] Pablo S. Rojas Fredini; Alejandro C. Limache (2013). Evaluation of weakly compressible SPH variants using derived analytical solutions of Taylor–Couette flows. Computers &amp; Mathematics with Applications, 66, 3, 304-317. https://doi.org/10.1016/j.camwa.2013.05.008

[V056] Damien Violeau; Agnès Leroy (2014). On the maximum time step in weakly compressible SPH. Journal of Computational Physics, 256, 388-415. https://doi.org/10.1016/j.jcp.2013.09.001

[V058] Qirong Zhu; Lars Hernquist; Yuexing Li (2015). NUMERICAL CONVERGENCE IN SMOOTHED PARTICLE HYDRODYNAMICS. The Astrophysical Journal, 800, 1, 6. https://doi.org/10.1088/0004-637x/800/1/6

[V072] Yujie Zhu; Chi Zhang; Xiangyu Hu (2021). A consistency-driven particle-advection formulation for weakly-compressible smoothed particle hydrodynamics. Computers &amp; Fluids, 230, 105140. https://doi.org/10.1016/j.compfluid.2021.105140

[V076] Renato Vacondio; Corrado Altomare; Matthieu De Leffe; Xiangyu Hu; David Le Touzé; Steven Lind; Jean-Christophe Marongiu; Salvatore Marrone; Benedict D. Rogers; Antonio Souto-Iglesias (2021). Grand challenges for Smoothed Particle Hydrodynamics numerical schemes. Computational Particle Mechanics, 8, 3, 575-588. https://doi.org/10.1007/s40571-020-00354-1

[V082] Pawan Negi; Prabhu Ramachandran (2022). Techniques for second-order convergent weakly compressible smoothed particle hydrodynamics schemes without boundaries. Physics of Fluids, 34, 8, 087125. https://doi.org/10.1063/5.0098352

[V092] Matteo Antuono; Salvatore Marrone (2025). Weakly Compressible Approximation of the Taylor–Green Vortex Solution. Studies in Applied Mathematics, 154, 1, e12792. https://doi.org/10.1111/sapm.12792
