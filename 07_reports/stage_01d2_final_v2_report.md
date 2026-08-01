# Stage 01D2 final V2 report

正式配置：`06_experiments/stage_01d2_v2_requalification/configs/preregistered_stage01d2_v2.yml`（SHA-256 `87583422ddf81d1252a618cf87a57795097d2c519df1ded90d531c66ab2dcceb`）。分析时提交：`dc403e7df9d33b89080ef66a7703ca418bcc761c`。Stage 01D-P canary 使用数：`0`。

## 1. Stage 01D-P 冻结

P 状态 `POLICY_PASS_ISOLATED_DEFAULT_GC`；tag 固定于 `e8e50ad4cd3b3cccc273870bd9372f62e266edae`。

## 2. 历史失败状态

Stage 01D 及 R–R5 的失败/诊断状态全部保留，未追溯修改。

## 3. 正式资源运行政策

独立子进程、默认 GC、no_grad、checkpoint-only；campaign_index 记录 PID、回收和父进程增长。

## 4. Canary 排除证明

正式数据中 Stage 01D-P canary 行数为 `0`。

## 5. 固定物理方程和参数

二维周期 TGV，rho0=1、U0=1、L=2、nu=0.02、Re=100、主 c_s=20、float64 CPU；Stage 01C 压力/黏性与 midpoint RK2 未改。

## 6. Prerequisite

状态 **PASS**，pytest 与身份、zero-flow、smoke、守恒、资源、回收均有机器证据。

## 7. 时间误差

T1–T4：T1=PASS, T2=PASS, T3=PASS, T4=PASS。

## 8. 空间误差

S1–S6：S1=PASS, S2=PASS, S3=PASS, S4=PASS, S5=PASS, S6=PASS；条件 N48 完成但 velocity L2=`0.019456041`，未消除非单调性；GCI not justified。

## 9. 支撑族比较

constant 与 increasing 两族均按预登记矩阵报告误差、成本、edge count 和 RSS。

## 10. 动态无序

唯一子判定 **D_FAIL**。

## 11. Mach/模型形式

三条完成=PASS，密度 non-worsening=PASS。

## 12. 动态守恒

硬门 **PASS**；角动量仅作诊断。

## 13. AD 回归

20/20，**PASS**；拓扑选择不可微。

## 14. 资源使用

全部接受轨迹资源与子进程回收总门 **FAIL**。

## 15. 数值不确定性

时间、空间、Mach、无序、support、舍入与 CPU 确定性已区分；GC 不作物理误差。

## 16. 所有失败和限制

6/6 jitter 均完成数值轨迹，但 RSS 首末四分位相对增量为 `54.9%–61.7%`，超过 50% 硬门；5% jitter 因而失败，不能降级为 D_CONDITIONAL。10% jitter median velocity-error multiplier=`9.338`。空间主序列及 N48 仍非单调；evidence_complete=True。

## 17. 唯一 Stage 01D2 状态

**STAGE01D2_V2_REQUALIFICATION_FAIL**

## 18. 是否具备申请 V3 的资格

否；只有无条件 PASS 才可申请。

## 19. Stage 02 边界

Stage 02 未开始；V3、网络训练、学习标签与高保真资格均未启动。
