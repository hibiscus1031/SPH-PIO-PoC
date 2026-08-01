# Stage 01D-P Evidence-horizon Audit

## R5 冻结

R5 最终证据提交为 `f4262b71d1f5fb4763535a34e8187c1b1e02bcaa`；annotated tag `stage-01dr5-bounded-gc-delay-confirmed` target 为 `f4262b71d1f5fb4763535a34e8187c1b1e02bcaa`；状态 `R5_BOUNDED_GC_DELAY_CONFIRMED` 保持不变。

## 只读 SHA-256 复核

| evidence | expected SHA-256 | observed SHA-256 | pass |
|---|---|---|---|
| stage01d_primary_config | 7fa2dd01f7c9a493958fc3732a776e919077479d5c91baad345f172f177f6da0 | 7fa2dd01f7c9a493958fc3732a776e919077479d5c91baad345f172f177f6da0 | True |
| r5_gc_mode_summary | 4b9f36d36c300112753cd4745fea266510afb1500df3294997c4b01c4349d178 | 4b9f36d36c300112753cd4745fea266510afb1500df3294997c4b01c4349d178 | True |
| r5_retired_slot_summary | 207a48abc25995fe5220a66bf5778929842e7c1bf21a94f6ccd98a58b6e6977b | 207a48abc25995fe5220a66bf5778929842e7c1bf21a94f6ccd98a58b6e6977b | True |
| r5_numerical_regression_summary | 8c8ce2c07313519c0a089e5f337b335e4212330e78af7ca7264dda62517e0f62 | 8c8ce2c07313519c0a089e5f337b335e4212330e78af7ca7264dda62517e0f62 | True |
| r5_status | 2d69c898fc0d42618b605d2bcf4a47d39715e981336e15313a586319aee3b3f7 | 2d69c898fc0d42618b605d2bcf4a47d39715e981336e15313a586319aee3b3f7 | True |

## 步数计算与证据覆盖

明确计算：`0.2 / 0.000125 = 1600 steps`。

| source | t_final | minimum dt | steps | repeats | pass |
|---|---|---|---|---|---|
| Stage 01D primary/time-convergence configuration | 0.2 | 0.000125 | 1600 | n/a | True |
| Stage 01D-R5 G1 default-GC evidence | n/a | n/a | 2000 | 3 | True |

R5 default-GC 证据长度为 2000 steps，大于计划最大单轨迹 1600 steps；旧 R5 状态未重新计算。
