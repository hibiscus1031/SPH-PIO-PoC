# Stage 01F5-Q 完整执行包

## Bundle v3

`stage01f5_execution_bundle_v3.json` 的 `schema_version` 为 3。它引用：Stage 01F5 commit `ca297db…`、Stage 01F5-P commit `38487d6…`、原 64 行矩阵和扩展 69 行矩阵 SHA-256、horizon amendment、21 点共同时间、31 行 binding、N64 DAG、dry-resolution audit，以及 T/P/H/S/安全门的 canonical hashes。

执行前数值源代码 commit 冻结为 `38487d66b40fa2c8dd65eb7aa6c279da4a8e5e2c`；Stage 01F5-Q 只新增元数据，没有改动 numerical source tree。

## 69 行 dry resolution

Dry audit 仅解析配置，不调用 solver。每行均唯一给出 run ID、solution、N、`H/dx`、执行类型、条件状态、输出目录、时域合同、dt/resolver、步数或参考积分合同、共同时间合同、依赖前驱和参数来源优先级。

解析结果：31 条正式空间相关运行绑定到 `0.02`/21 点；两条 N64 smoke 绑定到 20-step 派生时域；其余 36 条 N20/N28 相关运行保持 `0.015`/16 点。69 行全部 `RESOLVED`，无 null、implicit default 或 unresolved placeholder，69 个输出目录唯一。

## 门与矩阵身份

Stage 01F5-P v2 矩阵 SHA-256 仍为 `ebbfa5fd…`，未被修改。T1–T5、P1–P3、H1–H5、S1–S4 和 hard-safety 分别按 canonical JSON 保存 hash；N64 trigger、DOP853 容差、主配置、held-out 与 run ID 均未改变。

该 bundle 只使执行参数清单达到可申请状态，不启动 Stage 01F5B，也不生成任何资格结果。
