# 项目代码审查报告

**日期**：2026-07-09
**审查范围**：47 个源文件，覆盖 app/ 全部模块

---

## 一、Critical Bugs（运行时崩溃）

### 1. `record_node.py` + `crud_health.py` — 参数不匹配导致 TypeError

`_extract_flat_record()` 返回的 dict 包含 `record_time` 字段，但 `create_health_record()` 的签名只接受 `user_id, blood_glucose, blood_pressure, symptoms`。调用 `create_health_record(**flat)` 时多余的 `record_time` 关键字会触发 `TypeError`。任何记录操作都会直接崩溃。

**涉及文件**：
- `app/nodes/record_node.py:59`
- `app/database/crud_health.py:10-15`

### 2. `rag_graph.py` — 重复定义 `_get_effective_query`

第一个定义在第 47 行，4 个 factory 闭包（`cache_lookup_node_factory`、`hybrid_retrieve_node_factory`、`rerank_documents_node_factory`、`update_cache_node_factory`）在第 74-232 行捕获了它。第二个定义（加了 blood_glucose fallback 逻辑）在第 242 行，但永远不被任何代码路径调用。血糖 fallback 修复写了但没生效。

**涉及文件**：`app/rag/rag_graph.py:47, 242`

### 3. `rag_graph.py` — return 语句后有脏代码

```python
return graph.compile()#query = state.get("rewritten_query") or state.get("user_input", "")
```

疑似合并冲突残留，第 352 行。

**涉及文件**：`app/rag/rag_graph.py:352`

---

## 二、Serious Issues（功能缺损 / 架构问题）

### 4. `app/graph/nodes.py` — 整个文件是死代码

包含旧版所有节点的完整实现（`parse_node`、`normalize_intent_node`、`record_node`、`history_node` 等），没有任何文件 import 它。和真实节点有多处不一致：

- 旧版用中文风险标签（"低"/"中"/"高"），真实版用英文（"low"/"medium"/"high"/"urgent"）
- 旧版 `record_node` 返回 mock dict，真实版调用 `create_health_record()`
- 旧版 `risk_node` 有硬编码阈值常量，真实版调用 `evaluate_risk()`
- 旧版 RAG 字段名是 `evidence_context` / `evidence`，真实版是 `retrieved_context` / `retrieved_evidence`

**建议**：直接删除。

### 5. `plan_conflict_node.py` — 硬编码 mock 数据

冲突检测不与数据库交互，用的是写死的数据：

```python
existing_plans = [
    {"tasks": [{"task": "测血糖", "time": "08:00"}]}
]
```

应改为从 `crud_plan.list_plans()` 查询真实计划。

**涉及文件**：`app/nodes/plan_conflict_node.py:8-13`

### 6. `user_confirm_node.py` + `routes.py` — 确认逻辑完全失效

`user_confirm_node` 永远返回 `True`（mock）。`routes.py` 在 workflow 执行完后才设置 `result["user_confirmed"]`，但此时流程早就过了确认节点。Human-in-the-loop 机制实际上不工作。

**涉及文件**：
- `app/nodes/user_confirm_node.py`
- `app/api/routes.py:17-18`

### 7. 两个 LLM 调用路径各自为政

| | `core/llm/client.py` | `services/llm_client.py` |
|---|---|---|
| 使用者 | parser_node, plan_draft_node | advice_node |
| 客户端 | 单例复用 | 每次 new OpenAI() |
| streaming | 支持 | 不支持 |
| enable_thinking | 可配置 | 硬编码 False |
| System prompt | 无（user message 自带） | 固定："你是一个慢性病管理助手..." |

每次 Advice 调用都重新创建 HTTP 连接池，低效且配置行为不一致。

**涉及文件**：
- `app/core/llm/client.py`
- `app/services/llm_client.py`

### 8. `app/rag_client/` — 两个文件都是空的

`client.py` 和 `schemas.py` 各只有 1 行空行。架构文档描述 RAG 为"外部 HTTP 服务"，但 client 层完全未实现。当前实际 RAG 功能在 `app/rag/rag_graph.py` 中直接实现，和架构设计不符。

**涉及文件**：
- `app/rag_client/client.py`
- `app/rag_client/schemas.py`

### 9. DB CRUD 操作缺少 rollback

所有 `crud_*.py` 都用 `try/finally: db.close()` 模式，但 error path 没有调用 `db.rollback()`。commit 失败时事务悬挂，数据库文件锁不释放，后续操作可能阻塞或读到脏数据。

**涉及文件**：
- `app/database/crud_health.py`
- `app/database/crud_plan.py`
- `app/database/crud_reminder.py`

### 10. 没有任何错误处理

LLM 调用失败（网络超时、API 限流、401 认证错误）会直接穿透 LangGraph 抛到用户端。没有 retry 机制、降级策略、或友好的错误消息包装。

**涉及文件**：
- `app/nodes/parser_node.py`
- `app/nodes/advice_node.py`
- `app/nodes/plan_draft_node.py`

---

## 三、Moderate Issues（重复代码 / 不一致）

### 11. `_normalize_plan_item` 完全重复

两个文件中有逐字相同的 37 行函数定义。

**涉及文件**：
- `app/nodes/plan_reminder_node.py:3-39`
- `app/nodes/reminder_create_node.py:7-32`

**建议**：提取到 `app/core/tools/` 下作为共享工具函数。

### 12. `reminder_router_node.py` 是纯透传 no-op

```python
def reminder_router_node(state):
    return state  # 实际路由在 routing.py
```

一个只 return state 不做任何事的节点。路由逻辑可以直接在子图入口条件边完成。

### 13. `ADVICE_PROMPT` 定义了但从未被使用

`prompts.py:221-239` 的 `ADVICE_PROMPT` 模板没有被任何文件 import。`advice_node.py` 实际使用的是内联 f-string，两个 prompt 内容完全不同。

**涉及文件**：`app/core/llm/prompts.py`

### 14. `scheduler.py` 的 `InMemoryScheduler` 单例从未被 import

`scheduler` 模块实例化了 `InMemoryScheduler` 单例，但没有任何文件引用它。`ReminderService` 直接操作 SQLite，完全绕过了调度器。整个 `scheduler.py` 和 `tasks.py` 是死代码。

**涉及文件**：
- `app/scheduler/scheduler.py`
- `app/scheduler/tasks.py`

### 15. `constants.py` 中大量常量未被引用

`CONFIRM_STATUSES`、`ERROR_CODES`、`DEFAULT_*` 等常量定义了但没有任何源代码引用它们。

**涉及文件**：`app/config/constants.py`

### 16. `schemas/` Pydantic 模型在运行时全被 dict 替代

`PlanDraft`、`PlanConflict`、`ConfirmedPlan`、`ReminderBatchCreateResult`、`WorkflowResponse`、`ErrorResponse` 等模型被定义和导出，但运行时代码全部使用 `Dict[str, Any]`。类型定义和实际行为脱节。

**涉及文件**：`app/schemas/__init__.py`

### 17. 字段名 shadow Python 内置 `type`

`BloodGlucose.type` 和 `ExerciseSlot.type` 字段名和 Python 内置 `type()` 冲突。运行时无影响，但 IDE 和静态检查工具会报警。

**涉及文件**：
- `app/schemas/health.py:19`
- `app/schemas/intent.py:43, 61`

### 18. 计划冲突检测只用精确字符串比对

`plan_conflict_rules.py` 仅当 `new_time == old_time`（精确字符串）或 `new_name == old_name` 时判定冲突。不处理：
- 时间相近（8:00 vs 8:05）
- 任务语义相似（"测血糖" vs "测空腹血糖"）
- 资源冲突（同一时间不能做两件事）

**涉及文件**：`app/core/rules/plan_conflict_rules.py`

### 19. `settings.py` 有 23 行被注释掉的旧 Settings 类

整个旧版 `BaseSettings`（含中文注释）被注释保留，应删除。

**涉及文件**：`app/config/settings.py:1-23`

### 20. `DATABASE_URL` 未在 Settings 类声明

`connection.py` 用 `getattr(settings, "DATABASE_URL", "sqlite:///...")` 兜底取值，但 Settings 类没有声明该字段。虽然 Pydantic `extra="ignore"` 允许通过，但该配置对验证、IDE 补全、文档都不可见。

**涉及文件**：
- `app/database/connection.py:10-14`
- `app/config/settings.py`

### 21. `output_parser.py` 使用裸 except

```python
except:
    cleaned = extract_json(text)
    return json.loads(cleaned)
```

裸 except 会吞掉包括 `KeyboardInterrupt` 在内的所有异常。

**涉及文件**：`app/core/llm/output_parser.py:20-25`

### 22. 节点返回 State 的方式不一致

同一个 workflow 中混用了三种模式：
- 返回 `Dict[str, Any]` 部分更新（rag_node、advice_node、history_node）
- 原地修改 state 后返回 state 对象（normalizer、parser_node、risk_node）
- spread `{**state, ...}` 后返回新 dict（record_node）

LangGraph 三种都支持，但混用容易产生隐蔽 bug。

---

## 四、Security（安全）

### 23. API 无认证

任意 client 传任意 `user_id` 即可读写任何用户的健康数据、计划、提醒。无 token、无 session、无权限校验。

**涉及文件**：`app/api/routes.py`

### 24. 无输入校验

`user_input` 通过 `PARSER_PROMPT.replace("{user_input}", ...)` 直接拼入 prompt。可被 prompt injection 攻击，且无长度限制、无内容过滤。

**涉及文件**：
- `app/nodes/parser_node.py:7`
- `app/api/routes.py`

### 25. 健康数据明文存储

SQLite 数据库和 Markdown 用户画像文件均以明文存储敏感健康数据（血压、血糖、症状），无加密。

**涉及文件**：
- `data/sqlite/chronic_care.db`
- `data/memory/users/`

### 26. API Key 可被意外泄露

Settings 对象上存储的 API Key 如果被序列化（日志、调试端点、错误堆栈），会直接暴露。

**涉及文件**：`app/config/settings.py`

---

## 五、修复优先级汇总

### P0 — 运行时崩溃 / 逻辑完全不生效（立即修复）

| # | 问题 | 涉及文件 |
|---|------|----------|
| 1 | record_time 参数不匹配导致 TypeError | record_node.py, crud_health.py |
| 2 | _get_effective_query 重复定义，fallback 不生效 | rag_graph.py |
| 3 | return 语句后有脏代码 | rag_graph.py:352 |
| 4 | app/graph/nodes.py 整文件死代码 | graph/nodes.py |

### P1 — 功能缺损（近期修复）

| # | 问题 | 涉及文件 |
|---|------|----------|
| 5 | plan_conflict_node 硬编码 mock | plan_conflict_node.py |
| 6 | user_confirm 确认链路完全失效 | user_confirm_node.py, routes.py |
| 7 | 两个 LLM 调用路径不一致 | llm/client.py, services/llm_client.py |
| 8 | rag_client 空文件 | rag_client/ |
| 9 | DB CRUD 缺少 rollback | database/crud_*.py |
| 10 | 无错误处理 | nodes/parser_node.py, advice_node.py 等 |

### P2 — 代码质量（逐步改进）

| # | 问题 |
|---|------|
| 11 | _normalize_plan_item 重复 |
| 12 | reminder_router_node 无操作节点 |
| 13 | ADVICE_PROMPT 死代码 |
| 14 | InMemoryScheduler + tasks.py 死代码 |
| 15 | constants.py 未引用常量 |
| 16 | schemas Pydantic 模型未被使用 |
| 17 | type 字段名 shadow 内置函数 |
| 18 | plan_conflict 只用精确字符串比对 |
| 19-22 | 注释旧代码清理 / 裸except / State 返回不一致 |

### P3 — 安全（上线前必须处理）

| # | 问题 |
|---|------|
| 23 | 无认证 |
| 24 | 无输入校验 / prompt injection |
| 25 | 健康数据明文存储 |
| 26 | API Key 泄露风险 |
