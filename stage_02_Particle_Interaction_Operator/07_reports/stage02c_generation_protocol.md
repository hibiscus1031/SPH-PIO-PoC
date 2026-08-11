# Stage 02C — Controlled Generation Protocol

## 1. Scope

本协议只授权 `stage02c_r2_audit_scale_20260804` 的审计级数据生成。它不授权模型、Transformer、attention、
optimizer、training、split assignment、normalization statistics、validation 或 performance evaluation。

## 2. Frozen pipeline

```text
configuration
  -> SPH state generation
  -> R2 reference evaluation
  -> delta_a computation
  -> eligibility engine
  -> sample storage
```

每一步在 `../03_dataset/manifests/generation_run_manifest.json` 中记录 `status`、`output_hash` 和 provenance；
configuration 额外记录 case/config/schema/rules/source 输入哈希。

## 3. Numerical construction

- domain：二维单位周期盒；CPU float64；
- initial state：预定义低 Mach 周期涡旋及轻微密度扰动；
- baseline state generation：固定步长 explicit midpoint RK2，`dt=5e-4`，输出 `t=0` 与 `t=0.002`；
- SPH：二维 cubic-spline kernel，linear isothermal EOS，pressure 与对称黏性 pair 项；
- baseline acceleration：manifest graph 上的 sparse directed-edge assembly；
- R2 acceleration：同一 RK2 state 上的 dense all-pairs semidiscrete assembly；
- temporal qualifier：SciPy DOP853 primary/sensitivity 两个容差层；
- target：逐粒子 `delta_a = a_ref - a_SPH`，字符串固定为 `a_ref_minus_a_sph`。

该实现是 Stage 02C 独立 audit pipeline，不声称复现已丢失的 Stage 01 原始执行代码。其 R2 身份限于
same-semidiscrete dense assembly 与 DOP853 temporal qualifier，全部记录保持 diagnostic/rejected，不能升级为
空间训练标签。

## 4. Determinism and no-overwrite

生成器在写盘前对完整科学对象执行两次 in-memory generation，并要求 canonical bytes bitwise identical。
本次 determinism PASS。所有目标文件在写入前必须不存在；重试不得覆盖已有成功产物。

## 5. Transaction history

首次执行完成数值对象后，在 manifest canonical hashing 处因 YAML timestamp 被解码为 `datetime` 而失败。部分
样本/reference 输出被明确删除，随后仅把 timestamp 改为字符串；数值方法、case、阈值和 reference 均未修改。
第二次执行 PASS。两次 attempt 均保存在 generation run manifest，首次失败未被隐藏。

## 6. Materialized output

本次生成3个 reference records、6个 frame samples、2个 manifests、一个 SHA-256 清单和4个自动 audit JSON。
规模仅用于验证 pipeline/schema/hash/eligibility，不是训练规模。
