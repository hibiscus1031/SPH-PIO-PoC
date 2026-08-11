# P2 literature search protocol

- 截止日期：2026-08-05。
- 数据源：Crossref REST用于可复现发现与精确DOI元数据；出版商/正式会议页面用于题录和方法核验；DOI resolver用于交叉一致性；arXiv仅用于预印本身份与开放全文；搜索引擎仅用于发现。
- 七组检索：T1 SPH/ML correction；T2 learned particle dynamics；T3 conservative/equivariant architectures；T4 differentiable solvers/gradient verification；T5 dynamic topology events；T6 Scientific ML V&V；T7 SPH verification。
- 查询：35条精确查询，逐条记录在`search_query_log.csv`；每条保留Crossref reported result count、screened count与retained raw count。
- 规模：raw=454；verified=87；core=40。核心主题计数（允许跨组重复）={'T1': 7, 'T3': 7, 'T4': 9, 'T5': 2, 'T2': 9, 'T6': 5, 'T7': 11}。
- 题录门：有DOI者要求Crossref exact DOI与DOI resolver一致；无独立DOI的正式会议论文要求publisher/conference official page与arXiv/第二官方记录一致。
- 证据门：CORE-A/B逐篇建立evidence note；无法访问正文时明确`ABSTRACT_ONLY`或`METADATA_ONLY`，不用于强方法推断。
- 去重：正式版优先，预印本只记录关系，不作为独立参考；撤稿/重复/纠正条目进入rejected清单。
- 排除原因：每条仅记录一个主原因；ResearchGate、聚合转载和搜索摘要不作为最终题录依据。
