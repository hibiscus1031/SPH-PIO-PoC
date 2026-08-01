# Stage 01D2 protocol and provenance

正式配置：`06_experiments/stage_01d2_v2_requalification/configs/preregistered_stage01d2_v2.yml`（SHA-256 `87583422ddf81d1252a618cf87a57795097d2c519df1ded90d531c66ab2dcceb`）。分析时提交：`dc403e7df9d33b89080ef66a7703ca418bcc761c`。Stage 01D-P canary 使用数：`0`。

Stage 01D-P 预注册提交为 `5fd5a56720dc7cfe32180e06ca6946f0082ec56f`，最终证据提交及冻结 tag 目标为 `e8e50ad4cd3b3cccc273870bd9372f62e266edae`；冻结状态为 `POLICY_PASS_ISOLATED_DEFAULT_GC`。R5 tag 目标为 `f4262b71d1f5fb4763535a34e8187c1b1e02bcaa`。`stage01dp_frozen_sha256_manifest.csv` 逐项复核了五份报告、状态、配置和机器证据，原文件未改动。

每条前向轨迹由 `run_stage01d2_campaign.py` 启动独立子进程；worker 全程采用默认 cyclic GC 和 `torch.no_grad()`，父进程只记录标量摘要与相对路径。Stage 01D-P 三条 canary 只构成资源政策依据，未复制、未拟合、未重复。

历史结论保持冻结：Stage 01D=`V2_FAIL`，R=`RESOURCE_FAIL_LINEAR_GROWTH`，R2=`ATTRIBUTION_UNRESOLVED`，R3=`R3_CONFIRMATION_UNRESOLVED`，R4=`R4_RETENTION_REDETECTED`，R5=`R5_BOUNDED_GC_DELAY_CONFIRMED`，P=`POLICY_PASS_ISOLATED_DEFAULT_GC`。
