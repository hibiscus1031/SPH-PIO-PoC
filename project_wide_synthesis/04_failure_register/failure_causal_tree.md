# 失败因果树

```text
PROJECT_ROUTE
├─ Stage01 V&V
│  ├─ V1实现/结构失败 → Stage01C修复
│  └─ V2模型形式/有限分辨率 → MMS与独立验证边界
├─ Stage02 static PIO
│  ├─ target/reference/data门 → blind static dataset
│  ├─ regularity硬门证伪 → diagnostic-only
│  └─ static fitting未资格 → 路线终止
├─ Stage03 dynamic hybrid
│  ├─ implementation qualified
│  ├─ multistep gradient NOT_QUALIFIED → Stage03E未授权
│  └─ topology QUALIFIED_COMPONENT
└─ training/rollout/performance → NOT_AUTHORIZED/NOT_EXECUTED
```

[INFERENCE] 树表达因果依赖，不把后续修复当作历史失败消失。
