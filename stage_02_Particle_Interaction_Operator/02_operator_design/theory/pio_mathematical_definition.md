# PIO 数学定义合同

**合同版本：** Stage 02A frozen theory  
**适用域：** 已由 Stage 01 审计的周期、光滑、弱可压缩 SPH 范围  
**执行边界：** 本文只给出数学对象与资格条件，不定义或实现任何神经网络。

## 1. 冻结对象

令粒子状态集合为 \(\mathcal S=\{s_i\}_{i=1}^N\)，冻结 SPH 邻域规则产生有向图
\(\mathcal G(\mathcal S)=(\mathcal V,\mathcal E)\)。对周期盒晶格 \(L\)，pair 几何统一写为

\[
r_{ij}=\operatorname{MI}_{L}(x_j-x_i),\qquad v_{ij}=v_j-v_i.
\]

其中 \(\operatorname{MI}_{L}\) 必须沿用 baseline 的 minimum-image 与 tie-breaking 约定。PIO
不得重新搜索、补边、删边或把合法 cutoff crossing 当作拓扑缺陷。

冻结 baseline 为

\[
a_{\mathrm{SPH},i}=\mathcal A_{\mathrm{SPH}}(\mathcal S,\mathcal G)_i,
\]

冻结合格 reference 为

\[
a_{\mathrm{ref},i}=\mathcal A_{\mathrm{ref}}(\mathcal S;i),
\]

且二者必须在同一状态、质量、EOS、支撑与邻域合同下评价或完成可审计的状态对齐。唯一允许的
PIO 目标符号为

\[
\boxed{\Delta a_i=a_{\mathrm{ref},i}-a_{\mathrm{SPH},i}}.
\]

PIO 只输出该增量的估计 \(\widehat{\Delta a}_i\)，校正结果定义为

\[
\boxed{a_{\mathrm{corr},i}=a_{\mathrm{SPH},i}+\widehat{\Delta a}_i}.
\]

\(a_{\mathrm{ref}}\) 是否有资格进入上述差值，由 reference hierarchy、误差归因和标签资格合同共同决定；
“存在差值”本身不构成标签资格。

## 2. 零修正回退定理

若对所有粒子 \(i\) 有 \(\widehat{\Delta a}_i=0\)，则

\[
a_{\mathrm{corr},i}=a_{\mathrm{SPH},i}+0=a_{\mathrm{SPH},i}.
\]

因此映射在零输出下逐粒子、逐分量严格恢复 baseline SPH。未来实现必须以“禁用 PIO 后输出张量严格为零、
校正 RHS 与冻结 baseline RHS 一致”为测试，而不能仅用近似相等的 rollout 代替此合同。

## 3. 禁止替代边界

PIO 的唯一定位是 **learned discretization correction operator over a validated physical interaction**。
它不得直接预测 \(a_{\mathrm{corr}}\)，也不得替代或重定义：

- EOS 或声速合同；
- 压力、黏性或外力项；
- 密度求和/连续性更新；
- baseline kernel、支撑半径或邻域搜索；
- 时间积分与步长控制。

上述任何 baseline 对象发生变化都形成新的 configuration identity，需要重新资格化，不能称为同一 PIO
合同下的修正。

## 4. 两级相互作用定义

### Level 1：node residual baseline

\[
\widehat{\Delta a}_i=f_\theta\!\left(s_i,\{e_{ij}:j\in\mathcal N(i)\}\right).
\]

这是用于表达能力比较的理论 baseline。它必须满足置换、平移、周期与旋转合同，但一般不从构造上保证
\(\sum_i m_i\widehat{\Delta a}_i=0\)，故不能仅凭 node 输出声称动量守恒。

### Level 2：pair-force correction（优先）

对每个无向 reciprocal pair \(\{i,j\}\)，定义“作用于 \(i\)、来自 \(j\)”的修正力
\(\Delta F_{ij}\)，并强制

\[
\boxed{\Delta F_{ji}=-\Delta F_{ij}}.
\]

节点修正为

\[
\boxed{\widehat{\Delta a}_i=\frac{1}{m_i}
\sum_{j\in\mathcal N(i)}\Delta F_{ij}}.
\]

pair 输出只能在 reciprocal、strict-support 合格的图上获得结构守恒资格。非 reciprocal 边、重复边、
strict-support omission 或 unexpected exterior edge 都必须先由拓扑门拒绝，不能在聚合时静默修补。

## 5. 可识别性边界

只允许把已隔离、可归因的粒子/空间离散成分称为 PIO target。若 reference 差异混入时间误差、reference
误差、forcing 离散误差、模型形式偏差或不可忽略的交叉项，则样本必须被拒绝、降级为 diagnostic，或在
未来协议中建立独立可证明的分解；不得把整项 continuum–SPH 差异重命名为 discretization error。

## 6. 本合同不冻结的内容

本文不选择特征维数、attention heads、层数、激活函数、参数量、损失权重、优化器、阈值或训练样本。
这些内容既不是 Stage 02A 结论，也不获得后续实施授权。
