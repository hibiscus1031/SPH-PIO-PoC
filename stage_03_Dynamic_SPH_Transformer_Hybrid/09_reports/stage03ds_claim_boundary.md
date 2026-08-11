# Stage 03D-S — Claim boundary

## SUPPORTED CLAIMS

| Claim | Allowed wording | Prohibited wording |
|---|---|---|
| dynamic RK2 hybrid solver implementation is verified | 动态 RK2 hybrid solver 的冻结实现合同已通过 Stage 03C。 | dynamic solver performance is verified |
| zero-correction equivalence is bitwise established | zero correction 在 288/288 检查中与 D0 bitwise 等价。 | nonzero learned correction is accurate |
| reciprocal pair-force conservation persists through multiple stages | 冻结多步审计的 540/540 stage conservation checks 通过。 | long-time conservation and stability are proven |
| deterministic edge birth/death semantics are qualified | TE1 的 birth/death、replay 和 fixed-side gradients 已资格化。 | cutoff membership is differentiable |
| gradients are valid on many fixed-topology paths | 360 个冻结 probes 中 216 个获得 stable AD/FD window。 | all multistep gradients are valid |
| complete multistep gradient qualification was not achieved | Stage 03D 保持 NOT_QUALIFIED，D-R 保持 MIXED_OR_UNRESOLVED。 | Stage 03D-R repaired the Stage 03D failure |

## CONDITIONAL CLAIMS

| Claim | Allowed wording | Prohibited wording |
|---|---|---|
| D3 gradients show backend sensitivity | 在冻结的 selected diagnostics 内，D3 的部分梯度显示 backend sensitivity。 | D3 is intrinsically non-differentiable |
| temporal-history influence is strongly attenuated through rollout | 当前 reference-prehistory paths 显示 rollout 中 history influence 强烈衰减。 | temporal memory is useless |
| finite-difference conditioning contributes to some failures | extended FD 支持 conditioning 对部分 failure 的贡献。 | all failures are finite-difference artifacts |
| no systematic vanishing/exploding gradient was detected | 冻结 horizon diagnostics 未检测到系统性 vanish/explode。 | gradient health is proven for training |

## UNSUPPORTED CLAIMS

| Claim | Allowed wording | Prohibited wording |
|---|---|---|
| dynamic Transformer is trainable | 动态训练尚未授权或执行。 | the dynamic Transformer is trainable |
| solver-in-the-loop training is valid | solver-in-the-loop 为 NOT AUTHORIZED / NOT EXECUTED。 | solver-in-the-loop training is valid |
| rollout improves SPH | 未进行 rollout 性能评价。 | rollout improves SPH |
| Transformer outperforms recurrent/instantaneous baselines | D1/D2/D3 未训练、未比较。 | Transformer outperforms D1/D2 |
| cutoff edge existence is differentiable | 只能主张 event 两侧的 piecewise-smooth gradients。 | edge membership is differentiable |
| Stage 01 V2 is restored | Stage 01 仍为 V2_QUALIFICATION_FAIL。 | Stage 03 restores Stage 01 V2 |
| viscosity operator is confirmed | viscosity operator form 仍为 NOT_CONFIRMED。 | viscosity operator is confirmed |
| long-time stability is established | 未执行 long-time rollout/stability qualification。 | long-time stability is established |

Unexecuted dynamic training must never be described as failed training. Stage 03D NOT_QUALIFIED must never be described as failure of the entire Transformer solver.
