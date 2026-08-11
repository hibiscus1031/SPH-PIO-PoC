# Stage 02 Dataset Design

**状态：DESIGN ONLY / NO DATA GENERATED**  
**目标：为未来 \(\Delta\mathbf a=\mathbf a_{ref}-\mathbf a_{SPH}\) 数据集定义合同、模式、切分和质量门。**

## 1. 数据集用途

数据集服务于 particle interaction correction operator，而不是端到端替代 SPH。每个合格样本必须同时保存 baseline SPH 输入/输出、独立参考、修正标签和资格证据，使任一预测都能回退到并比较于未修改的 SPH 基线。

当前文件只设计 schema；不得运行求解器、生成轨迹、写入样本、创建标签或统计数据分布。

## 2. 样本单位

建议支持两级样本：

1. **Frame sample**：同一物理时刻的完整粒子图，用于全局守恒和图级审计；
2. **Neighborhood view**：从 frame 派生的中心粒子及其邻域视图，用于批处理，但必须携带原 frame id，避免同一 frame 跨 split。

禁止把单个 edge 作为没有 frame/trajectory 归属的独立随机样本，因为这会破坏守恒配对和造成严重泄漏。

## 3. 输入字段

### 3.1 粒子字段

- `particle_id_local`：仅用于 frame 内关联，不可作为模型特征；
- positions（unwrapped 与 periodic-evaluation 版本分开）；
- velocities、densities、pressures、masses、supports；
- baseline SPH acceleration 及可审计的 pressure/viscosity/source 分量；
- solution/benchmark、physical time、resolution、layout、seed、dtype、device 元数据。

### 3.2 Pair / edge 字段

- directed row/col 与 reciprocal pair id；
- minimum-image displacement、distance、normalized distance；
- relative velocity、kernel value、radial gradient coefficient、support；
- cutoff-event flags、reciprocity、duplicate、strict-support omission 和 structural-defect flags；
- edge count、neighbor-count summary 和 topology identity/event summary。

### 3.3 参考与标签字段

- `a_ref`、`a_sph`、`delta_a`；
- reference class、solver/method、tolerances、sensitivity estimates；
- `reference_uncertainty`（按分量/范数）；
- time/space/forcing/model-form attribution flags；
- label qualification status 与 exclusion reason。

## 4. 标签定义

主标签严格为同状态差值：

\[
\Delta\mathbf a_i=\mathbf a_{ref,i}(\mathcal S_t)
-\mathbf a_{SPH,i}(\mathcal S_t,\mathcal G_t).
\]

“同状态”要求位置、速度、密度、压力、质量、物理时间和物理参数一致。参考若通过另一条轨迹生成，必须在目标状态上重新评价加速度，不能直接用不同状态的时间差分近似并称为同状态标签。

标签至少分为：

- `QUALIFIED_DISCRETIZATION_TARGET`；
- `REFERENCE_UNCERTAINTY_TOO_LARGE`；
- `MODEL_FORM_MISALIGNMENT`；
- `TEMPORAL_ERROR_NOT_ISOLATED`；
- `TOPOLOGY_STRUCTURAL_FAIL`；
- `RESOURCE_OR_EXECUTION_FAIL`；
- `NONFINITE`；
- `PROVENANCE_INCOMPLETE`。

只有第一类可进入未来主训练集；其他类别保留元数据但默认不进入模型拟合。

## 5. 候选覆盖矩阵（仅设计）

未来协议可覆盖：

- solution family：WCSPH-compatible MMS-A / MMS-B；
- independent holdout family：source-free shear 与 acoustic；
- resolution：在已验证的 N16/N24/N32/N48 范围内设计，N64 需独立资源授权；
- support path：increasing-neighbor consistency path 与 fixed-ratio diagnostic 分开；
- layout：regular、5% jitter、10% jitter；
- physical parameters：低马赫、正密度、已验证黏度/EOS 范围；
- time sampling：按 trajectory 分组并使用预冻结 physical times。

该矩阵没有 run ID、样本数量或阈值；这些只能在未来数据协议中前瞻性冻结。

## 6. 切分与泄漏防护

### 6.1 分组层级

切分单位从强到弱依次为：benchmark/solution family、initialization/seed family、trajectory、resolution/support family、frame。任何更高层单位被分到验证/测试后，其下全部样本必须随之隔离。

### 6.2 禁止方式

- 不得随机拆分同一 trajectory 的相邻 frames；
- 不得把同一 frame 的不同中心粒子分到不同 split；
- 不得让 deterministic repeat 分跨 train/test；
- 不得用验证/测试结果选择参考容差、标签门或 benchmark 参数；
- 不得把 Stage 01G 独立门全部吸收到训练数据后仍称其为独立验证。

### 6.3 建议 held-out

至少保留一个全新 resolution/support 组合、一个完整 jitter seed family、一个物理参数区间以及一个 source-free benchmark family。最终选择必须在数据生成前冻结。

## 7. 归一化与无量纲化设计

候选尺度包括 \(H\)、\(c_s\)、\(\rho_0\)、\(U_{ref}\) 和局部 kernel scale。归一化参数必须只由训练 split 或预定义物理常数得到；禁止使用测试标签统计量。所有量同时保存 SI/原始数值与无量纲版本的变换元数据，以便反算和审计。

## 8. 质量门

每个 frame 的未来硬门至少包括：

- 全部字段 finite；
- 正质量、正密度、合法 support；
- duplicate/nonreciprocal/strict-support omission/unexpected edge 为零；
- baseline source/force assembly 身份通过；
- reference sensitivity 和 uncertainty 合格；
- `delta_a == a_ref - a_sph` 在冻结容差内逐位复核；
- pair bookkeeping 可重建质量加权总修正；
- child process、resource、determinism 与 provenance 完整；
- 配置、代码、输入、输出 hash 完整且 no-overwrite。

如果 GCI 前置条件不满足，只能记录 `GCI not justified`，不能用虚构 GCI 通过质量门。

## 9. 文件组织与版本合同

未来物化时建议采用只增不改的版本目录：

```text
dataset_version/
  manifest/
  frames/
  splits/
  quality/
  provenance/
  reports/
```

每个 frame 单独或分片存储，并由 manifest 给出内容 hash、schema version、source commit、reference identity、split assignment 和资格状态。原始失败证据不得删除；修复或重试必须使用新 run/frame id。

## 10. 数据审计报告要求

未来数据集报告必须给出：合格/排除数量及原因；各 split 的 solution、resolution、layout、seed、time 和 target magnitude 分布；参考不确定性；守恒与拓扑统计；重复/近重复检查；资源与确定性；失败与限制；训练未启动声明。

## 11. 当前验收

- 数据目标与同状态合同已定义；
- schema、参考分类、切分、泄漏防护和质量门已起草；
- 未创建任何 run matrix、样本、轨迹、标签或模型输入文件；
- 未运行 SPH、参考求解器、Transformer 或训练。

当前状态：`DATASET_DESIGN_DRAFT_COMPLETE`。该状态不授权 dataset generation。
