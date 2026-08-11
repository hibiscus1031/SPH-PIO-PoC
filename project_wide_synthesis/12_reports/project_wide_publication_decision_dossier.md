# 全项目发表决策案卷

## 当前证据判定

[PROJECT_EVIDENCE] Stage00–03可以支撑verification-first方法/负结果论文；不能支撑训练、rollout、solver improvement或Transformer superiority论文。

## 推荐顺序

1. [PUBLICATION_RECOMMENDATION] 现在优先准备Option C/Paper1主线。
2. Stage04完成后只导入delta并匹配六场景。
3. 仅当Scenario5证据完整时优先评估单篇CMAME整合；否则保持两篇或verification-only。

## 决策护栏

- Stage01 V2失败、Stage02 static route termination、Stage03 multistep gradient NOT_QUALIFIED必须在摘要/正文可见。
- topology component PASS不得覆盖overall gradient failure。
- 所有外部新颖性措辞服从P2；其余标记LITERATURE_VERIFICATION_REQUIRED。
- overlap matrix是拆稿前置硬门。

## 选项矩阵

| Option | 触发条件 | 价值 | 风险 | 建议 |
|---|---|---|---|---|
| A | Stage04 E/F/G strong PASS + independent validation/refinement/cost | complete end-to-end narrative | highest dependency and length | conditional |
| B | Stage00–03 methods generalizable and Stage04 has distinct performance question | clear contribution separation | overlap/self-plagiarism | preferred default after a successful but distinct Stage04 |
| C | Stage04 gradients/training/rollout not qualified | independent verification and negative-result value | must avoid solver-success framing | preferred fallback |
