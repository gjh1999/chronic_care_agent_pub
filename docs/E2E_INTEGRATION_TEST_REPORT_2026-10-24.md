# 三服务端到端联合测试报告

日期:2026-10-24
项目:慢性病管理 Agent 联合 Medical_Lora 意图服务 + 外部 RAG 服务

## 1. 结论

三服务链路已打通:**用户输入 → 意图服务(7B LoRA)→ 主项目 LangGraph 全流程 → 外部 RAG → 真实 LLM → 最终回复**,记录、建议、计划两阶段确认、直接提醒、紧急风险拦截全部按预期工作。

端到端套件 **8 passed、1 failed**;失败用例暴露一个真实缺陷:**API 确认计划后不会创建计划提醒**(F2)。

同时发现两个此前单服务联调无法暴露的跨服务问题:**RAG 知识库错配**(F1,主项目连的是眼科知识库)与**提醒时间未解析为绝对时间**(F3)。

## 2. 测试方案摘要

方案文档:`docs/E2E_INTEGRATION_TEST_PLAN_2026-10-24.md`

- 全部真实 HTTP + 真实模型,不 mock 任何外部服务;
- 显式开关 `RUN_REAL_INTEGRATION=1`,普通 `pytest -q` 自动跳过(已验证:普通模式 36 passed、10 skipped);
- 主项目以 `APP_ENV=test` + 隔离 SQLite 启动,不污染开发库;
- 每个用例使用独立虚构用户与独立会话,避免跨用例数据残留掩盖缺陷;
- 意图模型输出具有概率性,用例均采用其测试集已验证的句式。

## 3. 测试环境

| 项目 | 内容 |
|------|------|
| 操作系统 | Windows 11 10.0.26200 |
| GPU | NVIDIA GeForce RTX 5080(16GB) |
| 意图服务 | Qwen2.5-7B-Instruct + routing LoRA,`127.0.0.1:8020`,`--workers 1` |
| RAG 服务 | `127.0.0.1:8010`,知识库 `medical_guidelines` |
| 主项目 | uvicorn `127.0.0.1:8000`,`APP_ENV=test`,`ALLOW_DEV_LOGIN=true`,隔离 SQLite |
| 外部 LLM | DashScope `qwen3.6-plus`,`enable_thinking=true` |
| 测试代码 | `tests/test_e2e_three_services.py`(新增) |

## 4. 场景结果

| 编号 | 场景 | 输入 | 结果 | 耗时 |
|------|------|------|------|------|
| E2E-01 | 系统与依赖健康 | GET /healthz /readyz /dependencies | 通过;`intent_service=up`、`external_rag=up` | <1s |
| E2E-02 | 开发登录与用户信息 | POST /auth/wechat-login + GET /auth/userinfo | 通过;JWT 签发、鉴权生效 | <1s |
| E2E-03 | 建议流(RAG+外部 LLM) | `我今天早上血压145/92,这正常吗?` | 通过;7B 路由 `need_record+need_advice`;本地规则 `level=medium`;RAG 返回 5 条证据 `suggested_action=continue`、`quality_passed=true`;LLM 生成建议 | 70.0s |
| E2E-04 | 记录流 | `我今天血糖6.8,帮我记录一下` | 通过;`record_result.success=true`;GET /health/observations 查到血糖记录 | 18.5s |
| E2E-05 | 计划两阶段确认 | `帮我制定一个控制血糖的饮食和运动计划` | 通过;首轮 `waiting_confirmation`+`interrupt_id`;确认后 `status=completed`、计划 `confirmed`(revision 1→2);会话状态 `waiting_confirmation→active`;GET /plans?status=confirmed 可查 | 189.9s |
| E2E-06 | 直接提醒流 | `明早8点提醒我测血糖` | 通过;`reminder_created=true`;GET /reminders 查到 `scheduled` 提醒 | 16.5s |
| E2E-07 | 多意图全流程 | `我今天早上血压145/92,帮我记录一下,这正常吗?顺便帮我制定一个降压计划,再提醒我晚上9点测血压` | **失败**;7B 正确识别四意图;记录、建议、RAG 证据、计划草稿、确认归档全部正常;**但确认后 `GET /reminders` 为空,计划提醒未创建**(缺陷 F2) | 114.6s |
| E2E-08 | 紧急风险本地规则拦截 | `我今天血压185/125,这正常吗?` | 通过;本地规则 `level=urgent`,返回规则拦截文本(含"高危范围""急救"),未调用外部 LLM;`final_response` 含 🚨 | 24.3s |
| E2E-09 | 会话状态与消息持久化 | 记录流 + GET /conversations/{id} | 通过;会话状态、`last_message_at` 正确更新 | 16.0s |

说明:E2E-07 的失败断言在测试代码中已注明对应缺陷,修复后该用例应转绿。

## 5. 关键链路验证细节

### 5.1 意图服务(7B LoRA)

- 单意图路由准确:记录、建议、提醒三类单意图输入均正确路由;
- 四意图复合句(`记录+建议+计划+提醒`)一次解析全部正确,`confidence` 与路由一致;
- 行为观察(非缺陷):对 `血压145/92,这正常吗?` 这类纯提问,模型额外输出 `need_record=true`,即"提及测量值即隐含记录"。主项目按此落库了一条血压观测。若产品不希望隐式记录,需在意图服务侧调整训练数据或加后处理。

### 5.2 RAG 服务

- 查询改写与扩展工作正常:血压问句被改写为"成人清晨血压145/92 mmHg是否达到高血压诊断标准及是否需启动降压治疗",扩展出 4 条高血压相关子查询;
- 质量门控工作正常:返回 `suggested_action=continue`、`final_quality.passed=true`(top_score 0.41、avg 0.39,高于 0.35/0.25 阈值);
- **但检索内容错域**:top-5 证据全部来自眼科文档(眼科日间手术、糖尿病视网膜病变、黄斑变性等),高血压/糖尿病指南内容从未被召回(缺陷 F1)。

### 5.3 外部 LLM(真实调用)

- 建议生成:基于规则评估 + RAG 证据生成,格式符合提示词要求(结论→依据→可执行建议);
- 安全性表现良好:在 E2E-05 中,LLM 主动指出"提供的 RAG 文献主要聚焦围手术期及并发症防治原则",未把眼科证据包装成慢病指南依据;E2E-08 紧急场景完全不经过 LLM;
- 计划草稿生成:结构化为 tasks(带时间),经冲突检测后进入确认流程。

### 5.4 数据持久化(隔离库直接核查)

| 表 | 行数 | 说明 |
|----|------|------|
| health_observation | 多条 | 血压 145/92、血糖 6.8/7.2 均落库 |
| care_plan | 3 | 全部 `confirmed`、`revision=2` |
| conversation_message | 18 | 用户/助手消息成对持久化 |
| reminder | 1 | 仅 E2E-06 的直接提醒 |
| notification_outbox | 1 | `available_at=now`(缺陷 F3 佐证) |

## 6. 发现的缺陷

### F1【严重】RAG 知识库错配:主项目连接的是眼科知识库

- 现象:血压、血糖类查询的 top-5 证据全部来自眼科文档;直接检索"中国高血压防治指南 降压治疗"仍返回黄斑变性、视网膜疾病文档。
- 根因:`RAG_KB_ID=medical_guidelines`,该 KB 的自我描述即"中国眼科临床指南、专家共识等文献知识库",索引 49 篇眼科文档。而《中国高血压防治指南(2024年修订版)》《中国糖尿病防治指南(2024版)》两份慢病指南被索引在另一个 KB `my_kb`(共 2 篇)中。
- 影响:建议/计划生成的证据基础错域。质量门控(基于分数阈值)无法识别此问题——分数 0.37~0.42 通过了 0.35 的门槛。当前仅靠 LLM 自觉提示证据局限,不可依赖。
- 建议:将慢病指南并入 `medical_guidelines` 并重建索引,或主项目按业务场景选择 KB;RAG 侧可增加"领域匹配"检查(如检索结果来源类别与查询医学领域的一致性信号)。

### F2【高】API 确认计划后不创建计划提醒

- 现象:E2E-07 计划确认成功(`status=confirmed`),但 reminders 表为空;子图中的 `plan_reminder` 链从未执行。
- 根因:API 的确认路径 `conversation_service.resume_interrupt(action=confirm)` 只调用 `change_plan_status` 翻转计划状态,**不会重新执行工作流**;而首轮调用(user_confirmed=None)时子图路由 `user_confirm → reminder_create`,此时 `confirmed_plan/plan_reminders` 均为空,创建 0 条提醒。`plan_reminder_node` 只有在 `run_workflow(user_confirmed=True)` 的直接调用路径(工作流单测)中才能执行到。
- 影响:违反架构设计"Reminder 只能基于 confirmed_plan 创建"的意图——计划提醒功能在真实 API 业务中不可用。
- 建议:确认后重新执行工作流(带 `user_confirmed=True` 与已确认计划上下文),或将计划提醒生成下沉到 `plan_service.change_plan_status(confirm)` 内部。

### F3【高】提醒时间未解析为绝对时间,outbox 立即可投递

- 现象:`明早8点提醒我测血糖` 落库为 `schedule_rule.time="明早8点"`、`next_run_at=None`;outbox `available_at` 回退为当前时间——worker 一旦运行会立即投递,而不是明早 8 点。
- 根因:`direct_reminder_node → reminder_create_node` 链路原样透传意图服务的原始时间文本,`app/core/tools/time_parser.py` 未接入;`create_reminder` 以 `next_run_at or now` 兜底。
- 建议:在提醒创建链接入时间解析,解析 `明早8点/今晚9点/21:00` 等表达为具体 `next_run_at`;解析失败时置为待人工确认或明确报错,禁止静默按"立即"投递。

### F4【观察】意图模型对纯提问隐式添加记录意图

见 5.1。是否修复取决于产品定义,建议在意图服务侧明确训练样本策略。

## 7. 尚未覆盖

- reminder worker 真实投递(本轮未运行 worker;F3 修复后需重测);
- 微信通道投递(需要模板与授权配置);
- 计划确认的 `reject`、`modify` 分支;
- RAG 服务在线宕机/超时时的 API 级降级行为(已有单测覆盖 fail-open 策略,未做在线注入);
- 多用户并发、GPU 压力与长文本边界;
- Docker Compose 容器网络(本机未安装 docker)。

## 8. 复测方式

```powershell
# 1. Medical_Lora 项目目录
.\.venv\Scripts\python.exe -m uvicorn service_app:app --host 127.0.0.1 --port 8020 --workers 1

# 2. RAG 项目目录
.\.venv\Scripts\python.exe -m uvicorn service_app:app --host 127.0.0.1 --port 8010

# 3. 主项目目录
$env:APP_ENV='test'
$env:DATABASE_URL='sqlite:///data/sqlite/pytest_e2e_chronic_care.db'
$env:ALLOW_DEV_LOGIN='true'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 4. 运行 E2E 套件
$env:RUN_REAL_INTEGRATION='1'
.\.venv\Scripts\python.exe -B -m pytest tests\test_e2e_three_services.py -q -s -p no:cacheprovider
```

## 9. 最终判定

**三服务联合链路已打通,建议流、记录流、计划两阶段确认、直接提醒、紧急规则拦截均可端到端工作。**

但存在三个需要修复的跨服务缺陷(F1 RAG 知识库错配、F2 计划提醒不创建、F3 提醒时间不解析),其中 F1 直接影响医学建议的证据质量,建议优先修复。E2E-07 的失败断言即为 F2 的回归测试,修复后整套件应转为 9 passed。

## 10. 修复记录:F1(RAG 知识库错配,当日完成)

**根因**:RAG 服务默认 KB `medical_guidelines` 是眼科知识库(49 篇眼科共识);慢病指南此前被建在 `my_kb`(2 篇)且从未被服务使用;主项目请求契约中没有 kb_id 字段,无法选库。

**修复(在 RAG 项目执行)**:

1. 新建输入目录 `knowledge_base/data/chronic_disease/`,放入《中国高血压防治指南(2024年修订版)》《中国糖尿病防治指南(2024版)》;
2. 用 `knowledge_base` 构建管线重建 KB `chronic_disease`(名称"慢病防治指南知识库"):2 篇文档、1399 个切片、0 错误;
3. RAG `.env` 增加 `RAG_KB_ID=chronic_disease`(此前未配置,走代码默认值 `medical_guidelines`);
4. 删除旧 KB `medical_guidelines` 与 `my_kb`(sqlite 行 + faiss/bm25/snapshot 索引文件);眼科源文档保留在磁盘,未删除。

**验证**:

- `/readyz` 返回 `kb_id=chronic_disease`;
- 血压探测查询 top-5 证据来源:4 篇高血压防治指南 + 1 篇糖尿病指南(血压管理章节),分数 0.57~0.66(修复前眼科文档仅 0.37~0.42);
- 血糖探测查询 top-5 全部来自糖尿病防治指南,分数 0.76~0.86;
- 三服务 E2E 复测:8 passed、1 failed(E2E-07 仍为 F2 计划提醒缺陷,与知识库无关);E2E-03 建议流证据来源确认全部为慢病指南,`suggested_action=continue`、质量通过,LLM 基于正确证据生成建议。

## 11. 修复记录:F2(计划提醒不创建)与 F3(提醒时间不解析,当日完成)

### F2【高】API 确认计划后不创建计划提醒

**根因**:API 确认路径 `resume_interrupt(confirm)` 只翻转计划状态不重跑工作流;子图中 `user_confirm → reminder_create` 在未确认首轮拿到空的 `confirmed_plan`,创建 0 条提醒;`plan_reminder_node` 只在工作流单测路径可执行。

**修复(主项目)**:

1. `app/service/plan_service.py` 新增 `confirm_plan(db, user_id, plan_id, revision)`:确认计划后按计划项逐条创建提醒(`plan_item_id` 关联 + `dedupe_key=plan:{plan_id}:{item_id}` 幂等),无时间/解析失败的项不创建、放入 `skipped` 返回;
2. `conversation_service.resume_interrupt` 的 confirm 分支改用 `confirm_plan`,结果携带 `reminders`/`skipped`;
3. `plan_archive_node`(工作流确认路径)改用 `confirm_plan` 并回写 `reminder_created`/`reminder_result`;
4. 子图路由重排:计划提醒改由确认服务创建,子图删除 `plan_reminder_node` 链;`user_confirm` 未确认时若 `need_reminder` 则进入直接提醒链(修复多意图消息中直接提醒被丢弃的问题),否则结束;`plan_archive → END`;`reminder_create_node` 简化为仅直接提醒。

### F3【高】提醒时间未解析为绝对时间

**根因**:`direct_reminder_node → reminder_create_node` 原样透传意图服务的原始时间文本,`time_parser` 未接入;`create_reminder` 以 `next_run_at or now` 兜底,导致 outbox 立即可投递。

**修复(主项目)**:

1. `app/core/tools/time_parser.py`:`parse_time_text` 支持 明早/明晚/今早;新增 `resolve_next_run_at(schedule_rule)`,将自然语言/`HH:MM`/显式日期解析为 aware UTC datetime(中国固定 +8),已过去的时刻顺延到次日;解析失败返回 None;
2. `app/service/reminder_service.create_reminder` 强制解析:失败抛 `ServiceException`(422"提醒时间无法解析"),禁止静默立即投递;`next_run_at` 落库且 outbox `available_at = next_run_at`。

### 复测结果(同日)

- 普通测试套件 36 passed、1 skipped;三服务 E2E 全套 **9 passed(370.8s)**,E2E-07 转绿;
- 隔离库核查:E2E-07 确认后 `reminder` 表含计划提醒(`plan_item_id` 非空)+ 首轮直接提醒;`notification_outbox` 中 `available_at <= now` 的行数为 **0**,`明早8点` → 次日 00:00 UTC、已过时刻顺延次日,无立即投递;
- E2E-06/E2E-07 增加 `next_run_at` 回归断言。

**遗留**:reminder worker 真实投递仍未在线验证(需要配置微信通道或替换 in_app 投递实现);计划确认的 reject/modify 分支未做 E2E 覆盖;F4(纯提问隐式记录)待产品决策。
