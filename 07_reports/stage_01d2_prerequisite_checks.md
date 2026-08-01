# Stage 01D2 prerequisite checks

总状态：**PASS**。完整 pytest 返回码 `0`，原始日志为 `06_experiments/stage_01d2_v2_requalification/logs/full_pytest.log`。

- `explicit_midpoint_ode_evidence`: PASS
- `r5_tag_target`: PASS
- `stage01c_ad_baseline`: PASS
- `stage01c_disorder_design`: PASS
- `stage01c_manifest`: PASS
- `stage01d_primary_config`: PASS
- `stage01dp_manifest_rows_hash_match`: PASS
- `stage01dp_tag_target`: PASS

N16 zero-flow、20-step N16 与 N32 smoke 的逐点守恒、拓扑与资源证据位于 `run_summaries/` 和 `trajectory_samples/`；子进程回收证据位于 `results/campaign_index.csv`。
