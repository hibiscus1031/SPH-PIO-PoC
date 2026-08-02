# Stage 01F4 前瞻性重资格协议

## 1. 执行前冻结

本阶段只批准协议，不执行数值矩阵。任何未来运行开始前，必须在独立设计提交中冻结：主配置、至少 5 级按 2 倍细化的 `dt`、共同物理时间、精确解参数、参考设置、运行 ID、资源上限、条件分支和代码 SHA-256。不得使用插值制造共同时间点。

Stage 01F3B/F3C 的轨迹只可作为协议背景，不能计入新资格的误差点、参考、重复或 held-out。

## 2. 时间与平台路径

每条主配置需建立 production sparse RHS 的 baseline/tighter/third 半离散参考。position 与 velocity 的端点和 integrated-RMS 必须同时通过 T1–T5；total exact error 只通过 P1–P3 评价。交叉项、余弦和平台接近方向必须报告，但不设同号门。

## 3. 空间门

正式空间路径沿用 Stage 01F3B 已证明可执行的 increasing-neighbor consistency path：

| N | H/dx |
|---:|---:|
| 16 | 4.06155281280883 |
| 24 | 4.5 |
| 32 | 5.049509756796392 |
| 48 | 5.5 |
| 64（条件） | 6.041381265149109 |

position、velocity、density、pressure 均必须满足：最细端点优于最粗端点、四级 L2 严格逐级下降、global log-log slope 为正。该结果只能称为 increasing-neighbor path 的路径阶，不能称为 fixed-stencil 单参数 `h` 阶。

GCI 按变量分别资格化。每个变量只有在存在单调三层子序列、局部阶同号、相邻局部阶相对变化不超过 25%、误差高于参考 floor 20 倍且不同三点选择的阶次变化不超过 25% 时，才允许报告 observed order 和 GCI。fixed-ratio family 仅用于 quadrature-floor 诊断，不能通过正式空间门。

N64 只有在 N16–N48 非单调、N48/N32 误差比超过 `0.95` 或局部阶不清楚时才触发，并必须先通过资源和 cutoff-margin 预审。

## 4. 新 held-out

至少一个未产生过轨迹或参考数据的新配置必须在运行前封存。本协议封存：`N=28`、`H/dx=4.75`、`t_final=0.015`、`dt=[1e-3,5e-4,2.5e-4,1.25e-4,6.25e-5]`；最大无插值共同时间点数为 16。

该配置的数据未参与本协议阈值选择。Held-out 只要求：资格化半离散参考、position/velocity time error 下降、fitted order 至少 `1.80`、最细平台距离和 time/space 比均不超过 1%，以及 source、守恒、topology、reference、resource、determinism 全部通过。

Held-out 不要求交叉项与主配置同号，不要求从平台同一方向逼近，也不要求 total exact error 严格单调。

## 5. 硬安全门

未来每条轨迹必须保持 start/midpoint 两次 source 调用，pair/internal/assembly/momentum 残差、viscous power、最小间距、reciprocal topology、RSS、步时稳定性、子进程回收和父进程 scalar-only 边界均使用已冻结的 Stage 01F3B 量级门限。任何硬安全失败均阻止重资格，不得由平台解释覆盖。

## 6. 防止事后调参

- 协议提交和 SHA-256 在运行前冻结。
- 精确主矩阵在另一个设计提交中一次性冻结后才能运行。
- 新数据可见后不得删门、放宽阈值、更换主范数或改变 held-out。
- 排除规则、reference floor、N64 条件和失败处理必须预登记。
- 旧轨迹不能补足新矩阵缺失点。
- 本批准只允许申请一次全新重资格运行设计；不直接生成 Stage 01G、V2、V3 或 Stage 02 资格。

## 7. 一次性状态规则

- `PLATEAU_AWARE_PROTOCOL_APPROVED`：旧 CT2 不适合作为未来必要条件，且 T/P/空间/held-out/安全与防事后规则完整。
- `PLATEAU_AWARE_PROTOCOL_REJECTED`：旧 CT2 应保留为未来必要条件，或新协议降低验证严格性。
- `PROTOCOL_ADJUDICATION_INCOMPLETE`：公式、判据、held-out 或 provenance 不完整。

本阶段不依据任何新数值运行作判断。
