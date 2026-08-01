# Stage 01F governing-equation contract

Stage 01E tag `stage-01e-model-form-alignment-dominant` 固定于 `de0016ae2623ec0f03d1bd8486a8833dd185f3b2`；历史分类保持 `E_MODEL_FORM_ALIGNMENT_DOMINANT`。

连续目标固定为 `dx/dt=u`，`partial_t rho + div(rho u)=0`，`partial_t u+(u·grad)u=-(1/rho)grad(p)+nu laplacian(u)+f_MMS`，以及 `p=c_s^2(rho-rho0)`。

`f_MMS` 是单位质量外部加速度，不是内部粒子对力，不要求成对反对称。内部压力/黏性守恒与外力分开审计；受迫问题比较 `d/dt sum_i(m_i u_i)` 与 `sum_i(m_i f_MMS_i)`，不要求总动量恒定。source 不依赖数值误差、SPH residual 或网络输出。
