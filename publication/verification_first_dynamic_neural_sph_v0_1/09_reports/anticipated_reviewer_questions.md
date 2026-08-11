# Anticipated reviewer questions — evidence-locked answers

## 1. 为什么没有训练？

Stage 03D的完整多步AD/FD门未资格化，history为0/6；冻结路线规定Stage 03E authorization=false。因此训练未获授权且未执行。本文研究问题是资格链及梯度边界，不是训练性能。

## 2. 为什么NOT_QUALIFIED仍值得发表？

NOT_QUALIFIED本身不是论文价值的充分条件；价值来自预注册式合同、完整360-row公开、正负证据分层、mixed/unresolved归因和可复用的topology-event审计。正文不把失败包装成成功。

## 3. MMS是否构成物理验证？

不构成。D-R1只用于方程、源项与实现verification；无源independent validation由D-R3 oblique shear承担，D-R4仍缺失。

## 4. DOP853是否是真值？

不是连续方程真值。D-R2是同半离散系统的高精度时间参考，用于隔离时间推进误差，空间离散误差仍共享。

## 5. 144个失败是否说明实现错误？

不能直接这样判断。Stage 03C实现门通过，reverse/JVP 60/60也支持同后端AD一致；144个失败包含FD conditioning、接近结构零、固定图数值非光滑、方向不一致及19未决。总体结论仍是NOT_QUALIFIED，而不是“实现无误”或“求解器全部失败”。

## 6. 为什么topology组件可以单独PASS？

TE1使用独立合同检查birth/death、replay、fixed-side gradients、force jumps和empty graph。组件证据可独立满足，而固定拓扑多步梯度门仍失败；状态层级不同。

## 7. cutoff membership为何不可微？

edge membership由距离与cutoff的离散比较确定，crossing时图集合发生跳变。事件两侧分支可piecewise smooth，但edge存在性本身不是普通连续变量。

## 8. 为什么不切换attention backend后重跑？

这会改变冻结实现/AD合同并构成新的资格campaign。P1只报告既有48/60 match与12/60 sensitivity；统一后端或custom JVP属于未来新Stage 04假设。

## 9. 是否存在选择性报告？

没有。主文与图6同时显示216 PASS和144 failure，failure taxonomy包含19 unresolved；补充材料规划完整360 rows、2880 comparisons和2640 extended paths。

## 10. 方法能否推广到其他SPH实现？

当前不能声称已推广。可迁移的是合同结构与审计逻辑；数值一般性仍受单项目实现限制，需跨代码/问题族验证。

## 11. 是否达到CMAME的方法创新深度？

主题与meshless、fluid mechanics和physically based ML方向相容，但当前证据不支持“CMAME ready”。需要证明verification framework的跨实现一般性，并补足独立验证；当前分类为`METHODS_PAPER_DRAFTABLE_WITH_CLAIM_LIMITATION`。

## 12. 缺少性能对比是否致命？

对完整求解器论文是核心缺口；对严格定位的方法/验证论文，不必伪造性能结论，但必须把范围限定在verification architecture与negative gradient evidence，并避免暗示solver improvement。
