# Stage 01B 不确定性评估

## 评估边界

本评估只使用 Stage 01B 已生成的 V1 算子、邻域、守恒、积分器和自动微分
证据。V1 未通过，固定物理量 TGV 的 V2 时间/空间收敛试验均未运行。因此，
下文区分“已量化的 V1 诊断量”和“尚未估计的 V2 不确定度”，不把缺失数据
解释为零不确定度。

## 不确定性清单

| 来源 | 当前证据 | 可否量化为 V2 TGV 不确定度 | 当前判断 |
|---|---|---|---|
| 离散算子 | 规则布局的物理-\(\nu\) Laplacian L2 误差随 \(16^2,24^2,32^2\) 从 3.80765 降至 1.79038、1.04049；10% 无序则为 4.30739、3.01780、3.27669 | 否 | 对粒子无序敏感，最高分辨率出现反弹 |
| 时间离散 | 独立标量 ODE 的 `symplecticEuler` 观测阶为 2.073、2.036、2.018 | 否 | 只验证 ODE 接口；没有耦合 TGV \(\Delta t\) 序列 |
| 空间离散 | 仅有 V1 制造解算子三分辨率数据；没有固定-Re TGV 响应量 | 否 | TGV 空间误差、外推值与空间 GCI 未估计 |
| 粒子无序 | 每个无序等级只有一组固定种子布局；10% 无序核零阶矩和 Laplacian 均在 \(32^2\) 变差 | 否 | 可确认敏感性，不能给出随机分布或置信区间 |
| float32 与重复性 | V1 SPH 算子路径为 CPU/float32；布局状态有 SHA256；守恒残差中可见 float32 尺度项 | 否 | 输入可追溯，但没有独立重复运行或 float64 对照来分离舍入误差 |
| 弱可压缩性/模型形式 | 预登记 \(U_0=1,c_s=10\)，仅给出名义初始 \(Ma=0.1\)；V2 未运行 | 否 | 运行时 Mach、EOS/密度扩散/粒子移动相对不可压 TGV 的模型误差均未估计 |
| 自动微分 | 物理 \(\nu\) 与局部初速度两参数各做 3/5/8 步，共 6 行；AD 均为 FAIL/NaN，有限差分均为 PASS 且非零 | 否 | AD 不可用，不能与有限差分做一致性比较 |
| 黏性与压力守恒 | 5% 密度扰动时黏性归一化总内力残差约为 0.00575–0.0110；混合符号压力在无序布局也有非零残差 | 否 | 变密度黏性与符号切换压力存在模型/离散守恒风险 |

离散算子、时间积分与守恒数值分别来自：

- `06_experiments/stage_01b_operator_verification/results/manufactured_operator_metrics.csv`；
- `06_experiments/stage_01b_operator_verification/results/integrator_order.csv`；
- `06_experiments/stage_01b_operator_verification/results/conservation_audit.csv`。

粒子布局种子、状态哈希和邻域拓扑记录在：

- `06_experiments/stage_01b_operator_verification/results/layout_hashes.csv`；
- `06_experiments/stage_01b_operator_verification/results/neighborhood_audit.csv`。

自动微分结构化结果保存在
`06_experiments/stage_01b_operator_verification/results/autograd_scope.csv`，
6 组完整脱敏异常栈保存在
`06_experiments/stage_01b_operator_verification/logs/autograd_scope_failures.txt`。
首次三步失败的原始保留记录
`06_experiments/stage_01b_operator_verification/logs/autograd_multistep_failure.txt`
也未删除。异常发生于固定物理 \(\nu\) 前向算子之后的上游自定义 backward；
没有修改第三方包来掩盖该失败。

## 离散与粒子无序

规则布局的制造解 gradient、divergence 和 Laplacian 误差总体随分辨率下降，
但这不足以建立对无序粒子稳健的渐近区间。关键反例是：

- 10% 无序核零阶矩 L2：
  0.0179112→0.0176247→0.0191465；
- 10% 无序 Laplacian L2：
  4.30739→3.01780→3.27669；
- 10% 无序 Laplacian 的最后一段观测阶为 -0.28609。

这些数值分别记录在
`kernel_moment_metrics.csv` 和 `manufactured_operator_metrics.csv`。
`layout_hashes.csv` 证明各布局输入可复现，但每个 5%/10% 无序等级只有一个
确定性实现。它不能代表粒子无序总体，也不能提供均值、方差或置信区间。

上游默认 `verletScale=1.4` 在 \(16^2\) 规则布局出现 5,552 条重复边；限定
为 1.0 后该布局重复边为 0。完整对照在
`upstream_default_neighbor_diagnostic.csv`。这说明邻域实现参数本身也是显著
的离散不确定性来源；当前限定值虽消除了已识别的重复边，却没有消除高无序
算子反弹。

## 时间与空间不确定度

独立 ODE 检查支持 `symplecticEuler` 接口在该测试方程上的约二阶行为，但
耦合 WCSPH 中的压力、密度扩散、黏性、邻域更新和粒子移动会改变误差传播。
由于没有固定空间分辨率的多 \(\Delta t\) TGV 数据，时间截断误差和时间
不确定度均未估计。

同理，没有固定物理参数、对齐终止时刻的多分辨率 TGV 数据。V1 制造解误差
不是 TGV 响应量的空间误差代理，不能用于估算 TGV 的空间不确定度。

## 数值精度与重复性

V1 SPH 操作路径的预登记配置为 CPU/float32；独立 ODE 积分器阶数检查使用
float64。守恒 CSV 中规则、均匀密度情况下约 \(10^{-8}\) 量级的归一化总
内力残差与 float32 舍入量级相容，但这不能把所有更大的残差归因于舍入：
5% 密度扰动黏性残差达到约 \(5.75\times10^{-3}\) 至
\(1.10\times10^{-2}\)，高出多个数量级。

现有状态哈希只保证保存的输入布局身份可核查。当前没有同一配置的多次独立
运行、CPU 与 MPS 逐轨迹对照或 float32/float64 SPH 对照，因此：

- 不报告随机重复性标准差；
- 不报告后端差异置信区间；
- 不把单次确定性结果解释为统计不确定度。

## 弱可压缩性与模型形式

预登记值 \(U_0=1,c_s=10\) 只建立名义初始 \(Ma=0.1\)。由于 V2 未运行，
没有运行时最大 Mach、密度波动或声学 CFL 轨迹，因而不能量化弱可压缩
WCSPH 相对不可压缩解析 TGV 的偏差。

尚未量化的模型形式来源还包括等温 EOS、DeltaSPH 密度扩散、粒子移动、
Antuono 压力离散和项目物理-\(\nu\) 通用 Laplacian 适配器。尤其是后者虽
将显式 \(\nu\) 线性乘到官方通用 Laplacian 上，但
`conservation_audit.csv` 显示变密度状态下 pair-force residual 与总内力
残差非零。因此，物理参数“固定”不等于离散模型已经物理等价或守恒。

## 自动微分不确定性

`results/autograd_scope.csv` 对两个参数分别记录了 3/5/8 步固定邻居索引值
路径，共 6 行。两参数是物理黏度 `physical_viscosity` 和第 0 个粒子的局部
初速度 x 分量 `local_velocity_x_particle_0`。6 行总体状态和 AD 状态均为
`FAIL`，`autograd_gradient`、`gradient_norm` 和 `relative_difference`
均为 NaN。异常一致为
`TypeError: unsupported operand type(s) for *: 'float' and 'NoneType'`，
完整脱敏栈指向上游 generic Laplacian 自定义 backward，并保存在
`logs/autograd_scope_failures.txt`。

有限差分是独立完成的敏感性检查，6 行状态均为 `PASS` 且梯度非零：

- 物理 \(\nu\) 的 3/5/8 步有限差分梯度分别为
  -0.0138581、-0.0230968、-0.0370294；
- 局部初速度 x 分量的 3/5/8 步有限差分梯度均为 -0.000745058。

这些非零有限差分结果说明损失对两个参数的值路径存在可测敏感性，但 AD
梯度缺失，因而不能计算 AD–有限差分相对差，也不能做一致性判定。由此：

- 不能报告 3/5/8 步 AD 梯度范数为有效数值；
- 不能把有限差分单独通过表述为 AD 通过；
- 不能把 Stage 01 的较短或不同值路径梯度结果外推到本固定物理-\(\nu\)
  多步路径；
- 未对第三方源码打补丁，因此该失败被保留为已知实现不确定性。

## GCI 适用性判定

**GCI not justified（不具备计算或报告 GCI 的依据）。**

理由是：

1. 没有 V2 固定-Re TGV 的三组时间步长或三组空间分辨率响应量；
2. V1 的 10% 无序 Laplacian 序列在最高分辨率反弹，未展示稳定渐近区间；
3. 粒子无序只有单一固定实现，没有足够统计样本；
4. 变密度黏性守恒、混合符号压力守恒和多步 AD 均存在未解决失败；
5. 弱可压缩模型形式误差尚未由运行时 Mach、密度波动或与参考解比较量化。

因此，本阶段不计算时间 GCI、空间 GCI 或合成数值不确定度。当前可以可靠
报告的是各 V1 诊断量和失败边界，而不是一个总百分比。

## 总结

Stage 01B 的不确定性状态是“存在已观测的算子、无序、守恒和 AD 风险，
而 TGV 时间/空间与模型形式不确定度尚未估计”。这与零不确定度或条件通过
不同。V1 门控关闭 V2 是为了避免在空间算子尚未资格化时生成表面上的时间/
空间收敛率。
