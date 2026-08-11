# Stage 04C Freeze and Scope

Stage 04B authorization is `LOCAL_CAUSAL_REFERENCE_FAMILY_POOL_QUALIFIED`. Historical input freeze passed for 30 hashed inputs. The Stage 04C contract was written before the first TRAIN state-array decode; decode count at freeze was 0.

- Contract: `05_task_aligned_gradient/stage04c/contracts/task_aligned_parameter_gradient_contract_v0_1.yaml`
- Immutable contract hash: `sha256:eb63d659d8c4a868160c952ed9aed7aadf79938353a5d8129b238f22f7ef1840`
- Formal scope: CPU float64, explicit `SDPBackend.MATH`, N8, 6 TRAIN lineages, 2 variants, 2 origins, 3 seeds.
- Prohibited throughout: optimizer, parameter update, training, neural rollout evaluation, normalization fitting, validation target decode and sealed payload decode.
- Historical Stage 03D/03D-R failures and Stage 03E denial remain unchanged.
