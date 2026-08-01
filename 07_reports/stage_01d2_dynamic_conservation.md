# Stage 01D2 dynamic conservation

全部已接受正式轨迹的逐采样检查结果：**PASS**。原始值见每条 `trajectory_samples/*.csv` 与 `run_summaries/*.json`，涵盖 pressure/viscosity pair residual、reconstructed/assembled internal force、viscous power、momentum drift、angular diagnostic 与全部 topology defect counts。

硬门为 pair residual ≤1e-12、normalized internal force ≤1e-10、viscous power ≤1e-12 且 topology defects=0。角动量仅作诊断；未宣称非中心黏性力严格守恒角动量。
