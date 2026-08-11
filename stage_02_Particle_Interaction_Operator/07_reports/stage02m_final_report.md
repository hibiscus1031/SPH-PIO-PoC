# Stage 02M — Final report

## Final status

**STATIC_PAIR_FORCE_FITTING_NOT_QUALIFIED**

1. Authorization: Stage 02L `STATIC_FITTING_PROTOCOL_READY` under protocol `sha256:ab02a49a508c4ddcab5db037886abd329ab29d2eedfc8ffe5d818ad691668648`.
2. Freeze: protocol/dataset/architecture/normalization/split **PASS**.
3. Execution inventory: 9/9 frozen K0/K1/K2 × three-seed runs have terminal evidence.
4. Train target access: 10 frozen train targets decoded after execution freeze.
5. Validation target access: 5 frozen validation targets decoded after execution freeze.
6. Pre-release test target access/decode: **0**.
7. Optimizer/update counts: `[300, 300, 300, 300, 300, 300, 440, 740, 300]`; no budget exceeded 1000.
8. Early stopping: frozen minimum-300/patience-200/minimum-improvement rule applied; terminal states `['EARLY_STOPPED', 'EARLY_STOPPED', 'EARLY_STOPPED', 'EARLY_STOPPED', 'EARLY_STOPPED', 'EARLY_STOPPED', 'EARLY_STOPPED', 'EARLY_STOPPED', 'EARLY_STOPPED']`.
9. Checkpoint selection: validation graph-mean Q_L2 only, with earlier tie-break.
10. Selected checkpoint hashes: `['sha256:fe3f6a26b542b01b4a43ab44b7014cc9d513f9fcb0f680048a723b6c114657f1', 'sha256:f45a51ad1ae374fa045a9b46c86b990e5839d84891ac9c380743f3349813ac98', 'sha256:78d427a6da56242205f3d7cfcccd6188aa56d7b09dac9fe946d10bef170f6014', 'sha256:f190f7d6444926befc867e3d93b7310634b579e20b7c168b3879349f518f74bf', 'sha256:a8a7255be0323f2c4589062b8e9f2173e5754435b72a860a71aea1e3b5c7abd1', 'sha256:e5ffe44227afb90bf57b9ceb39476174784bd0c1d61a076e6b670cf3b92ceee7', 'sha256:2ab391cfb762b97cc3d9d0c6b86d7b078fbd0ba94b29229c256d6383f6d6db8f', 'sha256:fa5088d2a4ea41f6e47665192ba1f76c3591d6004a483f2dc2f3503e3ec4cc42', 'sha256:5372d24fa1ce54b838e288137edbfbe72e3abcdc3121dcf534fd0f3a349cff2d']`.
11. Infrastructure retry history: no pending retry and no result-dependent/scientific restart.
12. Training metrics: complete per-update histories retained.
13. Validation metrics: complete 20-update histories and selected metrics retained.
14. Test release manifest: `sha256:ae083e66f2c003258a3f9387b8eb16cf862dbbdf4d780960c751e461733f802d`, generated after immutable closure.
15. Sealed test: nine checkpoints evaluated exactly once; no post-test modification.
16. Zero correction: mandatory theoretical Q_L2=1 baseline reported.
17. K0 diagnostic: `{'A_numerical_stability': True, 'B_train_fit_pass_seed_count': 0, 'B_train_fit': False, 'C_validation_transfer_pass_seed_count': 0, 'C_validation_transfer': False, 'D_test_transfer_pass_seed_count': 0, 'D_test_transfer': False, 'E_conservation': True, 'all_A_through_E': False, 'route_decision_role': 'diagnostic_only'}`.
18. K1 result: `{'A_numerical_stability': True, 'B_train_fit_pass_seed_count': 0, 'B_train_fit': False, 'C_validation_transfer_pass_seed_count': 0, 'C_validation_transfer': False, 'D_test_transfer_pass_seed_count': 0, 'D_test_transfer': False, 'E_conservation': True, 'all_A_through_E': False, 'route_decision_role': 'eligible'}`.
19. K2 result: `{'A_numerical_stability': True, 'B_train_fit_pass_seed_count': 0, 'B_train_fit': False, 'C_validation_transfer_pass_seed_count': 1, 'C_validation_transfer': False, 'D_test_transfer_pass_seed_count': 1, 'D_test_transfer': False, 'E_conservation': True, 'all_A_through_E': False, 'route_decision_role': 'eligible'}`.
20. Postfit antisymmetry: all selected checkpoints PASS at `1e-10`.
21. Postfit momentum: all selected checkpoints PASS at `1e-10`.
22. Postfit equivariance/invariance: all selected checkpoints PASS at `1e-10`.
23. Actual resources: **PASS**, peak RSS and checkpoint storage within hard limits.
24. Frozen success-gate evaluation: **FAIL**; at least one K1/K2 A–E pass = `False`.
25. Stage 02N authorization: not authorized.
26. Rollout executed/authorized: **no**.
27. Solver-in-the-loop executed/authorized: **no**.
28. Stage 01 recovery claim: **none**; Stage 01 remains `V2_QUALIFICATION_FAIL`.
29. Attention/Transformer necessity claim: **none**.
30. Historical hashes unchanged: **PASS**; Stage 01 through Stage 02L files were not modified.

Stage 01H remains `FINITE_RESOLUTION_DOMINANT`, viscosity operator form remains `NOT_CONFIRMED`, and regularity remains `diagnostic_only`. Static sealed-test fitting is not dynamic solver or rollout qualification.
