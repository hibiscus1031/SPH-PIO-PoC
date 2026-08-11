# Reviewer positioning report

## 1. 最接近的论文

最接近的直接工作是JAX-SPH [V002]、diffSPH [V004]、Neural SPH [V003]、parameterized learnable SPH [V001]、DMCF [V022]、LagrangeBench [V024]、GNS [V013]与solver-in-the-loop [V016]。其中JAX-SPH已具有5步AD/FD和SPH SitL，diffSPH覆盖更长梯度链与更广应用；二者是最需要正面比较的竞争工作。

## 2. 当前工作增加什么

增加的是冻结的zero-correction bitwise identity、RK2 start/midpoint重建、accepted-only history commit、360-probe stable-window矩阵、reverse/JVP与extended FD归因，以及cutoff birth/death的event-side资格分支。措辞必须限定为“within the verified literature set”。

## 3. 当前工作缺少什么

缺少训练、autonomous rollout、误差、长期稳定性、外推、速度、equal-error cost、跨实现复现和D-R4独立验证；这些正是V003、V004、V013、V022、V024通常提供的性能层证据。

## 4. 最可能被视为工程审计的部分

checkpoint、hash、history事务和bitwise fallback若只在单一代码库展示，容易被认为是软件QA。需要用失败可诊断性、跨架构适用性和第二实现复现证明方法一般性。

## 5. 如何证明一般性

在至少两种SPH实现、两类邻域算法、多个边界/分辨率和两种AD后端复现同一合同；公开probe生成器、阈值依据与失败矩阵；预注册新增topology families。

## 6. negative result为何有方法价值

216/360与144 failures表明选择性展示成功梯度会改变授权结论。完整矩阵可区分局部实现PASS、总体NOT_QUALIFIED和topology component PASS，防止把部分成功转化为训练许可。

## 7. 未训练为何不是规避实验

训练明确依赖Stage 03D资格，而Stage 03D未通过；停止符合预注册路线。但这仍是论文限制，不能替代后续性能实验。

## 8. 必须弱化的结论

不得主张首次可微SPH、首次solver-in-the-loop、模型可训练、性能提高、长时稳定、edge membership可微、角动量/能量守恒或一般topology资格。

## 9. 期刊层级

当前比完整solver型CMAME更现实的是computational methods、verification/validation、Scientific ML methods或software/methodology取向期刊。是否适合具体期刊需在投稿时复核最新scope。

## 10. 升级为完整CMAME论文所需证据

重新授权后的训练资格、自主rollout、跨问题泛化、精度–成本曲线、长期守恒/稳定性、独立参考/实验验证、第二代码实现以及对现有JAX-SPH/diffSPH/Neural SPH的公平复现比较。Stage 03D当前状态必须继续写为`DYNAMIC_MULTISTEP_ADFD_AND_TOPOLOGY_NOT_QUALIFIED`。
