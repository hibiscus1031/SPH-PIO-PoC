# Stage 01F2 short rollout

下表只报告 implementation smoke 的最终诊断，不用于不同 N 或 dt 之间的精度推断。

| run | pos rel L2 | vel rel L2 | rho rel L2 | min sep/dx | peak RSS MB | time Q4/Q1 |
|---|---:|---:|---:|---:|---:|---:|
| A1 | 2.4516e-5 | 9.2986e-3 | 4.1977e-4 | 0.9999 | 262.8 | 0.999 |
| A2 repeat 1 | 3.3943e-5 | 5.0871e-3 | 1.1982e-4 | 0.9999 | 370.7 | 1.002 |
| A2 repeat 2 | 3.3943e-5 | 5.0871e-3 | 1.1982e-4 | 0.9999 | 363.5 | 1.002 |
| B1 | 2.4533e-5 | 6.6257e-3 | 4.2232e-4 | 0.9700 | 265.2 | 0.996 |
| B2 repeat 1 | 3.3980e-5 | 3.6530e-3 | 1.2120e-4 | 0.9399 | 368.5 | 1.014 |
| B2 repeat 2 | 3.3980e-5 | 3.6530e-3 | 1.2120e-4 | 0.9399 | 367.3 | 1.005 |

所有 sampled state 与 exact/reference state 均 finite；topology defects 为 0；内部守恒、外力动量更新、source contract、误差灾难阈值和资源门全部通过。每条轨迹在独立子进程内使用默认 cyclic GC 与 `torch.no_grad()`，循环内未调用 `gc.collect()`，子进程均完全回收。

结论：A1/A2/B1/B2 code-path verification **PASS**。
