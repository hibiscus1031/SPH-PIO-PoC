# Stage 01D-R4 Control F Reference Identity

## 15 个 age-2 weakrefs

下表来自 canonical short replay F1。只输出类型名称，不输出 referrer 内容或用户路径。

| slot | object id | storage key | created | first | last | fixed edge | current | retired | different generation | referrer types |
|---|---|---|---|---|---|---|---|---|---|---|
| endpoint_neighborhood.col | 4437737712 | cpu:5639176192:663552 | 0 | 198 | 200 | True | True | False | False | ["FrozenReciprocalTopology","PeriodicNeighborhood"] |
| endpoint_neighborhood.domain_max | 4437673456 | cpu:5266941248:16 | 0 | 198 | 200 | False | True | False | False | ["DynamicSPHState","PeriodicNeighborhood"] |
| endpoint_neighborhood.domain_min | 4437674016 | cpu:5266317184:16 | 0 | 198 | 200 | False | True | False | False | ["DynamicSPHState","PeriodicNeighborhood"] |
| endpoint_neighborhood.particle_support | 4437549824 | cpu:4472066560:8192 | 0 | 198 | 200 | False | True | False | False | ["DynamicSPHState","PeriodicNeighborhood"] |
| endpoint_neighborhood.row | 4437738752 | cpu:4566351872:663552 | 0 | 198 | 200 | True | True | False | False | ["FrozenReciprocalTopology","PeriodicNeighborhood"] |
| midpoint_neighborhood.col | 4437737712 | cpu:5639176192:663552 | 0 | 198 | 200 | True | True | False | False | ["FrozenReciprocalTopology","PeriodicNeighborhood"] |
| midpoint_neighborhood.domain_max | 4437673456 | cpu:5266941248:16 | 0 | 198 | 200 | False | True | False | False | ["DynamicSPHState","PeriodicNeighborhood"] |
| midpoint_neighborhood.domain_min | 4437674016 | cpu:5266317184:16 | 0 | 198 | 200 | False | True | False | False | ["DynamicSPHState","PeriodicNeighborhood"] |
| midpoint_neighborhood.particle_support | 4437549824 | cpu:4472066560:8192 | 0 | 198 | 200 | False | True | False | False | ["DynamicSPHState","PeriodicNeighborhood"] |
| midpoint_neighborhood.row | 4437738752 | cpu:4566351872:663552 | 0 | 198 | 200 | True | True | False | False | ["FrozenReciprocalTopology","PeriodicNeighborhood"] |
| start_stage_neighborhood.col | 4437737712 | cpu:5639176192:663552 | 0 | 198 | 200 | True | True | False | False | ["FrozenReciprocalTopology","PeriodicNeighborhood"] |
| start_stage_neighborhood.domain_max | 4437673456 | cpu:5266941248:16 | 0 | 198 | 200 | False | True | False | False | ["DynamicSPHState","PeriodicNeighborhood"] |
| start_stage_neighborhood.domain_min | 4437674016 | cpu:5266317184:16 | 0 | 198 | 200 | False | True | False | False | ["DynamicSPHState","PeriodicNeighborhood"] |
| start_stage_neighborhood.particle_support | 4437549824 | cpu:4472066560:8192 | 0 | 198 | 200 | False | True | False | False | ["DynamicSPHState","PeriodicNeighborhood"] |
| start_stage_neighborhood.row | 4437738752 | cpu:4566351872:663552 | 0 | 198 | 200 | True | True | False | False | ["FrozenReciprocalTopology","PeriodicNeighborhood"] |

## 三个独立 200-step 回归

| run | steps | edges | IDs | age-2 | current | retired | old | same-slot | unknown Δ | referrers | PASS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| stage01dr4_f_r1 | 200 | [82944] | 1 | 15 | 15 | 0 | 12 | 9 | 0 | 0 | False |
| stage01dr4_f_r2 | 200 | [82944] | 1 | 15 | 15 | 0 | 15 | 9 | 0 | 0 | False |
| stage01dr4_f_r3 | 200 | [82944] | 1 | 15 | 15 | 0 | 18 | 9 | 0 | 0 | False |

三次目标快照的 15/15 均为 current persistent，0/15 retired。但运行中非 GC
accepted steps 另有 retired old-survivor，三次峰值为 `[12, 15, 18]`，同槽多代峰值为
`[9, 9, 9]`；unknown growth 与明确 referrer chain 为零。按预登记规则，任一
retired old-survivor 已足以判为 retention signal。
