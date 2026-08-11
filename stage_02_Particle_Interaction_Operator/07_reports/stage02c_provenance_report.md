# Stage 02C — Provenance Report

机器证据见 `../03_dataset/manifests/` 与 `../03_dataset/audits/provenance_audit.json`。

## 1. Identity coverage

每个 sample 包含：

- `state_hash`：canonical particle state；
- `configuration_hash`：case + frozen generation configuration；
- `neighbor_graph_hash`：edge arrays、minimum-image/support/topology metadata；
- baseline/reference source SHA-256；
- software/hardware、resource policy、determinism policy 与 evidence URIs；
- eligibility rules version、verdict 和 reason codes。

6/6 state hashes、graph hashes、sample file hashes和 provenance required fields 复核 PASS。3/3 reference file
hash、DOP853 solver status和 R2 identity 复核 PASS。

## 2. Pipeline hashes

Configuration、SPH state generation、R2 reference evaluation、delta computation、eligibility engine 和 sample
storage 六步均具有 SHA-256 output hash 且 status PASS。Dataset manifest 保存 sample/reference Merkle-style roots，
`sample_hashes.sha256` 保存逐文件摘要。

## 3. Determinism and resource

完整对象在写盘前生成两次并进行 canonical byte comparison，结果 bitwise equal。运行采用 CPU float64，3 cases
共耗时约1.96 s，未越过60 s stopline；粒子数和 edge 数均未越过预冻结审计规模。资源状态只表示该 audit run
完成，不构成训练规模资格。

## 4. Failure retention

Attempt 01 的 manifest timestamp serialization failure 被保留为 infrastructure FAIL；删除其不完整部分输出后，
Attempt 02 只修复字符串类型并成功。该受控重试没有改变科学配置或数值方法。两个 topology negative-control
records 也原样保留为 rejected。

## 5. Historical boundary

Stage 01 文件只读。`V2_QUALIFICATION_FAIL`、shear finite-resolution dominant 和 viscosity operator form
NOT CONFIRMED 均写入 run manifest，未被本次数据审计重新解释。
