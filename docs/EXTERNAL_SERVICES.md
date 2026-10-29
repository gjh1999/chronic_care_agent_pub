# 外部模型服务接入契约

慢病管理 Agent 不在自身进程内加载 LoRA 权重或 RAG 索引。调用顺序为：

```text
用户输入
  -> Medical_Lora POST /v1/intent/parse
  -> LangGraph 路由、规则和业务节点
  -> RAG POST /v1/retrieve（仅建议/计划链需要）
  -> 通用 LLM 生成建议或计划
```

## 1. Medical_Lora 意图服务

- 项目目录：`C:\Users\gjh\PycharmProjects\Medical_Lora`
- 建议监听：`127.0.0.1:8020`
- 模型：`training/qwen_routing_lora_final`
- 基座：`Qwen2.5-7B-Instruct`（以 adapter_config.json 为准）

### 健康检查

`GET /healthz`，服务与模型均就绪时返回 HTTP 200。

### 意图解析

`POST /v1/intent/parse`

请求：

```json
{
  "text": "记录今天空腹血糖 7.2，并给我一些建议",
  "user_id": "可选",
  "conversation_id": "可选"
}
```

响应可直接返回下列对象，也可放在 `{ "code": 0, "data": {...}, "message": "ok" }` 的 `data` 中：

```json
{
  "routing": {
    "need_record": true,
    "need_advice": true,
    "need_plan": false,
    "need_reminder": false,
    "need_history": false
  },
  "confidence": {
    "need_record": 0.99,
    "need_advice": 0.95,
    "need_plan": 0.01,
    "need_reminder": 0.01,
    "need_history": 0.01
  },
  "slots": {
    "record": {
      "blood_glucose": {"value": 7.2, "unit": "mmol/L", "type": "fasting", "time": "今天"}
    }
  },
  "missing_fields": [],
  "risk_flags": [],
  "normalized": {"date": null, "time_of_day": null, "units": {}}
}
```

该服务位于 LangGraph 最前面，属于必需依赖。超时、非 2xx、非法 JSON 或 Schema 不匹配均终止本次工作流，不能静默改用通用 LLM，以免路由错误导致错误写记录或创建提醒。

## 2. RAG 检索服务

- 项目目录：`C:\Users\gjh\PycharmProjects\RAG`
- 建议监听：`127.0.0.1:8010`
- 运行时：现有 `retrieval_runtime.runtime.RetrievalRuntime`
- 知识库：现有 `medical_guidelines` BM25、FAISS 与 snapshot

### 健康检查

`GET /healthz`，索引与检索运行时就绪时返回 HTTP 200。

### 检索

`POST /v1/retrieve`

请求核心字段：

```json
{
  "query": "高血压患者日常饮食需要注意什么？",
  "context": {
    "user_id": "可选",
    "conversation_id": "可选",
    "metadata": {"health_record": {}, "history_data": [], "risk_level": "low"}
  },
  "top_k": 5,
  "enable_cache": true,
  "enable_rewrite": true,
  "enable_expand": true,
  "enable_rerank": true,
  "enable_consistency_check": false,
  "enable_multi_model_check": false,
  "metadata_filters": {},
  "debug": false
}
```

响应也支持直接对象或统一响应包装：

```json
{
  "query": "高血压患者日常饮食需要注意什么？",
  "rewritten_queries": [],
  "expanded_queries": [],
  "evidence": [
    {
      "evidence_id": "guideline-1",
      "text": "证据正文",
      "source": "中国高血压防治指南",
      "score": 0.91,
      "metadata": {}
    }
  ],
  "cache_hit": false,
  "suggested_action": "continue",
  "needs_human_confirmation": false,
  "errors": []
}
```

RAG 默认 `RAG_FAIL_OPEN=true`：服务不可用时仍可执行本地风险规则与响应链，但不会伪造医学证据，并在工作流状态中写入 `rag_error`。

## 3. 当前 Agent 配置

```dotenv
INTENT_BASE_URL=http://127.0.0.1:8020
INTENT_API_KEY=
INTENT_TIMEOUT=60

RAG_BASE_URL=http://127.0.0.1:8010
RAG_API_KEY=
RAG_TIMEOUT=45
RAG_TOP_K=5
RAG_FAIL_OPEN=true
```

若配置 API Key，Agent 会发送 `Authorization: Bearer <key>`。`GET /dependencies` 同时报告两个服务的连通状态，但只表示健康接口可访问，不等同于一次真实检索成功。

## 4. 启动顺序

1. 启动 RAG 服务并确认 `http://127.0.0.1:8010/healthz` 返回 200。
2. 启动 Medical_Lora 服务并确认 `http://127.0.0.1:8020/healthz` 返回 200。
3. 启动本项目：`uvicorn app.main:app --reload --port 8000`。
4. 访问 `http://127.0.0.1:8000/dependencies`，确认两项均为 `up`。

RAG 项目已经提供 `/healthz`、`/readyz` 和 `/v1/retrieve`。真实端到端联调仍需确保意图服务已启动，并显式启用集成测试开关。
