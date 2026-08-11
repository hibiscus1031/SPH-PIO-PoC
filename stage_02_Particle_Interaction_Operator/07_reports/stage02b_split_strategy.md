# Stage 02B — Split Strategy Report

规范策略见 `../03_dataset/splitting/split_strategy.md`。

## 冻结原则

切分单位是 family，不是 frame。禁止 random frame split，也禁止以下泄漏：

- 同一 trajectory 的相邻或非相邻 frames 跨 split；
- 同一 frame 的粒子/neighborhood views 跨 split；
- initial-condition/seed lineage 或 deterministic repeats 跨 split；
- restart、resample、格式转换等直接派生记录跨 split；
- validation/test/R3 统计进入 normalization、uncertainty 门或规则选择。

## 强制 axes

协议显式覆盖 trajectory family、initial condition、resolution、\(H/dx\)、disorder、deterministic repeat 和
solution/benchmark family。泄漏图的 connected component 是最低原子单元；unseen resolution/support/disorder/
initial-condition 再按完整 family 施加 holdout。

## 隔离优先级

若同一候选命中多个区域，使用

`R3_independent_validation > future_test > future_validation > future_train`

的最严格优先级，且不得复制。R2/R3/RX 或资格未完成记录不会因 split assignment 获得训练资格。

## Shear/acoustic

每个 R3 benchmark 必须在生成前选择 whole-class holdout 或 strict-unseen-range holdout。严格未见范围需要在
参数轴和 trajectory/initial condition/resolution/\(H/dx\)/disorder/seed lineage 上均无交叉。查看结果后不能
重分。

本阶段未物化任何 split manifest 或样本 assignment。
