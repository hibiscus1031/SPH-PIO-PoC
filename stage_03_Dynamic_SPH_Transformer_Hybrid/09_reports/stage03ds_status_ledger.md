# Stage 03D-S — Complete status ledger

| Stage | Unique status | Execution count | Principal PASS evidence | Principal blocker | Downstream authorization | Steps / runs / performance |
|---|---|---:|---|---|---|---:|
| Stage 03A | `DYNAMIC_HYBRID_SOLVER_SPECIFICATION_COMPLETE` | 0 (specification_only) | 45/45 contract hash checks；20/20 historical freeze checks；55/55 required files。 | 尚无动态实现、trajectory payload 或计算资格化。 | Stage 03B only；implementation/training/rollout 均未授权。 | 0 / 0 / 0 |
| Stage 03B | `DYNAMIC_REFERENCE_TRAJECTORY_QUALIFICATION_COMPLETE` | 1 (reference_qualification_campaign) | D-R1 两族、D-R2 六例、D-R3 两族 PASS；18/18 canonical trajectories；4302 RHS/rebuilds。 | acoustic 仅 linear-regime conditional；periodic vortex 不是 exact source-free reference；D-R4 不可用。 | Stage 03C implementation only；training/neural rollout 未授权。 | 0 / 0 / 0 |
| Stage 03C | `DYNAMIC_RK2_HYBRID_IMPLEMENTATION_VERIFIED` | 1 (implementation_qualification_campaign) | D0 48/48；zero correction 288/288 bitwise；checkpoint 6/6；one-step autograd 6/6；全部结构/资源门 PASS。 | 未执行 multistep AD/FD、训练或 rollout 性能评价。 | Stage 03D multistep AD/FD + preregistered topology family only；training=false。 | 0 / 0 / 0 |
| Stage 03D | `DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED` | 1 (formal_multistep_gradient_and_topology_campaign) | 216/360 stable windows；540/540 stage conservation；TE1 birth/death、6/6 replay、12/12 event-side gradients PASS。 | 144/360 probes failure；history gradient 0/6；固定拓扑 AD/FD 与 history gate 未通过。 | Stage 03E authorization NONE；仅允许 Stage 03D-R 失败归因。 | 0 / 0 / 0 |
| Stage 03D-R | `DYNAMIC_GRADIENT_FAILURE_MIXED_OR_UNRESOLVED` | 1 (forensic_attribution_campaign) | reverse/JVP 60/60；extended FD 2640 paths、30/60 stable；90 个 horizon 均 bounded/nonmonotone；topology status preserved。 | 19 unresolved；多类 FD conditioning/non-smooth/structural-zero 贡献并存；history rollout influence strongly attenuated。 | NONE；Stage 03E=false；不得立即改合同或训练。 | 0 / 0 / 0 |

## Non-override rule

Stage 03D-R is a diagnostic attribution stage. It does **not** override, repair, supersede or convert the Stage 03D failure verdict. All five rows have `superseded=false`.
