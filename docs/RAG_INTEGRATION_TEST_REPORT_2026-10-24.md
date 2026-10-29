# RAG 对接测试方案与结果

日期：2026-10-24  
项目：慢性病管理 Agent 对接外部 RAG 服务

## 结论

本次测试通过。自动化测试结果为 **36 passed、1 skipped**；显式启用的真实 RAG 联调为 **1 passed**。

真实联调覆盖主项目 `rag_node` 到本机 RAG HTTP 服务的检索调用、真实响应解析和 evidence 质量策略。它不是包含意图服务、主 API、LLM 在内的完整三服务端到端业务测试。

## 测试方案

| 测试层 | 方式 | 验证重点 |
|---|---|---|
| RAG 客户端单元测试 | `httpx.MockTransport` | 裸响应和 `{code,data,message}` 包装、Authorization、HTTP 错误分类、非法 JSON、Schema 错误、连接/读取超时和 5xx 的一次重试，以及 4xx 不重试 |
| 工作流策略测试 | 替换 RAG/LLM 客户端 | 规范化后的 `intent_flags.need_rag` 会调用 RAG；不需要 RAG 时跳过；证据不足或需医生确认时不调用 LLM；fail-open 开关行为正确 |
| HTTP 契约测试 | 启动本机临时 HTTP Mock 服务 | 经真实 HTTP 传递请求和响应，检查字段、`top_k`、HTTP 状态及响应映射，不依赖 DashScope |
| 真实 RAG 集成测试 | 连接运行中的 RAG 服务 | 检查 RAG 调用未被跳过、动作值合法、evidence 字段齐全、上下文包含 evidence ID 和来源、结果数不超过 `RAG_TOP_K` |

## 执行过程

1. 先运行既有和新增的 RAG 客户端、策略、安全与工作流相关测试，结果 **23 passed**。
2. 运行整个项目测试集。真实服务测试默认受 `RUN_REAL_INTEGRATION=1` 保护，因此此轮自动跳过该测试；结果 **36 passed、1 skipped**。
3. 检查本机 `http://127.0.0.1:8010/readyz`，起初服务未运行。随后使用 RAG 项目的虚拟环境临时启动 `uvicorn service_app:app --host 127.0.0.1 --port 8010`。
4. `/readyz` 返回 `status=ready`，知识库为 `medical_guidelines`。
5. 设置 `RUN_REAL_INTEGRATION=1`，单独运行 `tests/test_rag_integration.py`。真实 RAG HTTP 调用和断言全部通过：**1 passed**，耗时约 3.9 秒。
6. 测试结束后关闭临时 RAG 服务，并确认 8010 的健康端点已不可访问；测试日志已清理。

真实集成测试执行命令：

```powershell
$env:RUN_REAL_INTEGRATION='1'
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe -B -m pytest tests\test_rag_integration.py -q -p no:cacheprovider -s
```

全量测试执行命令：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider
```

## 结果明细

- 建议请求规范化后设置 `intent_flags.need_rag=True`，测试确认 RAG 收到请求，并在 metadata 中看到规范化路由标志。
- `need_rag=False` 时，测试确认不会产生 RAG 请求。
- RAG `continue` 且质量通过时，evidence 可进入 `rag_context`；上下文中含 evidence ID 和来源。
- `evidence_insufficient`、`ask_user_clarification`、`need_human_confirmation`、服务不可用或质量明确失败时，主流程使用安全降级结果，不把不合格 evidence 交给 LLM。
- HTTP 客户端携带配置的 Bearer Authorization；错误返回不包含 API Key 或完整内部堆栈。
- 网络瞬时错误、读取超时和指定 5xx 最多重试一次；4xx、非法 JSON 和 Schema 不匹配不重试。
- 请求和响应通过本机 HTTP 契约测试；请求 `top_k=3` 时收到的 evidence 数量为 3。真实集成使用配置的 `RAG_TOP_K` 并验证返回上限。
- Compose 文件通过 Python YAML 解析校验，`git diff --check` 通过。

## 尚未覆盖

- 当前机器没有安装 `docker` 命令，因此未运行 `docker compose config`，也没有启动 Compose 容器验证容器网络。
- 没有启动 Medical_Lora 意图服务，也没有通过主项目 API 执行从意图解析到最终回复的完整三服务业务流程。
- 本次真实 RAG 集成测试直接构造了包含 `intent_flags` 的状态，并调用主项目 `rag_node`；未调用通用 LLM。
- `/dependencies` 的外部服务状态检查没有在本轮实际执行；RAG 的 `/readyz` 已单独验证成功。

## 复测方式

先启动 RAG 服务并确认 `/readyz` 返回成功，再从项目根目录运行：

```powershell
$env:RUN_REAL_INTEGRATION='1'
pytest tests\test_rag_integration.py -q -s
```

若只运行普通测试，真实服务集成测试会按设计跳过，不会访问外部网络。
