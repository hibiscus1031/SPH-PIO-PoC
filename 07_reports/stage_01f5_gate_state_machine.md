# Stage 01F5 门与状态机

## 主时间门 T1–T5

`e_time=q_RK2-q_semidiscrete` 必须逐向量直接计算，禁止由两个标量误差相减。position/velocity 在 endpoint vector-L2 与 16-time integrated vector-RMS 上分别通过：逐级严格下降；global fitted order `>=1.80`；最细三层两个局部阶中位数在 `[1.70,2.30]`；每组合至少 4 点高于匹配 reference floor 20 倍；successive-dt self-difference 最细/最粗比 `<=0.30`。任一失败均阻止 PASS。

## 平台门 P1–P3

`e_space=q_semidiscrete-q_exact`，`e_total=q_RK2-q_exact`。对 position/velocity 和两种共主范数，P1 要求 `abs(E_total_finest-E_space)/E_space<=0.01`，P2 要求 `E_time_finest/E_space<=0.01`。P3 要求全部 total exact error finite，且 `max(E_total)/max(E_total_coarsest,E_space)<=2.0`。

进入平台后不要求 total exact error 严格单调。cross term、cosine 与平方范数重构必须报告但符号不是资格门；不得为旧 CT2 增加百分比容差。

## 安全与确定性硬门

所有未来数值轨迹必须在独立子进程中使用默认 cyclic GC 和 `torch.no_grad()`，时间循环内禁止 `gc.collect()`；父进程只接收标量树与相对路径，子进程必须完全回收，每步 source 恰好在 start/midpoint 调用。

冻结门限包括：pair-force `<=1e-12`，normalized internal-force、assembly、momentum defect 各 `<=1e-10`，viscous positive tolerance `<=1e-12`，structural defects `=0`，minimum separation/dx `>=0.25`，current RSS `<2 GB`，peak RSS `<4 GB`，RSS Q4-Q1 增量 `<=250 MB` 且相对增量 `<=50%`，step-time Q4/Q1 `<=1.30`。合法 reciprocal crossing 和 edge identity count 大于 1 不单独构成失败。

六条 `_rep2` 必须与原运行的 scalar summary、positions、unwrapped positions、velocities、densities、pressures、masses 和 topology event-sequence hash bitwise identical。

## 状态机

- `PLATEAU_AWARE_REQUALIFICATION_DESIGN_APPROVED`：冻结、novelty、run IDs、门、条件分支、零运行与 provenance 全部完整。只允许申请 Stage 01F5B。
- `PLATEAU_AWARE_REQUALIFICATION_DESIGN_REJECTED`：设计降低 Stage 01F4 严格性、主/held-out 不独立、允许旧数据或允许运行后改门。
- `REQUALIFICATION_DESIGN_INCOMPLETE`：矩阵、参考、分支、判据或 provenance 不完整。

本阶段唯一状态为 `PLATEAU_AWARE_REQUALIFICATION_DESIGN_APPROVED`。这不是执行授权，也不生成 V2、Stage 01G、V3 或 Stage 02 资格。
