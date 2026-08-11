# Stage 03B topology-event audit

D-R1-B 在每个 N 上用 1025 个等距 tau 点对完整短时域 `[0,0.0625]` 执行 dense exact pair scan，并完全重复一次。N=8/12/16 的 cutoff 最小绝对裕量分别为 0.0569371、0.0379249、0.0284341；均未出现 edge birth、edge death、cutoff touch、graph-relevant minimum-image representative switch 或 reciprocal failure。

因此 registry 的事件数为 0，分类是 `NO_EVENT_FIXED_TOPOLOGY`；每个 case 的唯一 fixed-topology interval 为 `[0,0.0625]`，deterministic repeat PASS。零事件是冻结 amplitude 与 `H/dx=2.6` 的真实结果，没有为了制造事件而修改 amplitude，也没有伪造候选。

本阶段未做任何 gradient audit。该 registry 为 Stage 03D 提供经过资格认定的固定-topology interval；若 Stage 03D 需要非空 cutoff event 样本，必须另行预注册新 family，而不能改写本次 D-R1-B。
