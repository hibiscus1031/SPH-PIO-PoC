# Stage 02M-S — Failure taxonomy

`FAIL` means an executed hard gate failed; `NOT QUALIFIED` means a completed qualification did not satisfy the full contract; `NOT AUTHORIZED` and `NOT EXECUTED` are not failures; `DIAGNOSTIC` is not PASS; `EVIDENCE INCOMPLETE` is a provenance/completeness state.

## 1. numerical verification failure

冻结数值/独立基准硬门未通过。

Recorded instances: [{'stage': 'Stage 01G', 'state': 'FAIL', 'evidence': 'V2_QUALIFICATION_FAIL; shear failed'}]

Explicit non-instances: ['Stage 02M-Q static learnability failure']

## 2. resource/infrastructure failure

执行因资源或基础设施不能完成；受控恢复不改变科学状态。

Recorded instances: [{'stage': 'Stage 02C/02J-W', 'state': 'DIAGNOSTIC', 'evidence': 'retained controlled infrastructure retry'}]

Explicit non-instances: ['02M/02M-Q resources PASS']

## 3. reference-construction failure

reference 与目标模型/状态/不确定性合同不满足。

Recorded instances: [{'stage': 'Stage 02E', 'state': 'NOT QUALIFIED', 'evidence': 'temporal/reference derivative dominated nonzero candidates'}]

Explicit non-instances: ['Stage 02H Fourier-analytic PASS']

## 4. attribution failure

候选差异无法通过预注册分量归因。

Recorded instances: [{'stage': 'Stage 02D/02F/02G', 'state': 'DIAGNOSTIC', 'evidence': '0 qualified then 4/6 diagnostic closure'}]

Explicit non-instances: ['Stage 02I seven 6/6 candidates']

## 5. conservation-scope failure

target 不满足所选 pair-force global residual范围。

Recorded instances: [{'stage': 'Stage 02I', 'state': 'NOT QUALIFIED', 'evidence': '2 jitter node-residual-only'}]

Explicit non-instances: ['five regular pair-only targets']

## 6. family/leakage failure

lineage components不足以形成合法 split。

Recorded instances: [{'stage': 'Stage 02J/02J-R', 'state': 'NOT QUALIFIED', 'evidence': 'one realized leakage component; no eligible split'}]

Explicit non-instances: ['Stage 02J-W four components PASS']

## 7. regularity-contract failure

预注册 regularity hard gate或其 invariance/controls失败。

Recorded instances: [{'stage': 'Stage 02J-S/J-T/J-V', 'state': 'NOT QUALIFIED', 'evidence': 'negative-control, magnitude, then invariance failures'}]

Explicit non-instances: ['regularity diagnostic-only registry in J-W']

## 8. optimization-conditioning failure

loss/optimizer数值尺度导致有效更新不利。

Recorded instances: [{'stage': 'Stage 02M-R', 'state': 'DIAGNOSTIC', 'evidence': 'v0.1 failure attributed to conditioning contribution'}]

Explicit non-instances: ['proof that v0.2 must succeed']

## 9. static learnability failure

完整预注册静态训练未满足资格门。

Recorded instances: [{'stage': 'Stage 02M', 'state': 'NOT QUALIFIED', 'evidence': 'v0.1 A-E failed'}, {'stage': 'Stage 02M-Q', 'state': 'NOT QUALIFIED', 'evidence': 'K1 B=0/3; K2 B=1/3'}]

Explicit non-instances: ['universal impossibility of learned SPH corrections']

## 10. dynamic evidence absence

动态证据从未授权或执行，不是失败结果。

Recorded instances: [{'stage': 'Stage 02M-Q', 'state': 'NOT AUTHORIZED / NOT EXECUTED', 'evidence': 'rollout=0; solver-in-loop=0'}]

Explicit non-instances: ['rollout failed', 'solver unstable']

Rollout is **NOT AUTHORIZED / NOT EXECUTED**, never 'rollout failed'.
