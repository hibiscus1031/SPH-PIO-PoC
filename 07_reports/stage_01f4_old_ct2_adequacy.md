# Stage 01F4 旧 CT2 充分性与必要性审计

## 冻结范围

Stage 01F3B 的历史状态固定为 `MMS_CONVERGENCE_VERIFICATION_FAIL`；Stage 01F3C 的状态固定为 `CT2_MIXED_OR_UNRESOLVED`。本审计只判断旧 CT2 是否适合继续充当未来协议的时间收敛必要条件，不重算、不放宽、也不重新分类旧 CT2。

## 误差对象

在固定空间离散、固定粒子标识和共同物理时刻上，定义

\[
e_{\mathrm{total}}(\Delta t)=u_{\mathrm{RK2}}(\Delta t)-u_{\mathrm{exact}},
\]

\[
e_{\mathrm{space}}=u_{\mathrm{semi}}-u_{\mathrm{exact}},\qquad
e_{\mathrm{time}}(\Delta t)=u_{\mathrm{RK2}}(\Delta t)-u_{\mathrm{semi}}.
\]

因此逐向量严格满足

\[
e_{\mathrm{total}}=e_{\mathrm{space}}+e_{\mathrm{time}},
\]

以及

\[
\lVert e_{\mathrm{total}}\rVert^2=
\lVert e_{\mathrm{space}}\rVert^2+
\lVert e_{\mathrm{time}}\rVert^2+
2\langle e_{\mathrm{space}},e_{\mathrm{time}}\rangle.
\]

时间积分器收敛要求 `||e_time(dt)|| -> 0` 并表现出预期阶次；它不要求 `||e_total(dt)||` 从某一固定方向接近 `||e_space||`。后者还取决于误差向量夹角。

## 旧 CT2 不是必要条件

取二维向量

\[
e_{\mathrm{space}}=(1,0),\qquad e_{\mathrm{time}}(\Delta t)=(-\Delta t^2,0).
\]

此时时间误差严格二阶收敛：`||e_time||=dt² -> 0`。但在 `0<dt<1` 时

\[
\lVert e_{\mathrm{total}}\rVert=1-\Delta t^2.
\]

随着 `dt` 细化，该总误差反而严格增大并从平台下方趋近 1。于是“连续精确解总误差随 dt 细化严格非增”不是时间收敛的必要条件。

## 旧 CT2 也不能单独充分证明时间收敛

取

\[
e_{\mathrm{space}}=(0,0),\qquad e_{\mathrm{time}}(\Delta t)=(c+\Delta t^2,0),\quad c>0.
\]

总精确误差随 `dt` 细化严格下降，但趋向非零常数 `c`；数值轨迹并未收敛到半离散解。因此只观察 total exact-error monotonicity 不能代替半离散时间误差的下降、阶次、参考不确定度和 self-difference 证据。

## 四个必须分开的概念

- `time-integrator convergence`：固定空间离散后，`e_time` 随 `dt` 下降并达到预期阶次。
- `total exact-error monotonicity`：`e_total` 的标量范数趋势，受空间误差和交叉项共同控制。
- `spatial-platform entry`：最细总误差接近 `e_space`，且剩余 `e_time` 相对平台足够小。
- `error-vector alignment`：`<e_space,e_time>` 的符号和大小，解释从平台上方或下方接近，但不属于时间阶的必要条件。

Stage 01F3C 中主配置与 held-out 的交叉项方向不同，正是这一区分的实证说明；这些旧数据仅用于审计协议充分性，不能充当未来重资格的新运行证据。

## 审计结论

旧 CT2 不适合作为未来时间收敛的必要条件，也不适合作为独立充分条件。未来协议应直接检验 `e_time`，并将 total exact error 降为独立的平台进入与有界性门。Stage 01F3B 的旧 CT2 形式失败保持原样。
