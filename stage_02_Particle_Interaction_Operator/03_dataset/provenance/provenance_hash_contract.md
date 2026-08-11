# Stage 02B Provenance and Hash Contract

**性质：** 未来记录身份协议；不计算实际样本 hash，不创建 manifest。

## 1. 三个强制内容身份

所有未来 frame 必须使用 `sha256:<64 lowercase hex>`：

- `state_hash`：覆盖物理时刻、dimension、particle count、canonical particle order、positions、velocities、
  density、pressure、mass、support/smoothing length、units、dtype 和 byte order；
- `configuration_hash`：覆盖 baseline/reference source identity、EOS、kernel、support、neighbor search、forcing、
  physical parameters、precision、integrator/state-alignment 配置及配置 schema version；
- `neighbor_graph_hash`：覆盖 canonical sorted directed edges、reciprocal pair identity、minimum-image displacement、
  MI/tie-breaking convention、support rule、dtype 和 graph serialization version。

浮点近似相等不得共享 content hash。若未来需要近似/同族检索，应另设 lineage/group id。

## 2. Canonical serialization

版本冻结为 `pio-canonical-bytes-1.0.0`。数组必须记录 shape、dtype、little/big endian 和 C-order；字符串使用
UTF-8；对象键按字节序排序；整数使用固定宽度；缺失值不得与空数组或零混同。particle canonical order 必须
与 `particle_id_local` bookkeeping 分离，且粒子 ID 不成为模型特征。

任何 serialization 变更必须升级版本并产生新 hash；不得覆盖旧身份。

## 3. Source provenance

至少记录 baseline source id、reference source id、configuration source id、software environment id、hardware
device id、resource policy id、determinism policy id、schema/rules/split policy versions 和 evidence URIs。若代码目录
无 commit identity，必须使用不可变制品 hash；文件名或“latest”不是有效 identity。

## 4. Lineage 与失败保留

frame、trajectory、initial condition、resolution、\(H/dx\)、disorder、deterministic repeat 和 derived
neighborhood view 都必须具有父子 lineage。重试/修复生成新 identity，不能覆盖失败记录。failure flags、原始
退出状态、resource/topology/determinism 证据与 eligibility reason codes 必须保留。

## 5. No-overwrite 与 split identity

未来 manifest 必须只增版本并包含自身内容 hash。split assignment 与 policy hash 绑定；在 validation/test/R3
结果出现后不得就地改分。Stage 02B 不创建任何实际 manifest、run id、state hash 或样本记录。
