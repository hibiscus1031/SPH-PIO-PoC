# Stage 01F5 未来运行矩阵

## 规模

机器可读矩阵共冻结 64 行、64 个唯一 run ID 和 64 个唯一未来输出目录。其中无条件计划 62 行，条件 N64 为 2 行。

无条件组成：主参考 6、主 RK2 10、held-out 参考 6、held-out RK2 10、空间时间步隔离 4、正式空间 RK2 8、确定性重复 6，以及 MMS-B 四个空间分辨率各三层的连续参考 12。

## 时间矩阵

主配置和 held-out 各对 MMS-A/MMS-B 使用五级 `dt`。每条轨迹在 16 个精确共同时间评价 endpoint vector-L2 与 integrated vector-RMS；不允许插值。

## 空间分支

正式空间行的 `time_control` 固定为 `SPACE_STEP_DECISION`。它不是可自由调节的占位符，而是唯一引用 immutable `space_step_decision.json`：若 N32 两个候选时间步的任一字段相对变化大于 0.10，则选择 `3.125e-5`，否则选择 `6.25e-5`。该文件必须在 N16/N24/N48 正式运行前提交且以后不可修改。

N64 两行标记为 conditional，仅允许由四个预注册 trigger 之一启动，并必须先通过专用资源与 cutoff 预审。

## 输出与重复

每个 future output directory 固定为 `06_experiments/stage_01f5b_requalification_execution/runs/<run_id>`。六个 `_rep2` ID 明确引用其原始 parent run，参数必须完全继承。

完整逐行清单位于 `06_experiments/stage_01f5_requalification_design/manifests/stage01f5_run_matrix.csv`。本报告所称“运行”均为未来计划；Stage 01F5 实际运行数为 0。
