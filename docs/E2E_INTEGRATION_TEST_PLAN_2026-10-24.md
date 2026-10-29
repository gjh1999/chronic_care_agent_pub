# 三服务端到端联合测试方案

日期:2026-10-24
项目:慢性病管理 Agent(主项目)联合 Medical_Lora 意图服务 + 外部 RAG 服务

## 1. 背景与目标

前两轮已分别完成:

- RAG 服务与主项目 `rag_node` 的真实联调(36 passed + 1 真实联调);
- Medical_Lora 意图服务与主项目 `parser_node`、基础路由的真实联调。

两轮均未覆盖**完整三服务业务链路**:用户输入 → 意图服务 → 主项目 LangGraph 全流程(含真实外部 LLM)→ RAG 证据 → 最终回复,以及计划两阶段确认、数据持久化。

本轮目标:通过主项目真实 HTTP API,端到端验证三服务联合工作,覆盖建议、记录、计划、提醒、多意图组合与紧急风险拦截。

## 2. 测试架构

```text
pytest (httpx, RUN_REAL_INTEGRATION=1)
   │ 真实 HTTP
   ▼
主项目 uvicorn :8000 (APP_ENV=test, 隔离 SQLite, ALLOW_DEV_LOGIN=true)
   ├── POST 127.0.0.1:8020/v1/intent/parse  → Medical_Lora(Qwen2.5-7B + routing LoRA, GPU)
   ├── POST 127.0.0.1:8010/v1/retrieve      → 外部 RAG(medical_guidelines 知识库)
   └── DashScope OpenAI 兼容 API            → 主项目通用 LLM(qwen3.6-plus,真实调用)
```

原则:

- 全部使用真实 HTTP 与真实模型,不 mock 任何外部服务;
- 显式开关 `RUN_REAL_INTEGRATION=1`,普通 `pytest -q` 自动跳过本套件;
- 主项目使用独立测试数据库,不污染开发库;
- 使用虚构用户与虚构健康数据;
- 意图模型输出具有概率性,断言区分硬性要求与观测记录。

## 3. 环境准备

```powershell
# 1. 意图服务(Medical_Lora 项目目录,.venv,GPU)
.\.venv\Scripts\python.exe -m uvicorn service_app:app --host 127.0.0.1 --port 8020 --workers 1

# 2. RAG 服务(RAG 项目目录,.venv)
.\.venv\Scripts\python.exe -m uvicorn service_app:app --host 127.0.0.1 --port 8010

# 3. 主项目(chronic_care_agent_2 目录,.venv,隔离测试库)
$env:APP_ENV='test'
$env:DATABASE_URL='sqlite:///data/sqlite/pytest_e2e_chronic_care.db'
$env:ALLOW_DEV_LOGIN='true'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 4. 运行测试
$env:RUN_REAL_INTEGRATION='1'
.\.venv\Scripts\python.exe -B -m pytest tests\test_e2e_three_services.py -q -s -p no:cacheprovider
```

## 4. 测试场景

| 编号 | 场景 | 输入 | 关键断言 |
|------|------|------|----------|
| E2E-01 | 系统与依赖健康 | GET /healthz /readyz /dependencies | 三个端点 200;`intent_service=up` 且 `external_rag=up` |
| E2E-02 | 开发登录 | POST /auth/wechat-login `{"code":"dev-e2e-alice"}` | 返回 access_token |
| E2E-03 | 建议流(RAG+外部 LLM) | `我今天早上血压145/92,这正常吗?` | `need_advice=true`;`rag_docs` 非空;`rag_suggested_action∈{continue,retry_done}`;`advice` 非空;`risk_result` 存在;`final_response` 含建议 |
| E2E-04 | 记录流 | `我今天血糖6.8,帮我记录一下` | `record_result` 非空;GET /health/observations 能查到该记录 |
| E2E-05 | 计划两阶段确认 | `帮我制定一个控糖计划` | 首轮 `status=waiting_confirmation` 且有 `interrupt_id`;确认后 `status=completed`;GET /plans 查到 confirmed 计划 |
| E2E-06 | 直接提醒流 | `明早8点提醒我测血糖` | `reminder_created=true`;GET /reminders 查到该提醒 |
| E2E-07 | 多意图全流程 | `我今天早上血压145/92,帮我记录一下,这正常吗?顺便帮我制定一个降压计划,再提醒我晚上9点测血压` | 记录+建议+计划草稿+提醒全链路;确认后计划归档、计划提醒创建;各环节状态齐全 |
| E2E-08 | 紧急风险本地规则拦截 | `我今天血压185/125,这正常吗?` | `risk_result.level=urgent`;`advice` 为规则拦截文本(不调用外部 LLM);`final_response` 含急救提示 |
| E2E-09 | 会话状态与持久化 | 复用 E2E-05 会话 | 会话 status 随确认流程变化;消息已持久化 |

## 5. 观测与记录

除断言外,每个场景记录实际输出用于报告:

- 意图服务的 `intent_flags` 与 `confidence`(验证 7B 模型真实路由);
- RAG 的 `suggested_action`、evidence 数量与来源;
- 外部 LLM 的 `advice` / 计划草稿内容(摘录);
- 各环节耗时。

## 6. 验收标准

- E2E-01~E2E-09 全部通过;
- 建议场景真实命中 RAG 证据并进入 LLM 生成;
- 紧急风险不调用外部 LLM,直接规则拦截;
- 记录、计划、提醒均真实持久化到隔离数据库;
- 计划必须经确认后才归档生效。

## 7. 风险与预案

| 风险 | 预案 |
|------|------|
| 7B 模型对复杂多意图输入路由不准 | 输入采用其测试集已验证句式;若路由偏差,如实记录为发现项 |
| LLM 开启 thinking 导致单次调用慢 | 提高 pytest 超时;不设整体时间红线 |
| GPU 显存不足(7B 4-bit 与系统共享 16GB) | 关闭无关 GPU 进程,意图服务 workers=1 |
| RAG 首次调用预热慢 | 健康检查后先跑一次建议场景预热 |
