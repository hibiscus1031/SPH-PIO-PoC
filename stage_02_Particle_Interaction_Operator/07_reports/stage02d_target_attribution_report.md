# Stage 02D — Target Attribution Qualification Report

**范围：** 审计 Stage 02C 既有 R2 records；无 dataset expansion、split、模型、训练或性能评价。

## 1. Stage 02C data boundary

输入固定为 `stage02c_r2_audit_scale_20260804`：3 cases、3 R2 reference records、6 samples；原 verdict 为4
diagnostic、2 topology rejected、0 eligible。Stage 02D 未修改这些 sample、manifest 或 verdict。

## 2. R2 reference identity

唯一 reference 为 `stage02c_r2_dense_all_pairs_dop853_v1`。`a_ref` 是同一 RK2 state 上的 dense all-pairs
semidiscrete RHS；DOP853 primary/sensitivity 只提供 temporal qualification。R1/R3 未加入。

## 3. State/config/time/graph alignment

Same state、same configuration 和 same timestamp 均为6/6 PASS。Same graph contract 为4/6 PASS；2个预注册
duplicate-edge controls 预期 FAIL。因此4个正控制满足完整 alignment，2个负控制保持 rejected。详见
`stage02d_state_alignment_audit.md`。

## 4. Temporal contamination

DOP853 primary/sensitivity acceleration 的 L2、Linf 与 relative magnitude 在本批次均观测为0；RK2-vs-DOP853
acceleration Linf 在 final time 为约 `2.99e-7` 和 `1.31e-6 m s^-2`。由于正控制 target 为零且没有预冻结
smallness threshold，不能判断 \(\Delta a_{time}\ll\Delta a\)。

## 5. Reference uncertainty

Dense forward/reverse difference 为 `1.11e-16`–`2.22e-16 m s^-2`，低于预冻结 float64 audit bound；DOP853
sensitivity、assembly sensitivity 和 time-state sensitivity 分列报告，没有 single total uncertainty，也没有
noise augmentation。详见 `stage02d_reference_sensitivity.md`。

## 6. Error decomposition

逐样本账本覆盖 space/time/reference/forcing/model-form/cross，每项含 status/evidence/uncertainty/confidence。
Space 与 cross 未识别；model-form 只证明 R2 内部一致；forcing 为零且匹配。结论是4 diagnostic、2 rejected，
而不是 all difference = discretization error。

## 7. Discretization attribution

六分量 score 包括 spatial consistency、resolution trend、support consistency、time contamination、reference
sensitivity 和 model-form compatibility。当前没有 PASS candidate：

- resolution 只有 N6 regular 与 N8 jitter，resolution/disorder 混杂；
- H/dx 只有2.6；
- topology-qualified `delta_a` 全为零，smooth trend/stable direction/non-random structure 均无法由 assembly
  identity 推断；
- continuum-compatible spatial reference 未提供。

Cross-resolution 状态为 `INSUFFICIENT_EVIDENCE_FOR_RESOLUTION_DEPENDENT_CORRECTION`。

## 8. Label upgrade rule

升级要求 reference class、same-state、uncertainty、model-form、topology、resource、determinism、discretization
attribution 和 leakage 九门全部 PASS。R2 不能自动升级；hard failure 优先保持 rejected。详见
`stage02d_label_upgrade_rules.md`。

## 9. Stage 02E decision

现有数据不允许 Stage 02E 数据资格升级：`stage02e_data_qualification_upgrade_authorized=false`。该决定不表示
Stage 02D 未完成，而表示归因审计完整地发现证据不足。

## 10. Historical boundary

Stage 01G 保持 `V2_QUALIFICATION_FAIL`；Stage 01H 保持 `FINITE_RESOLUTION_DOMINANT`；viscosity operator form
failure 保持 `NOT CONFIRMED`。Stage 01H diagnosis 未被写成 operator corrected。
