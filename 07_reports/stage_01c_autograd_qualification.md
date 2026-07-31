# Stage 01C 原生 PyTorch 自动微分资格报告

## 1. 资格结论

**PASS — 仅限固定邻居索引、固定几何的原生 PyTorch value path。**

最终矩阵包含 4 个参数、每个参数 1/3/5/8/16 步，共 20 个案例。20 行的
AD 梯度和中心有限差分（FD）梯度均有限，AD 梯度均非零，CSV `status`
均为 `PASS`。预登记要求使用 AD–FD 阈值的 1/3/5/8 步案例中，最大相对差
为 \(1.6190767\times10^{-5}\)，低于门槛 \(10^{-2}\)。四个 16 步案例
也均无异常、有限且非零；按照预登记，16 步 AD–FD 差异只作诊断，不参与
短步阈值判定。

机器可读结果：
`06_experiments/stage_01c_autograd/results/native_autograd_fd.csv`。

本结论不认证邻居拓扑可微性，也不认证完整 SPH 求解器的端到端可微性。

## 2. 预登记条件

预登记文件
`06_experiments/stage_01c_autograd/configs/preregistered_autograd.yml`
在查看本组原生自动微分结果前冻结了以下条件：

- \(16^2\) 粒子，5% 抖动，种子 20261001；
- 周期域 \([-1,1]^2\)，支撑半径与粒子间距之比为 4；
- `float64`，时间步长 \(10^{-4}\)；
- 步数为 1、3、5、8、16；
- 损失为 `mean(final_velocity^2)`；
- 四个参数分别为物理运动黏度、初始速度幅值、第 0 个粒子的局部 x
  速度和第 0 个粒子的局部压力；
- 四个参数的中心有限差分步长均为 \(10^{-6}\)；
- 1/3/5/8 步要求 AD、FD 有限、AD 非零且最大相对差不超过 0.01；
- 16 步要求无异常、有限且非零，AD–FD 差异只作诊断；
- 不声明拓扑可微性。

相对差按

\[
\frac{|g_{\mathrm{AD}}-g_{\mathrm{FD}}|}
{\max(|g_{\mathrm{AD}}|,|g_{\mathrm{FD}}|,10^{-12})}
\]

计算。

## 3. 被认证的计算路径

实现位于
`01_solver/structure_preserving/native_autograd_ops.py`。该路径使用项目自有
守恒压力/黏性算子和原生 PyTorch 张量运算，并通过
`torch.autograd.grad` 求导；它不调用 diffSPH 的自定义 Laplacian
backward。

邻域只在 rollout 前构建一次。整个 1/3/5/8/16 步过程中：

- 邻居索引固定；
- 粒子位置及由其确定的几何量固定；
- 密度不演化；
- 压力不随时间演化；
- 只有速度值通过显式 Euler 诊断步更新。

局部压力案例改变的是固定压力输入中第 0 个粒子的值；该压力在时间步之间
仍保持不变。因此这里认证的是连续变量穿过固定算子图的 value path，而不是
位置、密度、压力或邻域拓扑演化的完整求解过程。

## 4. AD–FD 完整结果

下表逐项列出
`06_experiments/stage_01c_autograd/results/native_autograd_fd.csv` 的 20 个
案例。`finite/nonzero` 分别表示该行数值检查通过以及 AD 梯度非零。

| 参数 | 步数 | AD 梯度 | FD 梯度 | 相对差 | finite / nonzero | 状态 |
|---|---:|---:|---:|---:|:---:|:---:|
| `physical_viscosity` | 1 | -3.4651963765e-3 | -3.4651963798e-3 | 9.4894059e-10 | True / True | PASS |
| `physical_viscosity` | 3 | -1.0392701421e-2 | -1.0392701422e-2 | 2.1953153e-11 | True / True | PASS |
| `physical_viscosity` | 5 | -1.7316357560e-2 | -1.7316357570e-2 | 5.7738271e-10 | True / True | PASS |
| `physical_viscosity` | 8 | -2.7694628667e-2 | -2.7694628646e-2 | 7.6847495e-10 | True / True | PASS |
| `physical_viscosity` | 16 | -5.5327740606e-2 | -5.5327740611e-2 | 1.0043058e-10 | True / True | PASS |
| `initial_velocity_amplitude` | 1 | 9.9966594056e-1 | 9.9966594055e-1 | 4.6189606e-12 | True / True | PASS |
| `initial_velocity_amplitude` | 3 | 9.9938878455e-1 | 9.9938878448e-1 | 6.7581503e-11 | True / True | PASS |
| `initial_velocity_amplitude` | 5 | 9.9911170553e-1 | 9.9911170554e-1 | 9.8320981e-12 | True / True | PASS |
| `initial_velocity_amplitude` | 8 | 9.9869623131e-1 | 9.9869623124e-1 | 6.7250176e-11 | True / True | PASS |
| `initial_velocity_amplitude` | 16 | 9.9758914619e-1 | 9.9758914612e-1 | 6.9842647e-11 | True / True | PASS |
| `local_velocity_x_particle_0` | 1 | 1.5009368658e-3 | 1.5009368748e-3 | 5.9699668e-9 | True / True | PASS |
| `local_velocity_x_particle_0` | 3 | 1.5003100435e-3 | 1.5003100429e-3 | 3.8997139e-10 | True / True | PASS |
| `local_velocity_x_particle_0` | 5 | 1.4996834450e-3 | 1.4996834607e-3 | 1.0511135e-8 | True / True | PASS |
| `local_velocity_x_particle_0` | 8 | 1.4987439669e-3 | 1.4987439623e-3 | 3.1028143e-9 | True / True | PASS |
| `local_velocity_x_particle_0` | 16 | 1.4962411519e-3 | 1.4962411587e-3 | 4.5721654e-9 | True / True | PASS |
| `local_pressure_particle_0` | 1 | 1.0115954318e-6 | 1.0115797089e-6 | 1.5542679e-5 | True / True | PASS |
| `local_pressure_particle_0` | 3 | 3.0341221176e-6 | 3.0340729928e-6 | 1.6190767e-5 | True / True | PASS |
| `local_pressure_particle_0` | 5 | 5.0557634598e-6 | 5.0557891207e-6 | 5.0755538e-6 | True / True | PASS |
| `local_pressure_particle_0` | 8 | 8.0865660485e-6 | 8.0865869556e-6 | 2.5854071e-6 | True / True | PASS |
| `local_pressure_particle_0` | 16 | 1.6158977473e-5 | 1.6158963057e-5 | 8.9218170e-7 | True / True | PASS |

## 5. 门槛汇总

| 参数 | 1/3/5/8 步最大相对差 | 与 0.01 门槛比较 | 16 步 AD | 16 步 FD | 16 步 finite / nonzero |
|---|---:|:---:|---:|---:|:---:|
| `physical_viscosity` | 9.4894059e-10 | PASS | -5.5327740606e-2 | -5.5327740611e-2 | True / True |
| `initial_velocity_amplitude` | 6.7581503e-11 | PASS | 9.9758914619e-1 | 9.9758914612e-1 | True / True |
| `local_velocity_x_particle_0` | 1.0511135e-8 | PASS | 1.4962411519e-3 | 1.4962411587e-3 | True / True |
| `local_pressure_particle_0` | 1.6190767e-5 | PASS | 1.6158977473e-5 | 1.6158963057e-5 | True / True |
| **全部短步案例** | **1.6190767e-5** | **PASS** | — | — | — |

16 步四行在 CSV 中的 `AD_FD_threshold_applies` 均为 `False`。表中仍列出
AD 和 FD，便于诊断，但其相对差不用于替代预登记的 16 步
finite/nonzero/no-exception 门槛。

## 6. 可执行测试证据

`tests/test_stage01c_native_autograd.py` 中的
`test_native_autograd_matrix_meets_preregistered_gate` 对同一生成函数执行
以下检查：

- 恰有 20 行，并覆盖四个参数及 1/3/5/8/16 五种步数；
- 每行 `status == "PASS"`、`finite is True`、`nonzero is True`；
- AD 与 FD 梯度均有限，AD 梯度范数大于零；
- 1/3/5/8 步相对差不超过 0.01；
- 每行 `topology_differentiability_claimed is False`。

该测试直接调用
`01_solver/structure_preserving/native_autograd_ops.py` 中的
`run_native_autograd_matrix()`；最终 CSV 是同一 20 案例矩阵的持久化证据。

## 7. 明确不在资格范围内的声明

本报告不作以下声明：

- 不声明离散邻居搜索、边集合变化或邻居拓扑对位置可微；
- 不声明周期折返、支撑域进入/退出或邻居重建事件可微；
- 不声明位置、密度或压力演化路径已通过 AD–FD；
- 不声明可对完整 SPH 求解器进行端到端反传；
- 不声明本 value-path 结果验证了长时间稳定性、守恒精度或物理收敛性。

`topology_differentiability_claimed=False` 已逐行写入最终 CSV。此次 PASS
应始终附带“原生 PyTorch、固定邻居索引与固定几何、仅连续值路径”这一
限定语。

## 8. 最终判定

在预登记的 float64、固定邻域和固定几何条件下，项目自有原生 PyTorch
压力/黏性 value path 对四个参数均取得有限、非零的 1/3/5/8/16 步 AD
梯度；短步 AD–FD 最大相对差满足 0.01 门槛，16 步也满足
finite/nonzero/no-exception 门槛。因此该**有限范围的 value-path 自动微分
资格为 PASS**。

该结论不能扩展为拓扑可微或完整求解器已认证。
