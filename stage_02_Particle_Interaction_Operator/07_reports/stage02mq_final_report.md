# Stage 02M-Q — Final report

## Final status

**STATIC_PAIR_FORCE_FITTING_V02_NOT_QUALIFIED**

1. Stage 02M-P authorization: `STATIC_FITTING_PROTOCOL_V02_READY`.
2. Frozen identities: protocol `sha256:8cd068c5b23eacfbcb2c56846352fd6f3c560b46d8562806e3ed568c278ddb6e`; collection `blind_multifamily_pair_scope_v1_1_protocol_v02`; architecture `sha256:1e313f871b13f3f2fc0cc780ab24d50a7fd9fe8a96866da91fae5ede9ab555a4`.
3. Supervision scale: `a_sup=0.392220124168075 m s^-2`, identity `sha256:85d5339dde02c29dba5bfa753096ab25598bd29a5df576def7691dcdbfef838e`.
4. New run inventory: nine preregistered K0/K1/K2 × three-seed runs, all with terminal records.
5. Pre-release test access/decode: 0.
6. Optimizer/update counts: `[1000, 1000, 1000, 1000, 1000, 1000, 700, 740, 1000]`.
7. Conditioning histories: required seven snapshots per run, aggregate PASS `True`.
8. Early stopping decisions: `[('K0_seed20261211', 'COMPLETED_MAX_UPDATES', 'maximum_1000_updates_reached'), ('K0_seed20261212', 'COMPLETED_MAX_UPDATES', 'maximum_1000_updates_reached'), ('K0_seed20261213', 'COMPLETED_MAX_UPDATES', 'maximum_1000_updates_reached'), ('K1_seed20261211', 'COMPLETED_MAX_UPDATES', 'maximum_1000_updates_reached'), ('K1_seed20261212', 'COMPLETED_MAX_UPDATES', 'maximum_1000_updates_reached'), ('K1_seed20261213', 'COMPLETED_MAX_UPDATES', 'maximum_1000_updates_reached'), ('K2_seed20261211', 'EARLY_STOPPED', 'validation_patience_200_updates_exhausted'), ('K2_seed20261212', 'EARLY_STOPPED', 'validation_patience_200_updates_exhausted'), ('K2_seed20261213', 'COMPLETED_MAX_UPDATES', 'maximum_1000_updates_reached')]`.
9. Validation selection: minimum graph-mean Q_L2, earlier-update tie break.
10. Selected checkpoint identities: `{'K0_seed20261211': {'update': 1000, 'sha256': 'sha256:8d65286395e5001645e7a9a7bcd5da605fe30e9e3a7825f4107e0106b059fae8'}, 'K0_seed20261212': {'update': 840, 'sha256': 'sha256:f667ce47fd91725eeb450599fb12bf54bd104dbf10ee88730dcabeb494def052'}, 'K0_seed20261213': {'update': 900, 'sha256': 'sha256:13d23924f96a6764130458d2c2d8bec56277c1dbe2ca74ee377cb1eacb65034f'}, 'K1_seed20261211': {'update': 1000, 'sha256': 'sha256:12cdd56070edc9beecddef890e77e377417bd72b670746ab3ac3830e72ebfc03'}, 'K1_seed20261212': {'update': 1000, 'sha256': 'sha256:921cafeaebb66624a5838f1c7ed9160318c65fae95c8f255bab63bc8215a9bcf'}, 'K1_seed20261213': {'update': 1000, 'sha256': 'sha256:ee948fa7c7c8f0fda52238f25680f7780287a22e275fc5835cfc9754338a3600'}, 'K2_seed20261211': {'update': 500, 'sha256': 'sha256:7e608d0dfc85064e03598724238e2b8f47be7e455f635379a2661a8833efcd44'}, 'K2_seed20261212': {'update': 540, 'sha256': 'sha256:8924bdae4b531ee2dacf0490e3635fd5214f186f9d6c1a622e43c789bf64e87d'}, 'K2_seed20261213': {'update': 1000, 'sha256': 'sha256:4936eb69bdc5fda7e5743f4e34bbe25f4af58986a051e89fcde0fad6560bb132'}}`.
11. Infrastructure retry history: no scientific restart and no pending retry.
12. Train metrics: retained per run in selected metrics and complete update histories.
13. New validation metrics: retained at each 20-update evaluation and selected checkpoints.
14. New test-release manifest: `sha256:41e330c20da6bab771e42d91ad2d28bff5972895327a988e63807dbbb74bb1e5`.
15. New sealed-test metrics: nine checkpoints, exactly once each, status `CLOSED`.
16. Zero-correction baseline: theoretical Q_L2=1.
17. K0 diagnostic: `{'A_numerical_stability': True, 'B_train_fit_pass_seed_count': 0, 'B_train_fit': False, 'C_validation_transfer_pass_seed_count': 3, 'C_validation_transfer': True, 'D_test_transfer_pass_seed_count': 3, 'D_test_transfer': True, 'E_conservation': True, 'all_A_through_E': False, 'route_decision_role': 'diagnostic_only'}`.
18. K1 frozen-gate result: `{'A_numerical_stability': True, 'B_train_fit_pass_seed_count': 0, 'B_train_fit': False, 'C_validation_transfer_pass_seed_count': 3, 'C_validation_transfer': True, 'D_test_transfer_pass_seed_count': 3, 'D_test_transfer': True, 'E_conservation': True, 'all_A_through_E': False, 'route_decision_role': 'eligible'}`.
19. K2 frozen-gate result: `{'A_numerical_stability': True, 'B_train_fit_pass_seed_count': 1, 'B_train_fit': False, 'C_validation_transfer_pass_seed_count': 3, 'C_validation_transfer': True, 'D_test_transfer_pass_seed_count': 3, 'D_test_transfer': True, 'E_conservation': True, 'all_A_through_E': False, 'route_decision_role': 'eligible'}`.
20. Postfit conservation: `PASS`.
21. Postfit equivariance/invariance: `PASS`.
22. v0.1 comparison: descriptive protocol comparison only; no historical-test reevaluation.
23. Actual resources: `PASS`; wall 761.144 s, peak RSS 649592832 B, checkpoints 159622554 B.
24. Final route decision: `STATIC_PAIR_FORCE_FITTING_V02_NOT_QUALIFIED`; if not qualified, the static PIO learning route terminates and v0.3 is not authorized.
25. Stage 02N authorization: `not authorized`.
26. Rollout executed/authorized: no.
27. Solver-in-the-loop executed/authorized: no.
28. Attention/Transformer necessity claim: none.
29. Stage 01 recovery claim: none; Stage 01 remains `V2_QUALIFICATION_FAIL`.
30. Historical hashes unchanged: `PASS`.

Stage 01H remains `FINITE_RESOLUTION_DOMINANT`, viscosity operator form remains `NOT_CONFIRMED`, and regularity remains `diagnostic_only`. Static sealed-test fitting does not qualify dynamic solver integration or rollout.
