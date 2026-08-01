# Stage 01D-R3 Cutoff-shell Audit

## R2 冻结

R2 运行前提交为 `084c702c6eab16b6983078494c01627fd2d8cfbe`，最终证据提交为 `39ae3dc1f88f4468d2a423cfad8c952a0a4da8d3`；annotated tag `stage-01dr2-attribution-unresolved-cutoff-topology` target 为 `39ae3dc1f88f4468d2a423cfad8c952a0a4da8d3`。R2 的 `ATTRIBUTION_UNRESOLVED` 保持不变。

## H/dx=5 壳层几何

N32 规则周期格点在 q=5 上有 12 个整数偏移：
`[[-5, 0], [-4, -3], [-4, 3], [-3, -4], [-3, 4], [0, -5], [0, 5], [3, -4], [3, 4], [4, -3], [4, 3], [5, 0]]`。因此初始 cutoff 壳层包含
`12288` 条 directed edges；float64 中初始
`min |r/H-1|=0.000e+00`。

## C1–C3 切换复核

R3 replay 得到 edge count `[82940, 82942, 82944]`，并与 R2 C1–C3 的
`135` 个采样行全部一致。发生切换的具体 keys：

| edge key | row | col | offset | shell | actions | min |r/H−1| |
|---|---|---|---|---|---|---|
| 11435 | 11 | 171 | (-5,0) | 5.0 | removed | 3.997e-15 |
| 16560 | 16 | 176 | (-5,0) | 5.0 | removed | 3.997e-15 |
| 175115 | 171 | 11 | (5,0) | 5.0 | removed | 4.219e-15 |
| 180240 | 176 | 16 | (5,0) | 5.0 | removed | 4.219e-15 |

所有切换均位于 q=5 壳层=`True`，全部满足预登记
`|r/H-1|≤1e-12`=`True`。这些是 cutoff inclusion 的
浮点切换，不称为物理粒子迁移。
