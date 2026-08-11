# Stage 02E — Target Excitation Protocol

规范矩阵见 `../04_target_attribution/excitation_design/target_excitation_matrix.yaml`。

## 1. Frozen matrix

本次一次性枚举8个预注册 cases，不进行随机生成后筛选：

- resolution：N6×6、N8×8、N10×10，固定 H/dx=2.6、regular、periodic vortex；
- support：H/dx=2.2、2.6、3.0，固定 N8×8、regular、periodic vortex；
- disorder：regular、5% jitter（seed 5505）、10% jitter（seed 5510），固定 N8×8、H/dx=2.6；
- state：periodic vortex 与 compressive wave，固定 N8×8、H/dx=2.6、regular。

重叠 anchor `e_n8_h26_regular_vortex` 同时属于四条路径，使路径在同一配置交汇而无需复制记录。

## 2. Non-zero excitation construction

每个 case 用 DOP853 生成中心状态 \(S(t_c)\)，\(t_c=0.002\)。在该同一状态上评价 sparse SPH
instantaneous RHS；R2 reference 使用中心于 \(t_c\) 的五点速度导数：

\[
a_{ref}(t_c)\approx
\frac{v(t_c-2h)-8v(t_c-h)+8v(t_c+h)-v(t_c+2h)}{12h},
\qquad h=0.001.
\]

目标保持 \(\Delta a=a_{ref}-a_{SPH}\)。另用 \(h/2\) 与第二组 DOP853 tolerance 形成 reference sensitivity。
该构造旨在激发并辨别非零 candidate，不预设它是 spatial discretization。

## 3. Retention and scope

8/8 manifest cases 全部物化；没有删除小 target。本批次没有 zero target，但 Stage 02D 的4 diagnostic、2
rejected 和其中的 zero targets/拓扑失败保持原文件、reason code 和 provenance。Candidate pool 明确标记
`training_permitted=false`。
