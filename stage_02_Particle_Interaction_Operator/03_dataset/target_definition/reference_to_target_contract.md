# Stage 02B Reference-to-Target Contract

**合同性质：** 数据协议定义；不生成 reference、trajectory、frame 或标签。  
**继承依据：** Stage 02A PIO 数学定义、reference hierarchy 与 error decomposition contract。

## 1. 冻结目标

对同一粒子状态 \(\mathcal S_t\) 和冻结邻域图 \(\mathcal G_t\)，baseline 为

\[
a_{\mathrm{SPH},i}=\mathcal A_{\mathrm{SPH}}(\mathcal S_t,\mathcal G_t)_i,
\]

reference 为

\[
a_{\mathrm{ref},i}=\mathcal A_{\mathrm{ref}}(\mathcal S_t;i),
\]

数据目标严格冻结为

\[
\boxed{\Delta a_i=a_{\mathrm{ref},i}-a_{\mathrm{SPH},i}}.
\]

机器可读符号必须是 `a_ref_minus_a_sph`。禁止交换符号、用不同状态的 trajectory 差分冒充瞬时目标，
或直接把 \(a_{\mathrm{corr}}\) 定义为标签。未来每个 frame 必须逐粒子、逐分量复核
`delta_a == a_ref - a_SPH`，复核容差和 dtype 必须在生成前写入 campaign manifest。

## 2. 同状态与同合同要求

形成候选差值前，以下身份必须一致或给出可审计、预先批准的对齐证明：

- 位置、速度、密度、压力、质量、支撑和平滑长度；
- 物理时刻、单位、坐标/周期代表元和 minimum-image convention；
- EOS、声速、kernel、支撑规则、forcing 与物理参数；
- baseline RHS/source identity、数值 dtype 和 configuration hash；
- neighbor graph hash 及 topology status。

另一条 trajectory 上“接近”的状态不满足同状态合同。R2 可用于量化状态/时间误差，但不能通过插值后静默
替换 `state_hash`。

## 3. Reference class 与 target 用途

| class | 定义 | `delta_a` 的允许角色 | 未来训练资格 |
|---|---|---|---|
| `R1_continuum_compatible` | analytic/MMS，连续模型与冻结 WCSPH/EOS/forcing 合同相容 | verification；在同状态和误差归因通过后构造候选 discretization target | 条件允许 |
| `R2_semidiscrete_qualified` | qualified high-order temporal/semidiscrete reference | 隔离 time error、state drift 和空间平台；提供资格证据 | 本合同下默认 `diagnostic`，不直接作为主空间标签 |
| `R3_independent_benchmark` | 与训练构造隔离的 shear/acoustic 或其他独立 benchmark | validation only | 默认 `diagnostic` 且 `training_permitted=false` |
| `RX_model_form_misaligned` | continuous model 与冻结 SPH contract 不一致 | diagnostic of mismatch | `rejected` |

`reference_class` 是强制字段。R1 的“continuum-compatible”必须由 configuration-specific model-form
checklist 证明，不因解析性自动成立。R2/R3 若未来要改变角色，必须建立新版本合同和新的独立验证资产；
不得在数据生成后依据结果回溯改类。

## 4. 误差归因门

候选差值必须附带

\[
e_{\mathrm{total}}=e_{\mathrm{space}}+e_{\mathrm{time}}+e_{\mathrm{reference}}
+e_{\mathrm{forcing}}+e_{\mathrm{model\_form}}+e_{\mathrm{cross}}
\]

的分项状态。只有 `target_component_attribution=discretization_attributed`，且 time/reference/forcing/
model-form/cross 项已 `isolated`、`bounded` 或 `not_applicable`，才可继续训练资格判断。不能把全部
continuum–SPH 差异或单一 total error 直接命名为 discretization target。

## 5. Validation 隔离

R3 默认不进入未来训练、归一化统计、阈值选择或超参数选择。Shear/acoustic 必须保留完整类别，或在数据生成
前冻结严格未见参数范围；二者只能选择一种明确策略并写入 split manifest。查看 R3 结果后不得重新划分。

## 6. Stage 01 边界

本合同保持 Stage 01G `V2_QUALIFICATION_FAIL`、shear failure 的 **finite-resolution dominant** 诊断以及
**viscosity operator form NOT CONFIRMED**。有限分辨率诊断不证明修正可学习，且不授权改写 Stage 01。
