# Stage 01F3-R cutoff 光滑性审计

## 结论

冻结的 Wendland C4 核及实际 pressure/viscosity 粒子对表达式在 `q=r/H=1` 处通过审计。左侧粒子对加速度随 `q→1-` 消失，`q>=1` 时显式为零；没有可观测有限跳跃。

## 解析检查

冻结核形函数为

`W = 9/(pi H^2) (1-q)^6 (1+6q+35q^2/3)`（`q<1`），支撑外为零；其径向导数正比于 `q(5q+1)(1-q)^5`。因此 `W` 与 `dW/dr` 的左极限均为零，并与支撑外零值连接；`grad W` 同样趋于零。冻结 pressure pair force 线性依赖 `grad W`，viscosity coefficient 通过 `r·grad W` 进入，故 pressure force、viscosity coefficient 与 viscosity force 均在 cutoff 消失。

## float64 数值探针

| q | W | dW/dr | pressure pair L2 | viscosity coefficient | viscosity pair L2 | pair acceleration L2 |
|---:|---:|---:|---:|---:|---:|---:|
| 0.9999 | 2.139e-22 | -2.566e-17 | 1.002e-23 | 2.053e-18 | 3.817e-22 | 2.384e-20 |
| 0.999999 | 2.139e-34 | -2.567e-27 | 1.003e-33 | 2.053e-28 | 3.818e-32 | 2.384e-30 |
| 0.99999999 | 2.139e-46 | -2.567e-37 | 1.003e-43 | 2.053e-38 | 3.818e-42 | 2.384e-40 |
| 0.9999999999 | 2.139e-58 | -2.567e-47 | 1.003e-53 | 2.053e-48 | 3.818e-52 | 2.384e-50 |
| 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 1.0000000001 | 0 | 0 | 0 | 0 | 0 | 0 |
| 1.00000001 | 0 | 0 | 0 | 0 | 0 | 0 |
| 1.000001 | 0 | 0 | 0 | 0 | 0 | 0 |
| 1.0001 | 0 | 0 | 0 | 0 | 0 | 0 |

`q=1-1e-10` 的左极限探针加速度贡献为 `2.384e-50`，右侧为零，数值跳跃量即该趋零余量。全部九点中的最大探针值为 `2.384e-20`（位于最远的 `q=1-1e-4`）。函数值和一阶导数连续性检查均通过。

Dense 路径采用严格 `r<H`；生产 sparse 邻域可能保留机器精度 tolerance shell 内的 `r=H` 边，但核、梯度和实际 pair term 均为零，因此 inclusion convention 不改变聚合 RHS。

证据：`06_experiments/stage_01f3r_reference_qualification/results/cutoff_smoothness.csv` 与 `cutoff_smoothness_summary.json`。
