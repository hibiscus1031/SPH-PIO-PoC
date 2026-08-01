# Stage 01D-R4 Gate-semantics Audit

## R3 冻结

R3 预注册提交为 `2c8c3f377b53315c2c7cb378ec4054b89b96a793`，最终证据提交为 `12bc7e4e56539cd6f14db12f4c9ee6cbe10b3f99`；annotated tag `stage-01dr3-confirmation-unresolved-weakref-semantics` target 为 `12bc7e4e56539cd6f14db12f4c9ee6cbe10b3f99`。R3 的 `R3_CONFIRMATION_UNRESOLVED` 保持不变。

## 新语义层

- `current_persistent_reference`：storage 仍属于当前 state、固定 neighborhood 或当前工作区，后续 solver 仍会读取。
- `retired_reference`：同语义对象已被替换，storage 不再属于当前 solver-readable working set。
- `old_survivor`：retired storage 在至少两个 accepted steps 后仍存活。
- `same_slot_multigeneration`：同一语义槽至少两个不同的 retired storage generations 同时存活。

只有 old-survivor 与 same-slot multigeneration 是 retention signal。单纯 age>2
不构成 retention。R3 的旧 age-2=0 规则没有修改；R4 是新的独立语义门槛。

## 证据身份

冻结输入共 `11` 项，身份/语义检查通过 `11/11`。
