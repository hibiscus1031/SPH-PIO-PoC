# Stage 03D-S — Dynamic evidence matrix

| ID | Category | Item | Status | Frozen evidence | Interpretation boundary |
|---|---|---|---|---|---|
| A01 | A_SPECIFICATION | governing equations | **PASS** | dx/dt, dρ/dt and dv/dt with additive conservative correction frozen. | 合同证据；无性能含义。 |
| A02 | A_SPECIFICATION | causal Transformer contract | **PASS** | D3 H=4 causal scalar-history Transformer with reciprocal pair head frozen. | 候选架构，不证明必要或优越。 |
| A03 | A_SPECIFICATION | D0-D3 arm matrix | **PASS** | D0 baseline, D1 instantaneous MLP, D2 recurrent, D3 temporal Transformer roles frozen. | 未训练、未比较性能。 |
| A04 | A_SPECIFICATION | RK2/history/graph semantics | **PASS** | Start/midpoint graph rebuild and one accepted-state history commit specified. | 语义合同与实现证据分层。 |
| A05 | A_SPECIFICATION | reference hierarchy | **PASS** | D-R1 through D-R4 roles and disallowed uses frozen. | D-R4 remains NOT_AVAILABLE. |
| B01 | B_REFERENCE | D-R1 analytic/MMS closure | **PASS** | Two D-R1 families passed analytic closure and produced six exact trajectories. | MMS verifies equations/code, not physical validation. |
| B02 | B_REFERENCE | D-R2 time-reference sensitivity | **PASS** | Six same-semidiscrete DOP853 cases passed. | Isolates time error; not spatial truth. |
| B03 | B_REFERENCE | D-R3 source-free exact reference | **PASS** | Two oblique-shear families passed and yielded six exact trajectories. | Independent validation only; forbidden for training/threshold selection. |
| B04 | B_REFERENCE | acoustic boundary | **DIAGNOSTIC** | Classified DR3_ACOUSTIC_LINEAR_REGIME_CONDITIONAL. | Not an unrestricted exact D-R3 family. |
| B05 | B_REFERENCE | periodic vortex boundary | **NOT_QUALIFIED** | Rejected as exact source-free reference due to momentum/EOS mismatch. | May only support a separately sourced MMS role. |
| C01 | C_IMPLEMENTATION | independent RK2 | **PASS** | Independent RK2 comparison 48/48. | Implementation verification only. |
| C02 | C_IMPLEMENTATION | zero correction | **PASS** | 288/288 bitwise equivalence; no post-hoc tolerance. | Does not prove nonzero correction accuracy. |
| C03 | C_IMPLEMENTATION | conservation/equivariance | **PASS** | Reciprocal antisymmetry, conservation, O(2), permutation and periodic checks passed. | Structural property, not learned performance. |
| C04 | C_IMPLEMENTATION | checkpoint/resume | **PASS** | Six configurations reproduced state, graph, history and RNG identity. | No trained checkpoint exists. |
| C05 | C_IMPLEMENTATION | one-step autograd | **PASS** | 6/6 one-step runs returned finite nonzero expected gradients. | No finite difference and no multistep qualification in Stage 03C. |
| C06 | C_IMPLEMENTATION | resources | **PASS** | CPU float64 resource audit passed. | Resource record is not a speed or cost comparison. |
| D01 | D_MULTISTEP_GRADIENT | 360 frozen probes | **NOT_QUALIFIED** | 216 PASS and 144 failure rows; 2880 AD/FD comparisons. | Complete gradient qualification failed. |
| D02 | D_MULTISTEP_GRADIENT | stable epsilon windows | **DIAGNOSTIC** | 216/360 probes had a stable adjacent window. | Cannot report only the passing subset. |
| D03 | D_MULTISTEP_GRADIENT | reverse/JVP crosscheck | **PASS** | 60/60 same-math-backend reverse/JVP comparisons passed. | Supports AD implementation consistency, not complete AD/FD validity. |
| D04 | D_MULTISTEP_GRADIENT | extended finite difference | **DIAGNOSTIC** | 2640 FD paths; 30/60 selected paths stable. | Conditioning contribution remains path dependent. |
| D05 | D_MULTISTEP_GRADIENT | history influence | **UNRESOLVED** | 1 HISTORY_FD_CONDITIONING_LIMITED and 5 HISTORY_SENSITIVITY_BELOW_FD_RESOLUTION. | Strong rollout attenuation is observed; long-chain trainability is not established. |
| D06 | D_MULTISTEP_GRADIENT | backend sensitivity | **DIAGNOSTIC** | Historical default backend disagreed with math JVP on 12/60, all in D3 selected probes. | Conditional diagnostic; no backend switch or requalification authorized. |
| D07 | D_MULTISTEP_GRADIENT | failure attribution | **UNRESOLVED** | 144 failures split across seven reasons, including 19 unresolved. | Mixed contributors; no single complete root cause. |
| D08 | D_MULTISTEP_GRADIENT | horizon scaling | **DIAGNOSTIC** | 90/90 traces classified bounded or nonmonotone. | No systematic vanishing/exploding detected, not proof of healthy training gradients. |
| D09 | D_MULTISTEP_GRADIENT | dynamic training | **NOT_EXECUTED** | optimizer steps=0; training runs=0; performance evaluations=0. | Must not be called training failure. |
| E01 | E_TOPOLOGY | TE1 birth/death | **PASS** | One deterministic edge birth and one death recorded. | Discrete edge existence is not differentiable. |
| E02 | E_TOPOLOGY | replay | **PASS** | 6/6 topology-stage replays passed. | Qualification is for TE1 semantics. |
| E03 | E_TOPOLOGY | event-side gradients | **PASS** | 12/12 fixed-side gradients passed. | Gradients are within a fixed event side, not through cutoff membership. |
| E04 | E_TOPOLOGY | piecewise-smooth boundary | **PASS** | Finite bounded force jumps and deterministic empty-graph behavior established. | Topology map remains piecewise smooth with discrete events. |

The matrix deliberately keeps `DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED` and `TOPOLOGY_EVENT_COMPONENT_QUALIFIED` as different levels of verdict.
