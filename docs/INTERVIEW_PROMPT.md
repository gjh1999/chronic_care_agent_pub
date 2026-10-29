# 面试回答：提示词设计

**日期**：2026-07-09
**对应问题**："你这个项目的提示词是怎么写的？"

---

## 一句话总起

> 我把模型调用分成了两条链路：**高频的结构化提取走 fine-tune 小模型**，**低频的深度推理走通用大模型**。提示词的写法在这两条链路上思路完全不同。

---

## 第一条链路：意图识别 + 信息抽取 → Fine-tune 的 Qwen 模型

这里没有用通用大模型 + 超长 prompt 硬撑，而是选了一个外部微调过的 Qwen 模型。

**为什么？** 意图识别和信息抽取（血糖值、血压值、症状名、时间表达）是高频调用 + 固定 Schema + 对延迟敏感的任务。每个用户请求都要走这个节点。如果用大模型，token 消耗大、延迟高、输出格式还不稳定。

Fine-tune 的 Qwen 模型直接解决了三个问题：

### 1. 不需要在 prompt 里写复杂的 Schema 描述

用通用模型时，你得在 prompt 里把所有字段定义一遍（字段名、类型、取值范围、null 条件），光 Schema 描述就吃掉几百个 token。Fine-tune 模型在训练阶段已经学会了输出格式，推理时只需要简短指令 + 用户输入，prompt 可以极简。

### 2. 输出更稳定

通用模型偶尔会漏字段、多写字、JSON 格式不对，需要 output_parser 做正则兜底、retry、fallback。Fine-tune 模型因为训练时就对着这个 Schema 学的，输出的 JSON 结构一致性远高于通用模型。这对流水线系统很重要——后面十个节点都等着这个输出做路由和数据写入。

### 3. 延迟和成本都可控

Qwen 小参数量模型推理速度远快于大模型，适合作为每次请求的"守门人"。大模型只留给 Advice 和 Plan 这种需要深度推理、调用频率低的节点。

### 这个 prompt 的写法逻辑是"指令型"而不是"示例型"

不需要几个 few-shot（模型已经会了），重点是给出清晰的输出规范：
- 路由维度有哪些（need_record / need_advice / need_plan / need_reminder / need_history）
- 槽位有哪些（血糖/血压/体重/饮食/运动/用药/症状，每个字段的固定结构）
- 哪些字段必填、缺失信息该怎么标记（missing_fields）
- 风险预标怎么做（risk_flags 给后续 Rule Engine 发信号）

Prompt 短且精准，token 消耗小。

**本质上，这是在给模型划边界，而不是在教模型做任务。** 教是 fine-tune 阶段完成的。

### 为什么输出是结构化 JSON 而不是自然语言？

一个具体场景就能讲清楚：用户说"我今天早上测了血压 145/92，有点头晕，帮我记一下，顺便给点建议"。

如果输出自然语言"用户想记录血压数据并获取健康建议"，下游还得再调一次 LLM 去提取具体数值——多一轮调用，延迟翻倍，出错概率也翻倍。

结构化 JSON 意味着一轮调用就直接产出机器可执行的路由指令和数据：

```json
{
  "routing": { "need_record": true, "need_advice": true, "need_plan": false, "need_reminder": false, "need_history": false },
  "confidence": { "need_record": 0.97, "need_advice": 0.85, ... },
  "slots": {
    "record": { "blood_pressure": { "systolic": 145, "diastolic": 92, "unit": "mmHg", "time": "早上" }, ... },
    "advice": { "topic": "blood_pressure", "question": "血压145/92是否偏高" }
  },
  "missing_fields": [],
  "risk_flags": ["血压偏高"],
  "normalized": { "time_of_day": "morning" }
}
```

LangGraph 的路由拿到 routing 直接走条件边，Record Node 拿到 slots.record 直接写库，不需要任何中间解析。

### JSON 不稳定怎么办？

虽然 fine-tune 模型输出一致性已经远好于通用模型，还是加了 `output_parser.py` 做兜底：正则 `\{.*\}` 先容错提取，实在解析不了才抛异常。后面规划是加 JSON Schema 约束校验 + retry。

---

## 第二条链路：建议生成 + 计划生成 → 通用大模型 + 结构化 prompt

Advice 和 Plan 节点没有 fine-tune，而是用通用大模型 + 精心设计的 prompt。

**为什么这两个不用 fine-tune？** 因为需求一直在迭代——今天加一个"不要制造恐慌"的约束，明天加一个"引用 RAG 证据"的要求，后天调整输出格式。Fine-tune 的迭代周期太长，prompt engineering 可以分钟级调整护栏。判断标准很简单：**Schema 固定的任务 fine-tune 一次收益持续，规则频繁调整的任务 prompt 更灵活。**

### Advice 的 prompt：按"证据链"组织输入

```text
用户长期画像 → 用户当前问题 → 当前健康数据 → 历史数据 → Rule 风险评级 → RAG 医学文献 → 输出建议
```

关键设计：
- **每个信息来源都有明确的标签**（【用户长期上下文】、【规则风险评估】、【RAG 检索医学证据】），模型在生成建议时能区分哪些是用户说的、哪些是规则判的、哪些是文献查的
- **加了一句"不要编造 RAG 证据中没有的医学结论"** —— 医疗场景下这是安全底线，防止模型在缺乏文献支撑时用训练数据的记忆补全
- **语气约束**："温和、不要制造恐慌"、"区分健康管理建议和需要医生判断的部分"

### Plan 的 prompt：把所有约束直接灌进去

目标、周期、偏好（"饭后""低强度"）、限制（"不能跑步"），让模型在约束空间内生成可执行的任务列表。输出是结构化 JSON，可以直接被调度器消费。

---

## 第三层：System Message 安全护栏

所有面向用户输出的调用共享一层底层约束：

- 不诊断疾病
- 不开处方药
- 不替代医生判断
- 不确定时建议就医
- 不要制造恐慌

这层跟 Rule Engine 是互补的：
- Rule Engine 做精确判断（血糖 10.5 = 高危，这是确定性规则，不能交给概率模型）
- Prompt 护栏做软约束（输出措辞不越界，不给"你得了糖尿病"这种诊断性表述）

两者一起构成了安全防线——**Rule 守住判断边界，Prompt 守住表达边界。**

---

## 选 fine-tune 还是选 prompt engineering？判断标准

| | Fine-tune | Prompt Engineering |
|---|---|---|
| 适用场景 | Schema 固定、高频调用、格式要求严格 | 规则频繁调整、需要灵活迭代 |
| 优势 | 输出稳定、延迟低、token 省 | 分钟级调整、零训练成本 |
| 劣势 | 迭代慢、需要标注数据 | 输出不够稳定、消耗更多 token |
| 本项目的选择 | Parser（意图识别 + 槽位填充） | Advice（建议生成）、Plan（计划生成） |

一句话：**该 fine-tune 的 fine-tune，该 prompt 的 prompt。不是非此即彼，是按任务特征分别选最优解。**

---

## 主动暴露的不足之处

如果面试官追问"有什么不足"，三个点：

### 1. Parser 要求归一化日期但没注入当前日期

模型输出 `normalized.date`（如"明天" → "2026-05-15"），但 prompt 里没有告诉模型今天是什么日期。Fine-tune 也解决不了这个问题——应该在调用时注入 `{current_date}` 占位符。

### 2. 两条链路的 LLM client 还没统一

Parser 链路和 Advice/Plan 链路走的是两套 client 代码，配置不一致（thinking 开关、连接池复用、system prompt 注入方式）。属于早期快速迭代的遗留问题，应该统一到一个 client，按调用场景传不同参数。

### 3. 用户画像还没灌入 Advice/Plan prompt

`memory_context` 在 State 里传了，但 Advice 和 Plan 的 prompt 模板没有使用它。生成的建议和计划还不够个性化——下一步就是把用户偏好（"不喜欢早上运动""喜欢简短直接的提醒"）注入 prompt。

---

## 面试速记版

记住这四个关键词 + 一个例子：

- **模型分层**：Parser = fine-tune Qwen（快稳省），Advice/Plan = 通用大模型（灵活可迭代）
- **Fine-tune 的 prompt 是"划边界"，不是"教做事"** —— 训练阶段学会了 Schema，推理时简短指令即可
- **通用模型的 prompt 核心是"证据链"** —— 画像 → 数据 → 历史 → 风险 → RAG → 输出，每步有据可查
- **选 fine-tune 还是 prompt 的判断标准是迭代频率**：固定 Schema fine-tune 一次收益持续，频繁调整的规则 prompt 分钟级可改
- **例子**：用户说"血压 145/92，帮我记录+给建议"——Parser（fine-tune Qwen）一轮调用输出路由 + 完整血压槽位 + 风险预标，后续十个 Node 直接消费，Parser 之后不再调 LLM 做解析
