# 完整假设演化登记

## H01 高分辨率 SPH 可自动作为真值。

- 状态：`FALSIFIED`
- [PROJECT_EVIDENCE] 证据/限制：Stage01与Stage02显示离散、时间、quadrature与模型形式污染必须分离。
- [INFERENCE] 后继假设：候选reference必须独立资格化。
- 禁止回溯改写：不得用后续局部PASS覆盖该条历史状态。

## H02 WCSPH 与不可压 TGV 在当前设置中模型形式一致。

- 状态：`LIMITED/FALSIFIED_IN_SCOPE`
- [PROJECT_EVIDENCE] 证据/限制：Stage01E EOS初始化残差主导，比例由机器记录给出。
- [INFERENCE] 后继假设：采用WCSPH-compatible MMS与source-free独立验证。
- 禁止回溯改写：不得用后续局部PASS覆盖该条历史状态。

## H03 static pair-force correction 在合格架构下可学习。

- 状态：`NOT_QUALIFIED`
- [PROJECT_EVIDENCE] 证据/限制：Stage02M/M-Q中K1/K2 train-fit硬门未整体通过。
- [INFERENCE] 后继假设：转向局部因果动态训练假设。
- 禁止回溯改写：不得用后续局部PASS覆盖该条历史状态。

## H04 regularity 可作为dataset hard gate。

- 状态：`FALSIFIED`
- [PROJECT_EVIDENCE] 证据/限制：v0.1–v0.4出现false positive、cross-mode与invariance失败；路线终止。
- [INFERENCE] 后继假设：regularity仅作diagnostic，dataset eligibility由reference/target/conservation/lineage决定。
- 禁止回溯改写：不得用后续局部PASS覆盖该条历史状态。

## H05 attention优于MLP。

- 状态：`NOT_TESTED`
- [PROJECT_EVIDENCE] 证据/限制：K1/K2结构资格化不等于优越性；static fitting也未建立稳定优势。
- [INFERENCE] 后继假设：未来只可在公平D0–D3合同和合格训练后比较。
- 禁止回溯改写：不得用后续局部PASS覆盖该条历史状态。

## H06 optimization conditioning主导static fitting。

- 状态：`SUPPORTED_AS_DIAGNOSIS_NOT_GENERAL_LAW`
- [PROJECT_EVIDENCE] 证据/限制：Stage02M-R量化归因支持conditioning，但v0.2仍未资格。
- [INFERENCE] 后继假设：需新任务对齐、尺度与blind families检验。
- 禁止回溯改写：不得用后续局部PASS覆盖该条历史状态。

## H07 短时历史改善动态closure。

- 状态：`NOT_TESTED/GRADIENT_ATTENUATED`
- [PROJECT_EVIDENCE] 证据/限制：Stage03D history gradient 0/6；D-R观察到history influence强衰减。
- [INFERENCE] 后继假设：Stage04需local-causal/task-aligned可证伪合同。
- 禁止回溯改写：不得用后续局部PASS覆盖该条历史状态。

## H08 动态Transformer混合实现正确。

- 状态：`QUALIFIED_COMPONENT`
- [PROJECT_EVIDENCE] 证据/限制：Stage03C D0/zero-correction/checkpoint/one-step AD通过。
- [INFERENCE] 后继假设：实现正确不等于多步可微或训练有效。
- 禁止回溯改写：不得用后续局部PASS覆盖该条历史状态。

## H09 多步梯度可按360-probe合同资格化。

- 状态：`NOT_QUALIFIED`
- [PROJECT_EVIDENCE] 证据/限制：216 stable、144 failure；history 0/6；归因为mixed/unresolved。
- [INFERENCE] 后继假设：需新任务对齐梯度合同，不能后改epsilon门。
- 禁止回溯改写：不得用后续局部PASS覆盖该条历史状态。

## H10 动态训练资格已建立。

- 状态：`NOT_AUTHORIZED/NOT_EXECUTED`
- [PROJECT_EVIDENCE] 证据/限制：Stage03E=false；optimizer/training=0。
- [INFERENCE] 后继假设：Stage04必须独立进口新证据。
- 禁止回溯改写：不得用后续局部PASS覆盖该条历史状态。

## H11 Stage04 local-causal training能避开全局history梯度衰减并保持结构性质。

- 状态：`NOT_TESTED`
- [PROJECT_EVIDENCE] 证据/限制：仅为Stage04新假设，没有训练或rollout证据。
- [INFERENCE] 后继假设：以task-aligned gradient→training→rollout→validation顺序检验。
- 禁止回溯改写：不得用后续局部PASS覆盖该条历史状态。
