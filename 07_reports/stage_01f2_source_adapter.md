# Stage 01F2 source adapter

`evaluate_mms_source(solution_id, numerical_positions, physical_stage_time, parameters)` 是无状态纯函数。它直接调用 Stage 01F 冻结的 `manufactured_acceleration`，不读取密度残差、压力残差、速度误差或未来 exact state，不缓存旧 Tensor，也不修改输入。

source 输出为单位质量外部加速度，保持 float64 CPU 和 PyTorch autograd。MMS-A 对 tensor-valued `U_c` 的梯度由精确平移坐标映射接入冻结模块，未复制或改写 Stage 01F source 公式。

动态接入位于新增的 sourced adapter 中。start 使用当前 `x_n,t_n`，midpoint 使用新建的 numerical `x_mid,t_n+dt/2`；每个 accepted step 恰好两次调用。每次记录 stage、stage time、position object identity、source L1/L2/Linf 和质量加权外力。source 始终与内部 pressure/viscosity pair result 分离。
