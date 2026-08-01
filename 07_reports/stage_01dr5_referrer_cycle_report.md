# Stage 01D-R5 Pre-GC Referrer-cycle Report

引用图在 retired 对象仍存活且调用 `gc.collect()` 之前捕获，最大深度 4；只保留类型、
attribute/key 名称、module 与 ownership 标志，排除了审计自身的 frame/list/queue。

| representative | nodes | edges | cycle localized | cycle type paths |
|---|---|---|---|---|
| unresolved:endpoint_neighborhood.displacement | 20 | 19 | False | [] |
| unresolved:endpoint_neighborhood.distance | 20 | 19 | False | [] |
| unresolved:endpoint_neighborhood.edge_support | 20 | 19 | False | [] |
| unresolved:midpoint_neighborhood.displacement | 4 | 3 | False | [] |
| unresolved:midpoint_neighborhood.distance | 4 | 3 | False | [] |
| unresolved:midpoint_neighborhood.edge_support | 4 | 3 | False | [] |
| unresolved:old_state.densities | 8 | 7 | False | [] |
| unresolved:old_state.positions | 8 | 7 | False | [] |
| unresolved:old_state.pressures | 8 | 7 | False | [] |
| unresolved:old_state.velocities | 8 | 7 | False | [] |
| unresolved:start_stage_neighborhood.displacement | 16 | 15 | False | [] |
| unresolved:start_stage_neighborhood.distance | 16 | 15 | False | [] |
| unresolved:start_stage_neighborhood.edge_support | 7 | 6 | False | [] |

明确闭环已定位=`False`。若表中没有 cycle type path，
本阶段不声称定位到具体闭环。
