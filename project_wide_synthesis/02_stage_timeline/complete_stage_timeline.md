# 全项目阶段时间线

[PROJECT_EVIDENCE] 依赖顺序来自Git/tag、阶段账本和冻结manifests；exact status保持原字面。

| 阶段 | exact final status | 科学问题/结果 | 阻断与下一授权 | 证据 |
|---|---|---|---|---|
| Stage 00 | CONDITIONAL | CPU/MPS操作检查通过；diffSPH仅安装/导入/邻域预检。 | 完整diffSPH求解器未在该阶段运行。 → Stage 01最小执行路径 | 07_reports/stage_00_summary.md |
| Stage 01 | CONDITIONAL PASS (V0 only) | V0工程可执行；V1部分；V2未完成；V3未开始。 | 不可作fixed-physics truth。 → Stage 01B V1 | 07_reports/stage_01_scope_reclassification.md |
| Stage 01B | V1_FAIL | kernel/Laplacian/AD及结构门触发停止。 | V2/TGV未授权。 → Stage 01C修复 | 07_reports/stage_01b_final_vv_report.md |
| Stage 01C | C1_PASS_C2_PASS_C3_PASS_C4_PASS | 四项静态重资格门通过。 | 不是动态V2。 → Stage 01D | 06_experiments/stage_01c_operator_candidates/results/stage01c_gate_status.txt |
| Stage 01D | V2_FAIL | N32 smoke资源门失败；后续多门NOT_RUN。 | 资源增长机制未明。 → Stage 01D-R诊断 | 06_experiments/stage_01d_fixed_physics_tgv/results/stage01d_v2_status.txt |
| Stage 01D-R | RESOURCE_FAIL_LINEAR_GROWTH | 资源重资格仍失败。 | 不能据此直接称memory leak。 → Stage 01D-R2 | 06_experiments/stage_01dr_memory_diagnosis/results/stage01dr_resource_status.txt |
| Stage 01D-R2 | ATTRIBUTION_UNRESOLVED | storage归因未唯一解析。 | cutoff topology与生命周期混杂。 → Stage 01D-R3 | 06_experiments/stage_01dr2_storage_attribution/results/stage01dr2_attribution_status.txt |
| Stage 01D-R3 | R3_CONFIRMATION_UNRESOLVED | 证据仍未解析。 | weakref语义待核。 → Stage 01D-R4 | 06_experiments/stage_01dr3_topology_confirmation/results/stage01dr3_status.txt |
| Stage 01D-R4 | R4_RETENTION_REDETECTED | retention被重新检测。 | GC时序未定位。 → Stage 01D-R5 | 06_experiments/stage_01dr4_weakref_semantics/results/stage01dr4_status.txt |
| Stage 01D-R5 | R5_BOUNDED_GC_DELAY_CONFIRMED | GC-disabled线性；default-GC 2000步有界。 | 不能把旧资源失败改写为假阳性。 → Stage 01D-P | 06_experiments/stage_01dr5_gc_cycle_localization/results/stage01dr5_status.txt |
| Stage 01D-P | POLICY_PASS_ISOLATED_DEFAULT_GC | 3/3 canary通过；政策资格化。 | 仅资源政策，不是V2数据。 → Stage 01D2设计申请 | 06_experiments/stage_01dp_resource_policy/results/stage01dp_status.txt |
| Stage 01D2 | STAGE01D2_V2_REQUALIFICATION_FAIL | 时间可解释，但空间非单调、jitter/资源门失败。 | 不能进入V3。 → Stage 01E归因 | 06_experiments/stage_01d2_v2_requalification/results/stage01d2_evaluation.json |
| Stage 01E | E_MODEL_FORM_ALIGNMENT_DOMINANT | EOS初始化残差主导；两项渐近拟合不可识别。 | 不改变V2失败。 → WCSPH-compatible MMS | 06_experiments/stage_01e_error_decomposition/results/stage01e_evaluation.json |
| Stage 01F | MMS_SPECIFICATION_PASS | MMS规格通过。 | 规格不等于实现/收敛。 → Stage 01F2 | 06_experiments/stage_01f_mms_design/results/stage01f_evaluation.json |
| Stage 01F2 | MMS_IMPLEMENTATION_VERIFIED_PASS | 实现验证通过。 | 未建立收敛资格。 → Stage 01F3 | 06_experiments/stage_01f2_mms_implementation/results/stage01f2_evaluation_v2.json |
| Stage 01F3 | MMS_CONVERGENCE_VERIFICATION_FAIL | reference/topology identity硬门前停止或收敛门失败。 | 需reference资格化。 → Stage 01F3-R | 06_experiments/stage_01f3_mms_convergence/results/stage01f3_evaluation.json |
| Stage 01F3-R | SEMIDISCRETE_REFERENCE_QUALIFIED_DENSE_EQUIVALENT | reference资格化。 | 不修复原F3失败。 → Stage 01F3B | 06_experiments/stage_01f3r_reference_qualification/results/stage01f3r_evaluation.json |
| Stage 01F3B | MMS_CONVERGENCE_VERIFICATION_FAIL | 仍为收敛资格失败；GCI不成立。 | plateau/cancellation影响门设计。 → Stage 01F3C | 06_experiments/stage_01f3b_mms_convergence/results/stage01f3b_evaluation.json |
| Stage 01F3C | CT2_MIXED_OR_UNRESOLVED | 时间阶接近2但抵消门失败，混合/未解析。 | 严格单点门不稳健。 → Stage 01F4 | 06_experiments/stage_01f3c_ct2_adjudication/results/stage01f3c_evaluation.json |
| Stage 01F4 | PLATEAU_AWARE_PROTOCOL_APPROVED | 新协议批准；旧失败保持。 | 尚未执行。 → Stage 01F5 | 06_experiments/stage_01f4_protocol_adjudication/results/stage01f4_evaluation.json |
| Stage 01F5 | PLATEAU_AWARE_REQUALIFICATION_DESIGN_APPROVED | 设计批准。 | 执行清单分支不全。 → Stage 01F5-P | 06_experiments/stage_01f5_requalification_design/results/stage01f5_evaluation.json |
| Stage 01F5-P | EXECUTION_MANIFEST_INCOMPLETE | 执行清单不完整。 | 空间horizon参数未绑定。 → Stage 01F5-Q | 06_experiments/stage_01f5p_branch_completeness/results/stage01f5p_evaluation.json |
| Stage 01F5-Q | FORMAL_SPACE_EXECUTION_BUNDLE_READY | 正式执行bundle就绪。 | 尚未产生资格。 → Stage 01F5B | 06_experiments/stage_01f5q_space_horizon_amendment/results/stage01f5q_evaluation.json |
| Stage 01F5B | PLATEAU_AWARE_MMS_REQUALIFICATION_PASS | 一次性重资格通过；基础设施retry单独保留。 | 不等于V2 physical validation。 → Stage 01G独立验证 | 06_experiments/stage_01f5b_requalification_execution/results/stage01f5b_evaluation.json |
| Stage 01G design | INDEPENDENT_VALIDATION_AND_V2_DESIGN_APPROVED | 设计通过但未执行。 | 需独立授权。 → Stage 01G-P | 06_experiments/stage_01g_validation_design/results/stage01g_design_evaluation.json |
| Stage 01G-P | INDEPENDENT_VALIDATION_EXECUTION_READY | preexecution audit通过。 | evaluator尚需资格化。 → Stage 01G-E | 06_experiments/stage_01gp_preexecution_audit/results/stage01gp_evaluation.json |
| Stage 01G-E | INDEPENDENT_VALIDATION_EVALUATOR_READY | evaluator就绪。 | 执行基础设施仍需授权。 → Stage 01G V2 preflight | 06_experiments/stage_01ge_evaluator_qualification/results/stage01ge_evaluation.json |
| Stage 01G preflight V2 | INDEPENDENT_VALIDATION_EXECUTION_AUTHORIZED | 执行获授权；未生成V2状态。 | 需基础设施成功。 → Stage 01G-R/execute | 06_experiments/stage_01g_execution_preflight_v2/results/stage01gv2_evaluation.json |
| Stage 01G-R | EXECUTION_INFRA_READY_FOR_BENCHMARK | 修复后基础设施就绪。 | 科学门仍待执行。 → Stage 01G execution | 06_experiments/stage_01gr_execution_infrastructure_repair/results/stage01gr_evaluation.json |
| Stage 01G execution | V2_QUALIFICATION_FAIL | acoustic通过；shear N48门失败；V2失败。 | SHEAR3衰减误差。 → Stage 01H诊断 | 06_experiments/stage_01g_validation_execution/results/stage01g_evaluation_reapplication_01.json |
| Stage 01H | VISCOSITY_DIAGNOSIS_COMPLETE | 分类FINITE_RESOLUTION_DOMINANT；算子形式失败未确认。 | 支持尺度与分辨率共变。 → Stage 02独立理论路线 | 06_experiments/stage_01h_viscous_decay_diagnosis/results/stage01h_evaluation.json |
| Stage 02A | PIO_THEORY_QUALIFICATION_COMPLETE | 理论合同完整；未生成数据或模型。 | 尚无可训练 target/dataset。 → Stage 02B 协议设计 | 07_reports/stage02a_pio_theory_report.md |
| Stage 02B | DATASET_QUALIFICATION_COMPLETE | 数据资格协议与 schema 完成。 | 未生成数据，完成协议不授权生成或训练。 → Stage 02C audit-scale generation | 07_reports/stage02b_final_report.md |
| Stage 02C | DATASET_GENERATION_AUDIT_COMPLETE | 3 reference records、6 samples；4 diagnostic、2 topology rejected。 | eligible_for_future_training=0。 → Stage 02D target attribution audit | 07_reports/stage02c_final_report.md |
| Stage 02D | TARGET_ATTRIBUTION_QUALIFICATION_COMPLETE | 6/6 完成分解；4 diagnostic、2 rejected。 | 0 attribution PASS；resolution/disorder 混杂。 → Stage 02E controlled excitation only | 07_reports/stage02d_final_report.md |
| Stage 02E | TARGET_CONSTRUCTION_COMPLETE | 8/8 非零且 reference audit 完整。 | 空间 assembly 为零/roundoff，时间/reference derivative 主导；0 qualified。 → Stage 02F semidiscrete spatial route only | 07_reports/stage02e_final_report.md |
| Stage 02F | SPATIAL_TARGET_QUALIFICATION_COMPLETE | 5 个非零 same-state spatial candidates；support 与 reference gates 完成。 | resolution smoothness 仍 diagnostic；0 qualified。 → Stage 02G attribution closure | 07_reports/stage02f_final_report.md |
| Stage 02G | SPATIAL_ATTRIBUTION_CLOSURE_COMPLETE | R2S bias、refinement、4/6 attribution 完整。 | R2S bias relative to target 可测但未受控；仍 diagnostic。 → Stage 02H independent reference qualification | 07_reports/stage02g_final_report.md |
| Stage 02H | REFERENCE_FIDELITY_QUALIFICATION_COMPLETE | Fourier 与 analytic 在受控 periodic-vortex scope 内独立一致并 PASS。 | 不授权 dataset；QWLS2/CWLS3 仍 diagnostic。 → Stage 02I target pool qualification | 07_reports/stage02h_final_report.md |
| Stage 02I | QUALIFIED_SPATIAL_TARGET_POOL_NOT_READY | 7/7 six-component attribution PASS；5 pair-compatible、2 node-residual-only。 | 守恒兼容性不完整，Stage 02J 未授权。 → Stage 02I-R scope resolution | 07_reports/stage02i_final_report.md |
| Stage 02I-R | CONSERVATION_COMPATIBILITY_RESOLVED_PAIR_ONLY | 五个 regular targets 确认 pair-only；jitter 保留诊断。 | 未形成 versioned dataset/split/normalization。 → Stage 02J limited regular dataset construction | 07_reports/stage02ir_final_report.md |
| Stage 02J | CONTROLLED_REGULAR_DATASET_NOT_READY | 5 records schema/canonical/QC 完整。 | 单一 leakage component，无法合法切分；0 eligible。 → Stage 02J-R independent family attempt | 07_reports/stage02j_final_report.md |
| Stage 02J-R | MULTIFAMILY_CONTROLLED_DATASET_NOT_READY | 15 candidates reference/conservation PASS，lineages 分离。 | regularity attribution 5/6 diagnostic，未物化；split/normalization blocked。 → Stage 02J-S versioned regularity contract | 07_reports/stage02jr_final_report.md |
| Stage 02J-S | VERSIONED_MULTIFAMILY_DATASET_NOT_READY | structured development paths PASS；80 invariance checks PASS。 | negative-control false-positive gate failed；held-out 未释放。 → Stage 02J-T single v0.3 candidate | 07_reports/stage02js_final_report.md |
| Stage 02J-T | REGULARITY_GATE_V03_NOT_QUALIFIED | 30 control combinations与 invariance 完成。 | CROSSMODE N12 magnitude gate failure；blind gate未开启。 → Stage 02J-V final necessity audit | 07_reports/stage02jt_final_report.md |
| Stage 02J-V | REGULARITY_HARD_GATE_ROUTE_TERMINATED | positive/hard-negative controls 与 real targets 完整。 | 9/192 invariance rows失败；禁止 v0.5。 → Stage 02J-W alternate eligibility route with regularity diagnostic-only | 07_reports/stage02jv_final_report.md |
| Stage 02J-W | BLIND_MULTIFAMILY_DATASET_READY | 20/20 reference/target/conservation/QC PASS；4 lineage components；10/5/5 split；train-only normalization。 | 仅静态 pair-scope 数据；不含 solver/rollout evidence。 → Stage 02K architecture qualification | 07_reports/stage02jw_final_report.md |
| Stage 02K | PAIR_FORCE_PIO_ARCHITECTURE_QUALIFIED | K1/K2 antisymmetry、momentum、O(2)、periodicity、differentiability、O(E d) PASS。 | 未训练；结构正确性不证明 learnability。 → Stage 02L protocol preregistration only | 07_reports/stage02k_final_report.md |
| Stage 02L | STATIC_FITTING_PROTOCOL_READY | 协议、loss、optimizer、checkpoint、test seal 完整。 | 尚无训练结果。 → Stage 02M formal static fitting | 07_reports/stage02l_final_report.md |
| Stage 02M | STATIC_PAIR_FORCE_FITTING_NOT_QUALIFIED | 9/9 runs、sealed test、postfit、resources 完整。 | K1/K2 未满足冻结 A-E，训练拟合失败。 → Stage 02M-R failure attribution only | 07_reports/stage02m_final_report.md |
| Stage 02M-R | STATIC_FITTING_FAILURE_ATTRIBUTED_OPTIMIZATION_CONDITIONING | loss scale、Adam epsilon/weight decay、梯度/更新尺度证据一致。 | 归因是 diagnostic contribution，不证明改参必成功。 → Stage 02M-P one prospective v0.2 design | 07_reports/stage02mr_final_report.md |
| Stage 02M-P | STATIC_FITTING_PROTOCOL_V02_READY | v0.2 protocol、a_sup、9-run matrix、v1.1 collection、test seal READY。 | 无训练；仅授权一次 02M-Q。 → Stage 02M-Q unique formal retry | 07_reports/stage02mp_final_report.md |
| Stage 02M-Q | STATIC_PAIR_FORCE_FITTING_V02_NOT_QUALIFIED | 9/9 conditioning/terminal/closure/test/postfit/resource evidence完整；C/D/E gates PASS。 | K1 train gate 0/3、K2 train gate 1/3；均未达 B 的2/3。 → Stage 02M-S closure only; Stage 02N unauthorized | 07_reports/stage02mq_final_report.md |
| Stage 03A | DYNAMIC_HYBRID_SOLVER_SPECIFICATION_COMPLETE | 45/45 contract hash checks；20/20 historical freeze checks；55/55 required files。 | 尚无动态实现、trajectory payload 或计算资格化。 → Stage 03B only；implementation/training/rollout 均未授权。 | stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03a_final_manifest.json |
| Stage 03B | DYNAMIC_REFERENCE_TRAJECTORY_QUALIFICATION_COMPLETE | D-R1 两族、D-R2 六例、D-R3 两族 PASS；18/18 canonical trajectories；4302 RHS/rebuilds。 | acoustic 仅 linear-regime conditional；periodic vortex 不是 exact source-free reference；D-R4 不可用。 → Stage 03C implementation only；training/neural rollout 未授权。 | stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03b_final_manifest.json |
| Stage 03C | DYNAMIC_RK2_HYBRID_IMPLEMENTATION_VERIFIED | D0 48/48；zero correction 288/288 bitwise；checkpoint 6/6；one-step autograd 6/6；全部结构/资源门 PASS。 | 未执行 multistep AD/FD、训练或 rollout 性能评价。 → Stage 03D multistep AD/FD + preregistered topology family only；training=false。 | stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03c_final_manifest.json |
| Stage 03D | DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED | 216/360 stable windows；540/540 stage conservation；TE1 birth/death、6/6 replay、12/12 event-side gradients PASS。 | 144/360 probes failure；history gradient 0/6；固定拓扑 AD/FD 与 history gate 未通过。 → Stage 03E authorization NONE；仅允许 Stage 03D-R 失败归因。 | stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03d_final_manifest.json |
| Stage 03D-R | DYNAMIC_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED | reverse/JVP 60/60；extended FD 2640 paths、30/60 stable；90 个 horizon 均 bounded/nonmonotone；topology status preserved。 | 19 unresolved；多类 FD conditioning/non-smooth/structural-zero 贡献并存；history rollout influence strongly attenuated。 → NONE；Stage 03E=false；不得立即改合同或训练。 | stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03dr_final_manifest.json |
| Stage 03D-S | STAGE03_ROUTE_PAUSED_GRADIENT_BOUNDARY_COMPLETE | 路线暂停；Stage03E=false。 | 多步梯度未资格。 → Stage04需新合同；非自动继承 | stage_03_Dynamic_SPH_Transformer_Hybrid/10_manifests/stage03ds_final_manifest.json |
| Publication P1 | PUBLICATION_EVIDENCE_LOCK_AND_DRAFT_V01_COMPLETE | 18799字；20页；claim map完成。 | 仍需外部文献定位。 → Publication P2 | publication/verification_first_dynamic_neural_sph_v0_1/10_manifests/publication_p1_final_manifest.json |
| Publication P2 | PUBLICATION_LITERATURE_VERIFICATION_AND_POSITIONING_COMPLETE | 文献核验与positioning完成。 | 项目后续Stage04仍未知。 → S1 project-wide decision dossier | publication/verification_first_dynamic_neural_sph_v0_1/11_literature_verification/manifests/publication_p2_final_manifest.json |
