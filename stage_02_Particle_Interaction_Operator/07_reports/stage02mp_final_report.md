# Stage 02M-P — Final report

## Final status

**STATIC_FITTING_PROTOCOL_V02_READY**

1. Stage 02M failure preserved：`STATIC_PAIR_FORCE_FITTING_NOT_QUALIFIED`。
2. Stage 02M-R attribution preserved：`STATIC_FITTING_FAILURE_ATTRIBUTED_OPTIMIZATION_CONDITIONING`。
3. Train-only supervision scale：`a_sup=0.392220124168075 m s^-2`，10 graphs、Kahan、等图权。
4. Output scale与input normalization严格分离；旧 hash `sha256:2208d2f4b9b7c848f2cd1b93624f9f6a3d9fb29e65cdd70ee453e6122c43d051` 原样复用。
5. v0.2 loss：10 个 complete train graphs 的 scaled node-vector MSE等图平均。
6. Adam epsilon/weight decay：1e-12 / 0；无 grid。
7. Architecture/features：Stage 02K K0/K1/K2完全不变，KNEG不训练。
8. New run seeds：20261211、20261212、20261213，共9 prospective runs。
9. Budget/success gates：保持 Stage 02L 原值，无放宽或延期。
10. Protocol freeze：hash `sha256:8cd068c5b23eacfbcb2c56846352fd6f3c560b46d8562806e3ed568c278ddb6e`，公式在 hash 后生成。
11. New blind validation formula：V02_BLIND_VALIDATION_01 / 2026080501 / `sha256:28886b28ecad9e2bc0340b69094101ad4b89c72e7d48da8ea7ad4660ac7c973e`。
12. New blind test formula：V02_BLIND_TEST_01 / 2026080502 / `sha256:5e6a31f8512f2c8d14b2b8f15587273c404cd50c1d20f79af7c9d3810204c47d`。
13. Reference/target/conservation：10/10 PASS；最大 force/pair residual `6.635e-15` / `6.395e-14`。
14. v1.1 collection：`blind_multifamily_pair_scope_v1_1_protocol_v02`，20 records完整。
15. Lineage/split：4 components，10 train / 5 validation / 5 test，无 cross-split lineage。
16. Input normalization：旧统计 hash复用，train record hashes一致，未 refit。
17. New test seal：4项 denial PASS；access=false；未生成 release manifest。
18. Zero-step conditioning：9/9 PASS；K1/K2 loss `[0.1,10]`、epsilon≤0.25、WD=0、主要模块梯度门通过。
19. Checkpoint/harness：9/9 zero-step roundtrip、RNG、next-forward、counter=0、resume dry run、gradient/reorder均 PASS；最大 gradient-equivalence error `2.464e-16`。
20. Resource forecast：PASS；RSS/storage/O(N²)/finite completion全部过门。
21. Stage 02M-Q authorization：**True**，仅限 Controlled Static Pair-Force Fitting v0.2 with New Sealed-Test Evaluation。
22. `new_optimizer_steps = 0`。
23. `new_training_runs = 0`。
24. `new_test_evaluations = 0`。
25. `rollouts = 0`；无 solver-in-the-loop。
26. Consumed historical boundary：BLIND_FAMILY_03/04仅作 historical validation/test，不进入v1.1。
27. Historical hashes unchanged：Stage 02M-R 285-file复核及本阶段直接冻结输入均 **PASS**。

Stage 02M-P没有正式训练、checkpoint selection、validation/test performance evaluation或Stage 01 recovery claim。若未来 Stage 02M-Q 仍不 qualified，当前 static PIO learning route终止并进入方法总结与论文边界评估。
