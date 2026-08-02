# Stage 01F3C CT2 机制门评估

## 旧 CT2

旧 CT2 要求 total exact velocity error 非增；MMS-A 从 `0.002593687534388588` 增至 `0.002593997366237996`，MMS-B 从 `0.002599595258802144` 增至 `0.002599676260560093`，故 Stage 01F3B 形式失败。 该历史失败保持不变。

## C1–C7

| gate | evidence | result |
|---|---|---|
| C1 | N32 reference sensitivity | PASS |
| C2 | vector decomposition closure | PASS |
| C3 | temporal error monotone and order >=1.80 | FAIL |
| C4 | frozen successive-dt self-difference identity | PASS |
| C5 | endpoint negative cross term explains below-platform total error | PASS |
| C6 | finest total velocity error within 1% of platform | PASS |
| C7 | source/conservation/topology/resource/reference | PASS |

N32 机制状态：`FAIL`。端点 coarse cross 为负，但 integrated-RMS coarse cross 为正；Stage 01F3B 的形式判据不被放宽、重算或重分类。
