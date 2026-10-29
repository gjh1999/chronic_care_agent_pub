# 模拟面试手册 —— Chronic Care Agent 项目

## 一、项目概述与架构理解

### Q1：用 3 分钟介绍一下你这个项目

**面试官在考察**：能不能讲清楚 WHY → HOW → WHAT，而不是罗列技术栈

**高分回答结构**：
```
1. 一句话定性：这是一个基于 LangGraph 的慢性病管理多意图 Agent 系统
2. 解决什么问题：用户可以用自然语言同时完成「记录数据 + 获取建议 + 制定计划 + 创建提醒」的组合需求
3. 核心架构决策：
   - 用 LangGraph 做流程编排而非 LangChain AgentExecutor（为了显式控制）
   - LLM 负责认知（理解/生成），Rule Engine 负责安全（风险判断/冲突检测），RAG 负责知识准确性
   - Human-in-the-loop：计划必须用户确认才能生效
4. 一个具体场景例子：用户说 "我血糖 10.5，给点建议，并提醒我晚上再测一次"
   → 系统并行执行 记录+建议+提醒 三个意图
5. 量化结果（如果有的话）
```

**减分说法**：
- "就是一个 LangGraph + FastAPI 的系统"（没有 WHY）
- 从头到尾列举技术栈不做取舍说明

---

### Q2：为什么选 LangGraph 而不是直接用 LangChain 的 AgentExecutor？或者 AutoGen / CrewAI？

**面试官在考察**：技术选型有没有做过 trade-off 分析

**高分回答**：

核心差异在于 **可控性 vs 便捷性**：

| | LangGraph | AgentExecutor | AutoGen/CrewAI |
|---|---|---|---|
| 流程控制 | 显式 DAG，每个节点可见 | 黑盒 Think-Act-Observe 循环 | Agent 自主协商 |
| 条件路由 | 原生支持条件边 | 不支持 | 不支持 |
| Human-in-the-Loop | `interrupt()` API 原生支持 | 需要自己 hack | 支持较弱 |
| 多意图并行 | 子图天然支持 | 需要自己编排 | 需额外设计 |

**关键金句**：这个系统的核心需求是「多意图组合执行 + 条件路由跳过 + 计划必须用户确认」，这三条需求直接排除了 AgentExecutor 和 AutoGen——前者不可控，后者缺少显式流程编排。LangGraph 的 StateGraph + 条件边 + interrupt() 是精确匹配。

**追问**：那什么时候用 AutoGen？→ 当任务是「多个 LLM 角色自主讨论/辩论」而非「按固定流程逐步编排」时。

---

### Q3：讲一下这个系统的分层架构设计

**面试官在考察**：有没有做职责分离，还是把所有逻辑混在一起

**高分回答**：按职责分了 5 层，每层只做一件事：

```
API/FastAPI 层 → 接收请求、返回响应（薄层）
    ↓
LangGraph 工作流层 → 流程编排、状态管理、条件路由（核心）
    ↓
Memory 层 → 用户长期画像，为上下文注入提供依据
    ↓
Core 能力层 → LLM 推理 + Rule 安全检查
    ↓
外部服务层 → RAG（知识）/ DB（数据）/ Scheduler（执行）
```

**关键原则**：
- Graph 只负责流程控制，不做业务逻辑
- Node 只负责一个业务步骤，不关心下一步是什么
- LLM 只做认知（理解/生成），不做安全判断
- Rule 只做安全控制（风险/冲突），不做推理

**追问**：为什么把 Rule Engine 和 LLM 分开？→ LLM 的输出不可靠、可能产生幻觉，安全判断（比如血糖 10.5 是什么风险等级）必须由确定性规则负责，不能交给概率模型。

---

## 二、LangGraph 工作流深度

### Q4：State 设计中最重要的原则是什么？你项目里的 ClinicalState 是怎么设计的？

**面试官在考察**：是否理解 State 的不可变性约束，以及 State 设计的粒度

**高分回答**：

核心原则：**State 不可变性**。每个 Node 不能直接修改 State，而是返回一个 State 更新字典，LangGraph 自动 merge。这是保证流程可追溯、可回放、可中断恢复的基础。

ClinicalState 设计原则：
- 按数据生命周期分字段，不是按节点分
- 每个字段有明确的「谁写入、谁读取」的契约
- 不做过度嵌套（嵌套越深，条件路由越难写）

关键字段：
- `user_input` / `intent`：Parser Node 写入，Router 读取（控制路由）
- `memory_context` / `task_preferences`：工作流入口写入，Advice/Plan Node 读取（上下文注入）
- `extracted_data`：Parser 写入，Record Node 读取
- `risk_level`：Risk Node 写入，Advice Node 读取
- `plan_draft` / `plan_conflicts` / `user_confirmed`：Plan 子图内部流转
- `confirmed_plan`：子图输出，提醒节点依赖

**追问**：State 设计太大会有什么问题？→ 序列化开销大、checkpoint 慢、条件路由逻辑变复杂。解决：拆成子图，子图有自己的 State 子集。

---

### Q5：说一下你项目里的条件路由是怎么做的？

**面试官在考察**：是否理解条件边的概念，有没有实际处理过复杂路由逻辑

**高分回答**：

路由分两层：

**第一层：Intent Normalize（意图补全）**
```
need_plan → need_advice（计划需要基于建议生成）
need_advice → need_history + need_risk + need_rag（建议依赖于数据+风险+知识）
need_reminder → 判断是 direct_reminder 还是 plan_reminder
```
这是补全依赖关系，避免流程不完整。

**第二层：Router 条件路由**
```python
# 不是 if-else 瀑布，而是声明式条件边
graph.add_conditional_edges(
    "normalize",
    route_by_intent,
    {
        "record": "record_node",
        "advice": "history_node",
        "plan": "plan_draft_node",
        "reminder": "direct_reminder_node",
    }
)
```

**关键设计**：节点按需跳过而非固定流水线。用户只记录数据 → 只走 Record 分支；用户要建议 → 走 History → Risk → RAG → Advice 链；用户全都要 → 多条路径并行/串行执行后在 Response Node 汇聚。

**追问**：条件路由太复杂怎么办？→ 抽成子图（plan_reminder_sub），主图只管「进不进子图」，子图内部自己管路由。

---

### Q6：Plan + Reminder 为什么要抽成独立子图？

**面试官在考察**：对子图机制的深刻理解，不只是会调用 API

**高分回答**：

三个理由：

1. **State 隔离**：Plan/Reminder 子图内部有大量中间态（plan_draft → conflicts → confirmed），这些字段主图不需要关心。子图有独立的 State 空间，不污染主图 State。

2. **独立编译与复用**：子图可以独立编译（`compile()`），独立测试，甚至可以独立部署。后续如果需要调整计划生成逻辑，只改子图内部，主图不受影响。

3. **Human-in-the-Loop 中断点清晰**：子图内部有 `interrupt()` 等待用户确认，中断边界就是子图边界。如果放在主图里，中断恢复后状态的完整性不好保证。

**金句**：主图管"做什么"，子图管"怎么做"。

---

### Q7：Human-in-the-Loop（人机协同）在你的系统里具体怎么实现的？

**面试官在考察**：有没有真正理解 interrupt/checkpoint 机制

**高分回答**：

关键设计：**计划必须用户确认后才能生效，Reminder 只能基于 confirmed_plan 创建。**

流程：
```
Plan Draft → Conflict Check → [interrupt() 中断] → 等待用户选择
    ↓
用户返回：confirm / reject / modify
    ↓
confirm → Plan Archive → Reminder Create
reject → 终止流程
modify → 回到 Plan Draft
```

技术实现：
```python
# 在 user_confirm_node 之前调用 interrupt()
graph.add_node("user_confirm", user_confirm_node)
# LangGraph 在遇到 interrupt 时自动保存 checkpoint
# 用户响应后通过 graph.invoke(resume_input, config) 恢复
```

为什么这很重要：**医疗场景下，不能让 AI 的建议直接生效**。用户必须审阅计划内容，确认后才能创建提醒。这是安全底线，不是 UX 优化。

---

## 三、AI/LLM 技术深度

### Q8：Parser Node 怎么做到多意图识别的？Prompt 怎么设计的？

**面试官在考察**：Prompt Engineering 能力，结构化输出的控制手段

**高分回答**：

核心思路：**让 LLM 做结构化 JSON 输出，而不是自由文本分类。**

输出 Schema（SchemaReadme.md 中的设计）：
```json
{
  "routing": {
    "need_record": true,
    "need_advice": true,
    "need_plan": false,
    "need_reminder": true
  },
  "confidence": { "need_record": 0.96, "need_advice": 0.90, "need_plan": 0.08, "need_reminder": 0.94 },
  "slots": {
    "record": { "blood_glucose": { "value": 10.5, "unit": "mmol/L" } },
    "advice": { "topic": "blood_glucose" },
    "reminder": { "action": "create", "task": "测血糖", "time": "晚上" }
  }
}
```

设计要点：
- `routing`：布尔值，直接驱动条件路由
- `confidence`：用于后续可能的降级策略（低置信度走人工确认）
- `slots`：按意图分类的槽位填充，每个意图独立解析
- `missing_fields`：标识需要追问的信息

**为什么不直接让 LLM 输出自然语言描述意图**？→ 结构化输出可以直接驱动条件路由，不需要二次解析，减少出错的链路。

**追问**：LLM 输出的 JSON 格式不稳定怎么办？→ 用 `output_parser.py` 做容错解析 + retry 机制，极端情况下走 fallback 规则。

---

### Q9：RAG 在你的系统里是怎么集成的？为什么设计成外部服务？

**面试官在考察**：RAG 策略的理解，服务边界的设计

**高分回答**：

RAG 作为一个**独立的外部 HTTP 服务**，不和主流程耦合。

原因：
1. **职责分离**：RAG 涉及向量检索 + rerank，有独立的技术栈（向量数据库、embedding 模型），不应该嵌入 LangGraph 节点
2. **独立扩缩**：RAG 服务的 QPS 和延迟特征和工作流不同，独立部署可以各自优化
3. **降低 LLM 幻觉**：Advice Node 拿到的不只是 LLM 知识，还有检索到的医学文献片段作为 grounding

调用链路：
```
RAG Node → HTTP → RAG Service → 向量检索 + rerank → 返回 top_k 文档片段
→ 注入 Advice Node 的 prompt 作为上下文
```

**追问**：为什么不直接在 prompt 里让 LLM 去搜索？→ 那是 WebGPT/Perplexity 的做法，需要 LLM 支持 function calling 去搜索。RAG 前置检索可以精确控制知识来源（只检索经过审核的医学文献），更适合医疗场景。

---

### Q10：LLM 调用怎么控制成本和延迟？

**面试官在考察**：生产环境的考量

**高分回答**：

1. **按需调用**：不是每个请求都走完整的 LLM 链路。Parser 之后通过条件路由跳过不需要的 LLM 节点，用户只记录数据就不触发 Advice/Plan 的 LLM 调用。

2. **Prompt 缓存**：系统调用的 prompt 中，系统提示词部分是固定的，可以用 Anthropic 的 prompt caching 或其他 LLM 的类似机制节省输入 token。

3. **模型分层**：Parser（意图识别）用轻量模型（快 + 便宜），Advice/Plan（内容生成）用强模型（准 + 贵），按场景匹配模型能力。

4. **输出长度控制**：结构化 JSON 输出限制 max_tokens，不让 LLM 无限生成。

---

## 四、系统设计与工程实践

### Q11：如果 5 个测试全挂了，你怎么排查？（参考 1.1fail.md）

**面试官在考察**：Debug 能力，排查思路是否系统化

**高分回答**：

从 1.1fail.md 的日志来看，所有 5 个测试都卡在 `parser_node.py` 调用 LLM 时报 `401 AuthenticationError`——说明 API Key 没配置。

排查思路（从底层到上层）：
1. **先看错误码**：401 = 认证失败，不是模型不存在（404）也不是额度不够（429）
2. **检查 .env 文件**：API Key 是否配置？key 是否过期？
3. **检查 config/settings.py**：是否正确读取了环境变量？
4. **补充**：配置加载应该有明确的启动检查（fail-fast），而不是等到实际调用时才报错

**额外建议**：这类问题应该在 CI 里加一个 smoke test（比如 check API key is configured），在跑完整测试之前先快速失败。

---

### Q12：这个系统的测试策略是什么？怎么测 LangGraph 工作流？

**面试官在考察**：测试思维，是否理解 Agent 系统的测试难点

**高分回答**：

由于 Agent 系统依赖 LLM 输出，测试分三层：

1. **单元测试（Node 级别）**：Mock LLM 输出，测试每个 Node 的逻辑。比如 Mock Parser 返回固定 JSON，测试 Intent Normalize 逻辑是否正确。

2. **集成测试（子图级别）**：Mock 外部依赖（LLM/DB/RAG），测试子图内部状态流转。比如给定 mock 的 advice 和 plan_draft，测试 Conflict → Confirm → Archive 链路。

3. **端到端测试（workflow 级别）**：需要真实的 LLM 调用（test_workflow_basic.py 的意图）。但 LLM 输出不稳定，所以 E2E 测试不应该 assert 具体内容，而是 assert：
   - 流程走完了没有报错
   - State 里关键字段不为空
   - 意图路由正确

**关键点**：不推荐对 LLM 输出做精确断言，那会让测试极其脆弱。测试的是「流程走通」+「结构正确」，而非「内容正确」。

---

### Q13：Memory 系统为什么设计成 Markdown 文件而不是向量数据库？

**面试官在考察**：对技术复杂度的克制，是否过度设计

**高分回答**：

第一版不做过度设计。当前阶段的核心需求是「把用户长期偏好放进 prompt 上下文」，不需要语义检索。

Markdown 文件方案的优势：
- 人类可读、可编辑、可审计（医疗场景很有意义）
- 零依赖、零部署成本
- 加载就是全文读取，不需要检索，不需要 embedding

Mem0 或向量数据库在该场景下的劣势：
- 过度设计：引入向量库、embedding 模型、检索 pipeline，运维成本大增
- 语义检索的精度问题反而可能引入噪音（召回不相关的历史片段）

**Policy Filter 的设计才是重点**：不是所有对话都能写入记忆。通过关键词过滤（"通常"/"一般" vs "今天"/"明天"/"这次"），只保存长期偏好，不保存一次性数据。

**金句**：「简单优先」不是偷懒，是知道什么阶段该用什么方案。当前阶段文件方案够用，等用户量上来、需要语义检索时再升级到 SQLite + 向量库。

---

### Q14：数据库里存什么？文件里存什么？是怎么划分的？

**面试官在考察**：数据建模能力，边界意识

**高分回答**：

三个存储系统，各管各的：

| 存储 | 存什么 | 不存什么 |
|------|--------|----------|
| **SQLite** | 健康记录（血压/血糖每次读数）、计划（draft/active/archived）、提醒任务、用户信息 | 用户偏好、长期习惯 |
| **Markdown 文件** | 用户画像（profile/preferences/care_context） | 具体健康数据、具体计划实例 |
| **RAG 向量库** | 医学知识文档的向量索引 | 用户数据 |

**核心原则**：
- 业务数据（每次记录、每个计划）进 DB，需要 CRUD 操作
- 上下文数据（偏好、习惯）进 Memory 文件，每次对话全文加载
- "今天血压 145/92" 是业务数据，进 DB；"用户通常早上测血压" 是偏好，进 Memory

---

## 五、医疗场景特殊性

### Q15：医疗 AI 系统最需要注意什么？你怎么做的？

**面试官在考察**：安全意识，有没有想过医疗场景的特殊风险

**高分回答**：

四点核心设计：

1. **Rule Engine 兜底，不信任 LLM 的安全判断**：风险等级（血糖 10.5 是高危）由确定性规则判断，不由 LLM 判断。LLM 可能把高危说成正常。

2. **Human-in-the-Loop 是硬约束不是可选项**：计划必须用户确认，这是安全底线。技术上通过 `interrupt()` 保证流程不会绕过确认节点。

3. **Plan Conflict Detection**：新计划必须先和已有 active 计划做冲突检测，不能静默覆盖。比如用户已有"每天早上运动"的计划，新计划不应该创建冲突的提醒。

4. **保守输出策略**：Memory 文档里明确写了 "Avoid making diagnosis-level claims"、"Give conservative health advice"、"Encourage medical consultation when risk is high"。Prompt 层面也做了约束。

**追问**：如果有用户说"我头晕想吐，怎么办？"→ 系统应该识别为紧急情况，不走正常流程，直接建议就医。这是规则引擎的另一个重要职责。

---

### Q16：用户说"帮我记录血糖，给点建议，顺便提醒晚上再测一次"，系统怎么处理的？

**面试官在考察**：端到端理解，能不能串起整体流程

**高分回答**：

```
Step 1: Memory 加载 → 读取用户画像（知道用户关注血糖管理）
Step 2: Parser Node → LLM 解析多意图
        → routing: {record: true, advice: true, reminder: true}
        → slots: {blood_glucose: {value: 10.5}, reminder: {task: "测血糖", time: "晚上"}}
Step 3: Normalize → need_advice → need_history + need_risk + need_rag（补全依赖）
Step 4: Router 条件分发：
        - Record 分支 → 写入 DB
        - Advice 分支 → History Node → Risk Node（Rule 判断：血糖 10.5 = 高危）
          → RAG Node（检索糖尿病管理知识）
          → Advice Node（综合生成建议："您的血糖偏高，建议..."）
        - Reminder 分支 → Direct Reminder Node → User Confirm → Reminder Create
Step 5: Response Node 汇总 → 返回给用户
Step 6: Memory 更新 → 从 session summary 提取候选记忆
```

---

## 六、行为面试 / 项目难点

### Q17：这个项目你踩过最大的坑是什么？怎么解决的？

**面试官在考察**：问题解决能力，复盘能力

**结合项目实际情况的参考回答**：

- **坑 1（1.1fail.md 暴露的）**：环境变量/API Key 没配置导致全部测试挂掉。解决：加了 .env.example 模板 + startup check（服务启动时检查必要配置是否存在）
- **坑 2（可能的）**：Intent Normalize 不完善导致流程不完整。比如用户说 "给我制定计划"，Parser 只 set 了 need_plan=true，但没 set need_advice=true，导致计划生成时缺少建议上下文。解决：加 Normalize 层补全依赖链
- **坑 3（可能的）**：Prompt 修改后测试全部失败，因为 LLM 输出格式变了。解决：结构化 JSON 输出 + output_parser 容错 + E2E 只验证结构不验证内容

**金句**：面试官最喜欢听"我一开始以为……后来发现……于是改成……"这种有反思的回答。

---

### Q18：如果让你重新设计这个系统，你会改什么？

**面试官在考察**：反思能力，技术审美

**高分回答**（任选 2-3 个）：

1. **加 Observability**：加 LangSmith/LangFuse trace，每个 Node 的耗时、token 消耗、成功率一目了然。现在 Debug 只能看日志。

2. **加 Plan 的版本管理**：当前只有 draft/active/archived 三个状态，但没有版本号。如果用户连续修改计划，应该保留修改历史。

3. **RAG 从 HTTP 调用改成 MCP 协议**：更标准化，工具发现和调用更规范。

4. **测试加 Mock LLM 的 fixture**：当前 E2E 测试依赖真实 LLM 调用（慢 + 不稳定 + 花钱），应该有 mock 模式支持 CI 快速验证流程。

**关键**：不要批评之前的设计"不好"，要说"如果有更多时间/资源，我会加什么"。

---

## 面试速查表

### 高频 5 问（一定要准备）

| 问题 | 核心得分点 |
|------|-----------|
| 为什么 LangGraph | 显式 DAG > 黑盒 Agent，条件路由 + HITL 是硬需求 |
| State 不可变性 | 每个 Node 返回更新字典，不直接修改，保证可追溯 |
| 多意图怎么处理 | Parser(JSON) → Normalize(补全) → Router(条件分发) |
| 医疗安全怎么保证 | Rule 兜底 + HITL 确认 + 保守 prompt |
| RAG 为什么独立 | 技术栈解耦 + 独立扩缩 + 知识来源可控 |

### 最容易被追问到墙角的回答

- "Node 就是函数的封装" → 应该是"有明确输入输出契约的执行单元"
- "RAG 就是在 prompt 里加文档" → 应该讲检索策略、rerank、知识来源管控
- "LLM 来判断风险等级" → 应该是 Rule Engine 判断，LLM 不负责安全
- "测试就是跑 test_workflow_basic.py" → 应该分层讲单元/集成/E2E 策略

---

### 参考资料

- 项目架构文档：`docs/ARCHITECTURE.md`
- 工作流文档：`docs/WORKFLOW.md`
- 项目结构文档：`docs/STRUCTURE.md`
- Memory 系统文档：`docs/MEMORY_SYSTEM.md`
- Schema 设计文档：`docs/SchemaReadme.md`
