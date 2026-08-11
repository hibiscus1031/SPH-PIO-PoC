# Stage 06A final report

## Final status

`ACTUAL_OPTIMIZER_UPDATE_DYNAMICS_QUALIFIED`

Stage 06B — Formal Training Protocol Preregistration, Validation Opening and Sealed-Test Preflight is authorized.

## 1. User-authorized hypothesis

H06-01 asks whether independently verified actual full-optimizer update dynamics can establish a new training-qualification route despite sparse coordinate FD-window failures. Stage 06A tests this hypothesis only; it is not Stage 05D and not formal training.

## 2. Historical status and failures

Stage 05B remains `CONSERVATIVE_DISCRETE_DEFECT_TARGET_AND_SCALE_QUALIFIED`; Stage 05C remains `OPTIMIZER_ALIGNED_DEFECT_GRADIENT_AND_LOCAL_DESCENT_NOT_QUALIFIED`; Stage 05C-R remains `DEFECT_GRADIENT_FD_FAILURE_EVIDENCE_INCOMPLETE`; Stage 05C-P remains `NOT_STARTED`; Stage 05C-Q remains `PROSPECTIVE_OPTIMIZER_PATH_GRADIENT_CONFIRMATION_NOT_QUALIFIED`; Stage 05D authorization remains false. The 4 Stage 05C hashes are `['sha256:1cc6c29e128dae209787d9e95468f6a3cd675beed7c7b403b94a62da2564eb92', 'sha256:3e83f230a85ff39ee97ea8f9964fa11ad2668f84291c8bbce244ccf2ca8526f8', 'sha256:9fb0443d1cbac82cd765f6a2642297e9307a89a07034f0f68d4079762a228a69', 'sha256:b0aa122c427bea6da621fd27751034f17184b92e878ee50c76afe36044b59fb7']` and the 6 Stage 05C-Q hashes are `['sha256:34fbf73aa8c0221cfb3a588c0669b0e28f125448eb2467533505fff4a12c7dbc', 'sha256:62f4722bdc8bce75d9966a8aeb335101871f8ef7dda3bfe5587d60bfdd7a3cb0', 'sha256:823f17db030aa9c007e8f096e0ca94164ef3b4b2a1fc203c15589eeb830d717f', 'sha256:a013995b33970f2bcc8c426c1c141655acd41ff69dcff5f15a3195ecc086b798', 'sha256:a4b939ec0f38b99571fca116758d385016f11db7116779e451bc816c0f88fc61', 'sha256:c5b3322ea469b6282dafd5c2757a0881c5b377dde85c931d266c47f50cf679d1']`; all are preserved. Complete coordinate/block coverage is not qualified.

## 3. Blind identities and access

Fresh model seeds: `[20600601, 20600602, 20600603]` for D1/D2/D3. Blind salt: `stage06a_blind_origin_v1`; 8 unused origins per lineage/variant, 16 records per lineage, 96 global, historical overlap 0. Validation evaluations = 0; sealed-test evaluations = 0; all forbidden decode counts = 0.

## 4. Optimizer and loss

The unique optimizer was AdamW with betas `(0.9,0.999)`, eps `1e-12`, weight decay 0, AMSGrad false, and global clip 1.0. The frozen LR ladder was `1e-5, 3e-5, 1e-4, 3e-4, 1e-3`. The sole loss remained the balanced mean squared conservative-defect acceleration error with `s_a=3.45632855338432798e-01`; target, scale, balancing, and RK2 were unchanged.

## 5. Gradient, one-step, and micro-update evidence

All contexts recorded complete gradient/update identities, group norms, clipping, cosine, moments, displacement, and deterministic repeats. All 63 contexts formed an adjacent one-step passing region; stable evidence sets were `{'D1': [1e-05, 3e-05, 0.0001, 0.0003], 'D2': [1e-05, 3e-05, 0.0001, 0.0003], 'D3': [1e-05, 3e-05, 0.0001, 0.0003, 0.001]}`. 266/272 2/4-step paths passed, with at least one passing path per context. These were qualification micro-updates only.

## 6. Actual-update FD and aggregation

The preregistered algorithm selected the smallest passing qualification LR within each context solely for actual-update FD. 63/63 contexts passed reverse/central-FD sign consistency, adjacent-scale directional stability, observed one-step consistency, topology, and safety. Arm aggregation: `{'D1': {'lineages': {'LCDF_01': {'seed_pass_count': 3, 'required': 2, 'pass': True}, 'LCDF_04': {'seed_pass_count': 3, 'required': 2, 'pass': True}, 'LCDF_05': {'seed_pass_count': 3, 'required': 2, 'pass': True}, 'LCDF_06': {'seed_pass_count': 3, 'required': 2, 'pass': True}, 'LCDF_07': {'seed_pass_count': 3, 'required': 2, 'pass': True}, 'LCDF_08': {'seed_pass_count': 3, 'required': 2, 'pass': True}}, 'lineage_pass_count': 6, 'global_seed_pass_count': 3, 'global_pass': True, 'pass': True}, 'D2': {'lineages': {'LCDF_01': {'seed_pass_count': 3, 'required': 2, 'pass': True}, 'LCDF_04': {'seed_pass_count': 3, 'required': 2, 'pass': True}, 'LCDF_05': {'seed_pass_count': 3, 'required': 2, 'pass': True}, 'LCDF_06': {'seed_pass_count': 3, 'required': 2, 'pass': True}, 'LCDF_07': {'seed_pass_count': 3, 'required': 2, 'pass': True}, 'LCDF_08': {'seed_pass_count': 3, 'required': 2, 'pass': True}}, 'lineage_pass_count': 6, 'global_seed_pass_count': 3, 'global_pass': True, 'pass': True}, 'D3': {'lineages': {'LCDF_01': {'seed_pass_count': 3, 'required': 2, 'pass': True}, 'LCDF_04': {'seed_pass_count': 3, 'required': 2, 'pass': True}, 'LCDF_05': {'seed_pass_count': 3, 'required': 2, 'pass': True}, 'LCDF_06': {'seed_pass_count': 3, 'required': 2, 'pass': True}, 'LCDF_07': {'seed_pass_count': 3, 'required': 2, 'pass': True}, 'LCDF_08': {'seed_pass_count': 3, 'required': 2, 'pass': True}}, 'lineage_pass_count': 6, 'global_seed_pass_count': 3, 'global_pass': True, 'pass': True}}`.

## 7. Coordinate/block boundary and structure

Fixed diagnostic classifications were `{'FD_WINDOW_MISSING': 23, 'PASS': 841}` over 864 probes. No allowed `FD_WINDOW_MISSING` changes the historical coordinate/block verdict. All 54 structure audits passed the seven transforms, reciprocal conservation, density, coefficient/hidden finiteness, graph identity, and commit requirements.

## 8. Destruction, resources, and counts

All qualification weights and optimizer states were destroyed. Future formal initialization is reserved to `stage06b_formal_seed_v1:not-any-of-20600601-20600603`. Peak per-process RSS delta was 1057144832 bytes; no retained-autograd monotonic growth or dense particle N×N allocation was observed. Qualification model instances = 1606; qualification optimizer instances = 1237; qualification optimizer steps = 2325; update paths = 8550; graph rebuilds = 842256. Formal training runs = 0; saved training checkpoints = 0.

## 9. Integrity and authorization

The frozen contract hash is unchanged: `sha256:5d3092f3bd8890b8de7a5734f8e92a581ef1751d6cbdbae5039eda52d5f4de3a`. Historical Stage 01–05 readable artifact hashes are unchanged (`3700` checked); protected private payloads remained unreadable. Stage 06B authorization = `True`.
