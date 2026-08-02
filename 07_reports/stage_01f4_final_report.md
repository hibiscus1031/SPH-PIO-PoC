# Stage 01F4 最终报告

## 1. Stage 01F3B/F3C 冻结

Stage 01F3C 最终证据提交固定为 `f831d4fa7d63ad3357e2b1e84c1260d7f3c46a2e`，annotated tag 为 `stage-01f3c-ct2-mixed-or-unresolved`，唯一状态保持 `CT2_MIXED_OR_UNRESOLVED`。16 项最终报告、evaluator、分解、held-out、参考和冻结证据的 SHA-256 全部复核通过。

Stage 01F3B 的历史状态仍为 `MMS_CONVERGENCE_VERIFICATION_FAIL`。本阶段未改动任何旧报告、数据、标签、判据或状态。

## 2. 旧 CT2 的数学充分性审计

由

\[
e_{\mathrm{total}}=e_{\mathrm{space}}+e_{\mathrm{time}}
\]

和

\[
\lVert e_{\mathrm{total}}\rVert^2=\lVert e_{\mathrm{space}}\rVert^2+\lVert e_{\mathrm{time}}\rVert^2+2\langle e_{\mathrm{space}},e_{\mathrm{time}}\rangle
\]

可知 total exact-error trend 不是 time error trend 的同义表达。构造 `e_space=(1,0)`、`e_time=(-dt²,0)` 可得到严格二阶时间收敛，同时总误差随细化增大；因此旧 CT2 不是必要条件。构造 `e_space=0`、`e_time=(c+dt²,0)` 可得到总误差随细化下降但时间误差不趋零；因此旧 CT2 也不是独立充分条件。

这一定理性审计不改变 Stage 01F3B 的旧 CT2 失败。

## 3. 时间误差与总误差的区别

未来时间资格直接比较项目 RK2 与资格化半离散参考，检验 `e_time` 的下降、全局阶、局部阶、reference floor 和 self-difference。total exact error 仅用于判断空间平台进入和有界性。误差向量交叉项只解释从平台上方或下方接近，不参与时间阶必要门。

## 4. Plateau-aware 主门

T1–T5 要求 position/velocity 在端点 L2 与共同时间 integrated RMS 上均下降、fitted order 至少 `1.80`、最细三层局部阶中位数位于 `[1.70,2.30]`、至少 4 点高于 20 倍参考 floor，且 successive-dt self-difference 最细/最粗比不超过 `0.30`。

P1–P3 要求最细 total error 距空间平台不超过 1%、最细 time/space 不超过 1%，并保持 finite 和预登记有界。平台内不要求 total exact error 严格单调，也不允许用百分比容差改写旧 CT2。

## 5. 空间门

正式空间验证沿用 increasing-neighbor consistency path。position、velocity、density、pressure 均须端点改善、逐级下降且 global slope 为正。GCI 按变量逐一资格化；fixed-ratio family 只作 quadrature-floor 诊断。任何路径阶均不得表述为 fixed-stencil 单参数 `h` 阶。

## 6. 新 held-out 规则

至少一个全新配置必须在运行前封存。本协议预先封存 `N=28`、`H/dx=4.75`、`t_final=0.015` 和五级时间步。Held-out 只检验半离散时间误差下降与阶次、平台接近和硬安全门；不要求交叉项同号、平台接近方向相同或 total exact error 单调。

## 7. 防止事后调参和旧数据复用

协议、阈值和 held-out 在新数据可见前冻结；未来精确主矩阵还须在独立设计提交中一次性冻结。Stage 01F3B/F3C 数据只能作为背景，不能计入新重资格。运行后不得删门、放宽阈值、改变范数、替换 held-out 或把旧轨迹补入新矩阵。

## 8. 唯一协议状态

`PLATEAU_AWARE_PROTOCOL_APPROVED`

旧 CT2 被认定不适合作为未来时间收敛必要条件；新时间、平台、空间、held-out、参考、硬安全和防事后门均已完整预注册。该状态不重新判定任何旧结果。

## 9. 全新重资格设计申请资格

具备申请一次全新重资格运行设计的资格。该资格只允许提交新的设计与预登记，不自动授权执行矩阵；本阶段没有启动 Stage 01F3D，也没有运行任何 SPH、DOP853、RK2 或收敛轨迹。

## 10. 下游仍未开始

Stage 01G、V3 和 Stage 02 仍未开始；未生成 V2、V3、Stage 01G 或 Stage 02 资格。训练和学习标签均未开始。
