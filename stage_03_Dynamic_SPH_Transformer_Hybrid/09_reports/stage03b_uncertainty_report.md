# Stage 03B trajectory-reference uncertainty

D-R1 分开保留 analytic derivative disagreement、symbolic float64 roundoff 与 material-map chain-rule disagreement。两族最大 route disagreement 分别为 7.37e-14 和 1.85e-13；MMS exactness 未被解释为 physical-validation uncertainty。

D-R2 每个 case 分开保留 primary/sensitivity field errors、deterministic summation、output interpolation 与 topology sequence。冻结 max-step 下 tolerance sensitivity 为 bitwise zero；这只限定时间参考不确定性，不能作为 spatial uncertainty。DOP853-versus-exact 差异另存为 semidiscrete spatial/model-form diagnostic。

D-R3 分开保留 source-free analytic closure roundoff、particle-path evaluation 和 periodic representative。A/B 最大 closure roundoff 分别为 1.24e-16 与 1.40e-16。

未合并单一 total GCI，未生成或伪造 spatial GCI，未将 MMS closure 升格为 physical validation。
