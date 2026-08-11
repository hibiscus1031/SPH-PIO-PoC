# Stage 02M-R — Final report

## Final status

**STATIC_FITTING_FAILURE_ATTRIBUTED_OPTIMIZATION_CONDITIONING**

1. Stage 02M failure preserved：`STATIC_PAIR_FORCE_FITTING_NOT_QUALIFIED`；Stage 02N authorization=false。
2. 9-run/checkpoint mapping 唯一；optimizer updates `[300, 300, 300, 300, 300, 300, 440, 740, 300]`，best updates `[100, 40, 40, 40, 20, 40, 240, 540, 20]`。
3. Initial/best-train/selected/terminal metrics：

| run | init train Q | best-train update/Q | selected update/Q | terminal update/Q |
|---|---:|---:|---:|---:|
| K0_seed20261201 | 0.998373 | 300 / 0.993085 | 100 / 0.994009 | 300 / 0.993085 |
| K0_seed20261202 | 1.000602 | 300 / 0.993927 | 40 / 0.994128 | 300 / 0.993927 |
| K0_seed20261203 | 1.000261 | 300 / 0.992885 | 40 / 0.993560 | 300 / 0.992885 |
| K1_seed20261201 | 0.998011 | 300 / 0.991511 | 40 / 0.993502 | 300 / 0.991511 |
| K1_seed20261202 | 1.006766 | 300 / 0.992371 | 20 / 0.995741 | 300 / 0.992371 |
| K1_seed20261203 | 0.998994 | 300 / 0.991059 | 40 / 0.992991 | 300 / 0.991059 |
| K2_seed20261201 | 1.001697 | 240 / 0.965867 | 240 / 0.965867 | 440 / 0.992843 |
| K2_seed20261202 | 0.999113 | 740 / 0.652523 | 540 / 0.905022 | 740 / 0.652523 |
| K2_seed20261203 | 1.001779 | 260 / 0.959224 | 20 / 0.993811 | 300 / 0.992399 |

4. Ever-achieved train gate：否，**NEVER_FIT_TRAIN**。
5. Checkpoint dynamics：K0/K1 持续欠拟合；K2 存在 seed instability/plateau，但没有 selection conflict 能解释 train failure；early stopping 非主要阻断。
6. Target scale：a0 保持 400；target_tilde RMS `4.305e-04`–`1.573e-03`，loss 处于极小数量级。
7. Gradient/Adam conditioning：selected multiplier=1 的历史 epsilon-dominated/WD-dominated 参数比例 `0.997` / `0.928`。
8. Loss multiplier：放大显著降低 prospective epsilon/WD dominance，但 update 方向不稳定；未授予严格 `LOSS_SCALE_CONDITIONING_EVIDENCE` 标签，未改变协议。
9. Basis vs learned map：自由 edge coefficient basis residual PASS 不证明 `g_theta(allowed_features)` 可学习。
10. Feature identifiability：**NO_HARD_IDENTIFIABILITY_CONTRADICTION_FOUND**；无 test target。
11. Tangent projection：18/18 完成；whole-network 是 30-iteration 上界。
12. Final-head projection：K1 selected 有 2 seeds 达 0.25 门，支持 `HEAD_OPTIMIZATION_GAP`。
13. Family/configuration shift：validation/test input 均明显偏离 train，但 train 从未拟合，故 transfer 不是主要阻断。
14. Consumed-test boundary：`current_test_status=consumed_confirmatory_test`；BLIND_FAMILY_04 仅可作历史 test。
15. Unique failure attribution：**STATIC_FITTING_FAILURE_ATTRIBUTED_OPTIMIZATION_CONDITIONING**。
16. Next authorized branch：`Stage 02M-P — Prospective Training Protocol v0.2 Design with New Blind Evaluation Families`，仅设计、不训练。
17. `new_optimizer_steps = 0`。
18. `new_training_runs = 0`。
19. `new_test_evaluations = 0`。
20. `rollouts = 0`；诊断后 285 个历史 hashes unchanged：**PASS**。

不修改 architecture/loss/features/a0，不重选 checkpoint，不解码 test target，不声称 K2 优于 K1、Attention 必要或 Stage 01 已恢复。
