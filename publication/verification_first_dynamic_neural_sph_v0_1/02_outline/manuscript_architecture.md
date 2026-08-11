# Evidence-locked manuscript architecture

## 论证主线

问题不是“Transformer是否提高SPH精度”，而是动态神经–SPH耦合中的守恒、时间推进、历史提交、动态图和多步梯度能否被拆分为可执行且不互相覆盖的资格合同。正文先建立公式和状态等级，再给出reference与implementation正证据，随后完整公开多步梯度负证据，最后把TE1作为独立组件处理。

## 研究问题

1. RQ1：如何把守恒、RK2、history commit与graph rebuild转化为可执行合同？
2. RQ2：zero correction、结构守恒与离散拓扑事件能否独立资格认定？
3. RQ3：固定拓扑多步rollout中的标准AD/FD资格门在哪些条件下不能形成完整证据？

## 论证顺序

Introduction → formulation → qualification framework → references → implementation → structural verification → complete multistep results → topology component → discussion/limitations → conclusions。

## 不可越界

Paper A不采用；Stage 03D NOT_QUALIFIED必须在摘要、结果和讨论可见；216/144同时报告；topology component PASS不等于整体gradient PASS；所有外部文献暂用`[REF-TODO: topic]`。
