# Publication P1 — Figure package plan

P1采用附件允许的详细设计路径；未指定Python/R投稿绘图后端，因此本轮不生成最终科研图。每幅图已锁定证据输入、面板结构和完整性规则。

| Figure | 标题 | 形式 | 完整性规则 | 文件 |
|---:|---|---|---|---|
| 1 | Stage 03 verification-first pipeline | workflow | 显示03A–03D-S时序及独立topology分支；Stage 03E=false。 | P1_DETAILED_DESIGN |
| 2 | D0–D3 dynamic architecture | architecture schematic | 不编码优越性；显示共享RK2/history/reciprocal head合同。 | P1_DETAILED_DESIGN |
| 3 | RK2 graph rebuild and history commit | state-transition schematic | start/midpoint各重建图，accepted state仅commit一次。 | P1_DETAILED_DESIGN |
| 4 | D-R1/D-R2/D-R3 reference hierarchy | evidence hierarchy | 保留MMS、time reference、source-free及拒绝边界。 | P1_DETAILED_DESIGN |
| 5 | Zero-correction and structural qualification matrix | status matrix | bitwise/structural与performance分离。 | P1_DETAILED_DESIGN |
| 6 | Complete 360-probe AD/FD outcome matrix | complete matrix | 显示全部360 rows、216 PASS与144 failure。 | P1_DETAILED_DESIGN |
| 7 | History attenuation and backend sensitivity | diagnostic panels | 条件性措辞；不声称可训练。 | P1_DETAILED_DESIGN |
| 8 | TE1 edge birth/death and piecewise-smooth boundary | event schematic | 不把edge existence画成可微。 | P1_DETAILED_DESIGN |
| 9 | Supported/conditional/unsupported claim map | claim map | 包含training/rollout NOT EXECUTED。 | P1_DETAILED_DESIGN |

禁止图件：训练曲线、rollout误差曲线、speedup、模型准确率或只包含216个PASS的选择性图。
