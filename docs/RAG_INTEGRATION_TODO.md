# 慢病管理 Agent 接入外部 RAG 服务改造说明

## 1. 目标与方案

本项目通过 HTTP 调用独立 RAG 服务：

```text
用户请求
  -> 意图服务
  -> LangGraph 规则与业务节点
  -> RAG POST /v1/retrieve
  -> 通用 LLM 基于证据生成建议
```

RAG 项目位置：

```text
C:\Users\gjh\PycharmProjects\RAG
```

推荐保持外部服务模式，不在本项目进程内导入 RAG 包、加载 FAISS 索引或持有 RAG 模型依赖。

## 2. 当前已完成部分

本项目已经具备：

- `app/rag_client/schemas.py`：RAG 请求与响应模型；
- `app/rag_client/client.py`：同步 HTTP 客户端；
- `app/nodes/rag_node.py`：工作流 RAG 节点；
- `RAG_BASE_URL`、`RAG_API_KEY`、`RAG_TIMEOUT`、`RAG_TOP_K`、`RAG_FAIL_OPEN` 配置；
- `/dependencies` 外部依赖状态检查；
- RAG 不可用时的 fail-open 基础逻辑；
- 客户端 MockTransport 单元测试。

HTTP 字段与 RAG 内部 `RetrievalRequest`、`RetrievalResponse` 基本一致，但工作流和部署仍有关键问题需要修复。

## 3. 必须修改：RAG 节点读取错误的路由字段

`normalize_intent_node()` 会把建议类请求补全为：

```python
intent_flags["need_rag"] = True
```

但是 `app/nodes/rag_node.py` 当前检查：

```python
intent = state.get("intent", {})
if not intent.get("need_rag", False):
    # 跳过 RAG
```

外部意图服务的 `RoutingResult` 没有 `need_rag` 字段，因此真实建议请求在经过 normalize 后，RAG 节点仍可能被错误跳过。

修改为读取规范化标志：

```python
flags = state.get("intent_flags", state.get("intent", {}))

if not flags.get("need_rag", False):
    ...
```

发送给 RAG 的 metadata 中，`intent` 建议传规范化后的 `flags`，或者同时传入 `raw_intent` 与 `intent_flags`，避免上下文与实际路由不一致。

## 4. 必须修改：处理 RAG 的质量信号

当前 `rag_node` 只要 HTTP 调用成功，就会把全部 evidence 格式化进 `rag_context`，没有根据以下字段做决策：

- `suggested_action`；
- `needs_human_confirmation`；
- `final_quality`；
- `errors`。

建议增加明确策略：

| suggested_action | 主项目行为 |
|---|---|
| `continue` | 允许 evidence 进入建议生成 |
| `retry_done` | 允许使用，但保留质量信息 |
| `ask_user_clarification` | 不生成确定性医学建议，提示用户补充信息 |
| `evidence_insufficient` | 清空 `rag_context`，进入无证据降级 |
| `need_human_confirmation` | 不把证据描述成确定结论，提示需医生确认 |
| 未知值 | 按不可信处理并记录错误 |

至少增加以下状态字段：

```python
rag_suggested_action: str
rag_needs_human_confirmation: bool
rag_quality_passed: bool | None
```

并在 `ClinicalState` 中声明这些字段。

## 5. 必须修改：无证据时的建议生成策略

当前 `advice_node` 即使 `rag_context` 为空，也会继续调用通用 LLM。`RAG_FAIL_OPEN=true` 可以保留本地风险规则和非医学性的通用交互，但不能让模型在没有依据时生成看似有医学证据支持的结论。

建议区分：

1. RAG 正常且质量通过：基于 evidence 生成建议；
2. RAG 不可用：仅输出本地规则已确认的信息、就医提示和服务不可用说明；
3. RAG 证据不足：提示无法从知识库找到足够依据，可要求用户补充信息；
4. 紧急风险：继续由规则节点直接拦截，不等待 RAG 或 LLM；
5. 需要人工确认：明确提示咨询医生，不生成诊断或用药调整。

建议在提示词中加入结构化证据状态，而不只是拼接 `rag_context`。

## 6. 客户端改进

### 6.1 超时拆分

当前使用一个总 timeout。建议拆分为 connect/read/write/pool，避免连接失败等待完整的 45 秒：

```python
httpx.Timeout(
    connect=3.0,
    read=settings.rag_timeout,
    write=10.0,
    pool=3.0,
)
```

### 6.2 客户端生命周期

模块导入时创建了全局 `httpx.Client`，但应用退出时没有关闭。建议在 FastAPI lifespan 中统一创建和关闭外部客户端，或者提供应用 shutdown 清理逻辑。

### 6.3 错误分类

建议至少区分：

- 连接失败；
- 超时；
- HTTP 4xx；
- HTTP 5xx；
- 非法 JSON；
- 响应 Schema 不匹配；
- RAG 业务错误。

对外返回的信息不能包含 Authorization Header、API Key 或完整的内部堆栈。

### 6.4 重试

只对连接错误、读取超时和部分 5xx 做最多一次短重试。不要对 4xx、Schema 错误或长时间检索无条件重试，避免放大请求和模型费用。

## 7. Schema 与契约调整

`app/rag_client/schemas.py` 应继续兼容 RAG 完整响应，并建议增加约束：

```python
query: str = Field(min_length=1)
top_k: int = Field(default=5, ge=1, le=20)
score: float
```

对 `suggested_action` 使用 `Literal` 枚举，避免拼写错误被静默接受。

主项目将 `top_k` 定义为“最终最多返回的 evidence 数量”。RAG 服务必须采用相同语义。若 RAG 服务需要控制内部召回数量，应使用单独的服务端配置。

主项目当前支持裸响应和 `{code,data,message}` 包装，可以暂时保留；推荐最终统一为裸 `RetrievalResponse`，减少契约分支。

## 8. 配置修改

本地开发配置：

```dotenv
RAG_BASE_URL=http://127.0.0.1:8010
RAG_API_KEY=
RAG_TIMEOUT=45
RAG_TOP_K=5
RAG_FAIL_OPEN=true
```

如果 RAG 服务开启鉴权，两边的 `RAG_API_KEY` 必须一致。

生产环境建议：

```dotenv
RAG_FAIL_OPEN=false
```

是否关闭 fail-open 取决于产品策略。即使保留 `true`，无 RAG 证据时也必须限制回答内容，不能伪造指南依据。

`dashscope_api_key` 属于旧的进程内 RAG 配置，在外部服务方案中不应由主项目使用。主项目只需要自己的 `LLM_API_KEY` 和调用 RAG 服务所需的 `RAG_API_KEY`。

## 9. Docker Compose 修改

当前 Compose 的 `api` 容器没有注入 `RAG_*` 配置，而且容器内的 `127.0.0.1` 指向 API 容器本身，不能访问宿主机或另一个 RAG 容器。

推荐把 RAG 加入同一个 Compose 网络：

```yaml
services:
  rag:
    build:
      context: ../RAG
    command: ["uvicorn", "service_app:app", "--host", "0.0.0.0", "--port", "8010"]
    environment:
      DASHSCOPE_API_KEY: ${DASHSCOPE_API_KEY:?set DASHSCOPE_API_KEY}
      RAG_API_KEY: ${RAG_API_KEY:-}
      RAG_KB_ID: medical_guidelines
    ports:
      - "8010:8010"
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8010/readyz')"]
      interval: 10s
      timeout: 3s
      retries: 20

  api:
    environment:
      RAG_BASE_URL: http://rag:8010
      RAG_API_KEY: ${RAG_API_KEY:-}
      RAG_TIMEOUT: "45"
      RAG_TOP_K: "5"
      RAG_FAIL_OPEN: "true"
    depends_on:
      rag:
        condition: service_healthy
```

如果 RAG 继续运行在宿主机，Windows Docker Desktop 下可使用：

```dotenv
RAG_BASE_URL=http://host.docker.internal:8010
```

生产环境不要依赖宿主机特殊域名，使用容器服务名或内部 DNS。

## 10. 测试修改

### 10.1 单元测试

新增或补充：

1. `need_advice=true` 经 normalize 后一定调用 RAG；
2. `need_rag=false` 时正确跳过；
3. `continue` 时 evidence 进入 `rag_context`；
4. `evidence_insufficient` 时不把 evidence 交给 LLM；
5. `need_human_confirmation` 时进入安全提示；
6. RAG 连接失败且 fail-open=true 时安全降级；
7. fail-open=false 时抛出明确异常；
8. 包装响应与裸响应均可解析；
9. 非法响应被映射为 `ExternalRAGError`；
10. Authorization Header 正确发送。

### 10.2 契约测试

增加一个不依赖真实 DashScope 的测试 RAG 服务或 Mock Runtime，通过真实 HTTP 验证：

- 请求字段；
- 响应字段；
- `top_k`；
- HTTP 状态码；
- 超时和错误响应。

### 10.3 真实联调测试

现有 `tests/test_rag_integration.py` 只断言返回字典包含若干 key，覆盖不足。应增加：

- 确认没有被错误跳过；
- evidence 至少包含 `evidence_id/text/source/score`；
- `rag_evidence.suggested_action` 合法；
- `rag_context` 中包含 evidence id 和来源；
- `len(rag_docs) <= RAG_TOP_K`。

真实测试继续通过 `RUN_REAL_INTEGRATION=1` 显式启用，普通单元测试不能依赖外部网络。

## 11. 文档和代码清理

- 更新 `app/nodes/rag_node.py` 中仍然写着“调用 `rag_graph.invoke()`”的旧注释；实际已经改成 HTTP 客户端；
- 从主项目文档中删除“RAG FastAPI 路由尚未实现”的说明，前提是 RAG 侧已经完成；
- `.env.example` 保留 RAG 配置但不包含真实密钥；
- README 增加本地三服务启动顺序；
- 明确 `/dependencies` 只表示连通性，不等同于一次真实检索成功。

## 12. 推荐实施顺序

1. RAG 项目完成 `/healthz`、`/readyz` 和 `/v1/retrieve`；
2. 修复本项目 `rag_node` 对 `intent_flags` 的读取；
3. 接入 `suggested_action` 和质量状态；
4. 完善无证据降级策略；
5. 增加契约和工作流测试；
6. 修改 Compose 服务发现和环境变量；
7. 执行真实端到端联调。

## 13. 验收标准

- `/dependencies` 显示 `external_rag=up`；
- 建议和计划相关请求实际调用 RAG；
- 非 RAG 请求不会产生多余调用；
- `RAG_TOP_K=5` 时最终 evidence 不超过 5 条；
- 证据不足不会被包装成有指南支持的结论；
- 紧急风险仍优先走本地规则；
- RAG 停止、超时、返回 5xx 和返回非法 JSON 均有预期行为；
- 本地运行和 Docker 运行均可正确解析 RAG 地址；
- 单元测试、契约测试和显式真实联调测试全部通过。

