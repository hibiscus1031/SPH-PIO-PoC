# Stage 01F4 Plateau-aware 指标

## 评价对象

下一次重资格必须先固定一个全新的主配置，并为同一空间离散建立三层资格化半离散参考。对 position 和 velocity，在端点 vector-L2 与无插值共同时间 integrated vector-RMS 两种共主范数上分别评价。

时间误差直接定义为

\[
e_t(\Delta t)=q_{\mathrm{RK2}}(\Delta t)-q_{\mathrm{semi}},
\]

而空间平台误差与总精确误差分别为

\[
e_s=q_{\mathrm{semi}}-q_{\mathrm{exact}},\qquad
e_{\mathrm{tot}}=q_{\mathrm{RK2}}-q_{\mathrm{exact}}.
\]

不得通过两个标量误差相减构造时间误差。

## 主要时间门 T1–T5

| gate | 前瞻性规则 |
|---|---|
| T1 | position/velocity 的 endpoint-L2 和 integrated-RMS time error 在每次 `dt` 二分时均严格下降。 |
| T2 | 每个字段、每个共主范数的全局 log-log fitted order 均不低于 `1.80`。 |
| T3 | 最细三个可用层级形成的两个局部阶，其中位数必须位于 `[1.70,2.30]`。 |
| T4 | 每个字段、每个共主范数至少有 4 个误差点高于匹配 reference uncertainty floor 的 20 倍。 |
| T5 | successive-dt self-difference 对 position/velocity 和两种范数显著收缩，最细与最粗 self-difference 之比不超过 `0.30`。 |

局部阶定义为

\[
p_k=\frac{\log(E_k/E_{k+1})}{\log(\Delta t_k/\Delta t_{k+1})}.
\]

参考不确定度按字段和范数取 `max(baseline-tighter, tighter-third)`，不可用单一全局常数代替。

## 平台门 P1–P3

| gate | 前瞻性规则 |
|---|---|
| P1 | 对 position/velocity 和两种共主范数，`abs(E_total,finest-E_space)/E_space <= 0.01`。 |
| P2 | 对相同字段和范数，`E_time,finest/E_space <= 0.01`。 |
| P3 | 所有 total exact errors 必须 finite，且 `max(E_total)/max(E_total,coarse,E_space) <= 2.0`。进入平台区后不要求严格单调。 |

P1–P3 不能反向替代 T1–T5。平台接近只说明总误差已由空间误差主导，不证明时间误差具有正确阶次。

## 向量对齐的地位

余弦、交叉项和平方范数重构仍必须报告，用于解释误差从平台上方或下方接近。但交叉项符号不参与主时间资格；否则同一个二阶积分器可能仅因空间与时间误差方向改变而得到相反判定。

## 参考资格

半离散参考必须使用 production sparse RHS 和非项目 RK2 的高阶积分器，完成 baseline/tighter/third 三层敏感性、至少 10 个状态的 sparse/dense acceleration 抽查、finite 与 reciprocal topology 审计。不得要求 edge identity 恒定。

## 与旧 CT2 的关系

本协议没有给旧 CT2 增加百分比容差，也没有把其历史失败改写为通过。旧 CT2 保留为 Stage 01F3B 的历史判据；T/P 门是只适用于未来新数据的新协议。
