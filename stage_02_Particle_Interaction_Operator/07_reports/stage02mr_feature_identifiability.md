# Stage 02M-R — Feature identifiability

仅使用 Stage 02K 允许特征。CPU float64 canonical-byte 审计发现 `7680` 个重复 edge-feature 组，但未把非唯一 pseudoinverse edge coefficient 当作真值；edge collision 本身不构成矛盾。完全允许输入 graph collision 组数 `0`，不相容 nodal target 案例数 `0`。

冻结半径 1e-6、1e-4、1e-2 的 normalized rooted-node near-collision pair 均为 0，未事后设置阈值。结论：**NO_HARD_IDENTIFIABILITY_CONTRADICTION_FOUND**。这是“未发现硬矛盾”，不是全局唯一性证明；test target 未使用。
