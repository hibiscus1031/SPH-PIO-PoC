# Stage 03B acoustic and vortex boundary

## Acoustic candidate

新 candidate 是 frozen `nu` 下的一维 viscous isothermal linear eigenmode，使用 epsilon=1e-4、2e-4、4e-4。Linearized continuity residual 为 0，linearized momentum 最大 3.33e-16；full nonlinear continuity residual 分别为 6.28e-7、2.51e-6、1.01e-5，epsilon slope=2.0000；full momentum residual 为 1.97e-8、7.91e-8、3.18e-7，slope=2.0055。

因此分类为 **`DR3_ACOUSTIC_LINEAR_REGIME_CONDITIONAL`**。它不是 `FULL_NONLINEAR_EXACT_REFERENCE`，也不是 Stage 03B 必需 PASS family。

## Periodic vortex candidate

在冻结 isothermal EOS 下以 constant density/p=0 审计 periodic TGV decay。Continuity residual 为 0，unsteady-viscous balance 为 2.78e-17，但 convective term Linf=0.251327、full momentum residual Linf=0.355073；所需 incompressible pressure 与 EOS pressure 的 Linf mismatch=0.08。

因此分类为 **`DR3_PERIODIC_VORTEX_REJECTED_AS_EXACT_SOURCE_FREE_REFERENCE`**；只允许未来在明确 source 下作为 `DR1_PERIODIC_VORTEX_MMS_ONLY` 重新立项。Stage 01E model-form mismatch 未被覆盖。
