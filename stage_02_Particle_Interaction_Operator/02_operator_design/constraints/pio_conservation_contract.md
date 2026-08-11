# PIO 守恒合同

## 1. 线动量硬合同

对封闭周期系统，令每个无向 reciprocal pair \(\{i,j\}\) 只计数一次，且
\(\Delta F_{ji}=-\Delta F_{ij}\)。由

\[
\widehat{\Delta a}_i=\frac{1}{m_i}\sum_j\Delta F_{ij}
\]

可得修正对总线动量变化率的贡献

\[
\sum_i m_i\widehat{\Delta a}_i
=\sum_{\{i,j\}}(\Delta F_{ij}+\Delta F_{ji})=0.
\]

该结论与粒子质量是否相等无关，但依赖：pair 完整 reciprocal、每个方向的力严格相反、聚合无重复或遗漏、
且不存在未建模外部修正力。未来实现中“接近零”属于数值容差测试；理论定义要求精确反对称。

## 2. Level 1 的限制

任意 node residual \(f_\theta\) 不自动满足上述恒等式。若未来保留 Level 1，只能将
\(\|\sum_i m_i\widehat{\Delta a}_i\|\) 作为诊断，或另行给出不改变目标含义的守恒投影及其证明。
Stage 02A 不冻结此类投影。

## 3. 角动量不作自动保证

反对称力并不足以保证 pair torque 为零。对未包裹的局部 pair 几何，pair torque 与

\[
(x_i-x_j)\times\Delta F_{ij}
\]

成正比；只有中心力条件

\[
\Delta F_{ij}=\phi_{ij}r_{ij},\qquad \phi_{ji}=\phi_{ij}
\]

才使每一 pair 的 torque 为零。非中心速度方向分量即便满足反对称，也可能产生角动量变化。周期 torus
没有与普通封闭欧氏域完全相同的全局原点角动量定义，故未来验证应同时报告局部 pair torque，并在采用
unwrapped 坐标时明确 convention。Stage 01H 未确认 viscosity operator form failure；本合同不借此扩大
黏性角动量声明。

## 4. 能量与黏性诊断

pair correction 对动能的瞬时功率为

\[
P_{\mathrm{PIO}}=
\sum_i m_i v_i\cdot\widehat{\Delta a}_i
=\sum_{\{i,j\}}(v_i-v_j)\cdot\Delta F_{ij}.
\]

反对称性不决定 \(P_{\mathrm{PIO}}\) 的符号，因此线动量守恒不等于能量守恒或黏性耗散。未来必须按压力型、
黏性型和总修正分别报告功率/耗散诊断；若声称耗散，应另行证明相应项满足非正功率条件。Stage 02A
不赋予能量或熵稳定资格。

## 5. 拓扑前置条件

守恒审计必须在聚合前验证：

- duplicate edge = 0；
- nonreciprocal edge = 0；
- strict-support omission = 0；
- unexpected exterior edge = 0；
- reciprocal cutoff crossing 可发生，但两方向必须在同一状态下共同进入或退出；
- neighbor graph hash、reciprocal status 与 topology defects 必须记录。

拓扑失败的样本不能借反对称化后处理获得“守恒合格”标签。

## 6. 未来验收量

至少记录 correction total force、相对总力残差、最大 pair antisymmetry residual、局部 pair torque、
PIO power、压力/黏性分项功率，以及 baseline 与 correction 分离后的诊断。具体数值容差留待 Stage 02B
依据精度与平台合同冻结，本阶段不调参。
