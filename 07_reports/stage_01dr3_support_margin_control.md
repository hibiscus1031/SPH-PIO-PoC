# Stage 01D-R3 Support-margin Control M

## 运行前几何选择

唯一壳层算法得到 `q_next=sqrt(26)=5.0990195135927845`，并在查看资源结果前冻结
`H/dx=(5+q_next)/2=5.049509756796392`。几何 margin 为
`0.049509756796392246`，初始 edge count 预登记为
`82944`。该值仅用于诊断，不是正式 V2 参数。

## 三次正常邻域重建

| run | steps | edge values | edge IDs | tensor Δ | unknown Δ | old bytes | age-2 | margin | PASS |
|---|---|---|---|---|---|---|---|---|---|
| stage01dr3_m_r1 | 2000 | 1 | 1 | 0 | 0 | 0 | 0 | 0.0495097567963283 | True |
| stage01dr3_m_r2 | 2000 | 1 | 1 | 0 | 0 | 0 | 0 | 0.0495097567963283 | True |
| stage01dr3_m_r3 | 2000 | 1 | 1 | 0 | 0 | 0 | 0 | 0.0495097567963283 | True |

所有 force stage 重新搜索邻域；edge identity 恒定，无 duplicate、nonreciprocal、
strict omission 或 unexpected edge，且最小 cutoff margin 大于预登记 `1e-12`。
