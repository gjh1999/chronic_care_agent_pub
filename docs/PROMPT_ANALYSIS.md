# 提示词全景分析与优化建议

## 当前提示词清单

| 位置 | 用途 | 实际使用? |
|------|------|-----------|
| `prompts.py` `PARSER_PROMPT` | 意图识别+槽位填充 | 生产使用 |
| `prompts.py` `ADVICE_PROMPT` | 健康建议（模板） | **未被使用（死代码）** |
| `prompts.py` `PLAN_PROMPT` | 计划生成 | 生产使用 |
| `llm_client.py` system message | 全局 system prompt | 所有调用共用 |
| `advice_node.py` 内联 f-string | 健康建议（实际） | 生产使用 |

---

## 一、PARSER_PROMPT（最核心的提示词）

### 1.1 缺少当前日期注入

提示词要求模型输出 `normalized.date`（如 `"明天" → "2026-05-15"`），但从未告诉模型"今天是什么日期"。模型只能猜测，导致日期归一化准确率极低。

**修复**：prompt 模板中加入 `当前日期：{current_date}` 占位符，由调用方注入。

### 1.2 示例太少且覆盖不足

只有 2 个 few-shot 示例，且都偏"正向"场景。缺失的关键示例：

- **闲聊/问候**（"你好"）→ 所有 routing=false
- **紧急情况**（"我头晕得站不起来"）→ 需要紧急路由
- **模糊表达**（"最近感觉不太好"）→ 需要追问，missing_fields 非空
- **否定/修正**（"不对，不是血压，是血糖"）→ 意图修正
- **纯查询**（"我上周血压怎么样"）→ 仅 need_history=true

**修复**：补充 3-5 个覆盖边界场景的示例。

### 1.3 输出 Schema 强制输出 null 字段

JSON 模板要求所有 slot 字段都必须出现（即使是 null），导致输出 token 大量浪费在无意义字段上：

```json
"blood_glucose": null, "weight": null, "diet": null, "exercise": null, ...
```

**修复**：无数据时整个 slot 对象为 null；有数据时只输出非 null 字段。

### 1.4 缺少 `need_rag` 路由

架构文档（ARCHITECTURE.md）明确写了 RAG Node 是独立节点，但 `PARSER_PROMPT` 的路由里没有 `need_rag` 标志。`rag_node.py:20` 检查的是 `intent.get("need_rag", False)`——这个值永远不会被 Parser 设为 true。

**修复**：routing 中增加 `need_rag` 布尔值，Normalize 层补全 `need_advice → need_rag`。

### 1.5 缺少紧急程度分级

路由只有 5 个布尔值，没有紧急程度维度。医学场景需要区分：

| 级别 | 含义 | 行为 |
|------|------|------|
| routine | 正常咨询 | 走标准流程 |
| attention | 需关注 | 流程中强调风险 |
| urgent | 紧急 | 直接建议就医，不走复杂流程 |

**修复**：routing 中增加 `urgency: "routine" | "attention" | "urgent"` 字段。

### 1.6 `confidence` 字段使用不充分

每个路由都有置信度，但后续流程从未使用。低置信度（<0.6）时应该触发追问确认，而不是静默走流程。

**修复**：Router 中对 confidence < 阈值的意图走追问分支。

---

## 二、System Message（llm_client.py:25）

```python
"content": "你是一个慢性病管理助手，请给出清晰、安全、温和的建议。"
```

### 2.1 所有节点共用同一个 system message

Parser、Advice、Plan 三种截然不同的任务共用同一个 system prompt：

- Parser 需要"你是精确的 NLP 解析器，只输出 JSON"
- Advice 需要"你是保守的医疗顾问，基于证据给建议"
- Plan 需要"你是健康计划制定者，考虑用户偏好和约束"

**修复**：每个 prompt 自带 system role 定义，或在 `call_llm` 中支持传入 system message。

### 2.2 缺少医疗安全护栏

系统级应注入不可覆盖的安全规则：
- 遇到紧急症状（剧烈胸痛、严重呼吸困难等）必须建议立即就医
- 不诊断疾病、不开处方药
- 不替代医生判断
- 不确定时保守处理，宁可建议就医

**修复**：所有面向用户的 LLM 调用共享一份安全护栏 system prompt。

### 2.3 `enable_thinking: False` 硬编码

对 Parser 这种结构化提取任务，关掉 thinking 是对的（快+省）。但对 Advice 和 Plan 这种需要深度推理的任务，关掉 thinking 会降低建议质量和计划合理性。

**修复**：`call_llm` 增加 `enable_thinking` 参数，按调用场景决定。

---

## 三、Advice 提示词

### 3.1 ADVICE_PROMPT 模板未被使用

`prompts.py` 里定义了 `ADVICE_PROMPT`（221-239 行），但 `advice_node.py` 完全没有 import 它，而是写了一个内联 f-string。两者内容完全不同——`ADVICE_PROMPT` 是死代码。

**修复**：删除 `ADVICE_PROMPT`，把 `advice_node.py` 的内联 prompt 收敛到 `prompts.py`，统一管理。

### 3.2 没有结构化输出要求

Advice 输出是自由文本，下游难以解析和呈现。应要求结构化：

- 简短结论（1-2 句）
- 依据说明（区分：用户数据 / RAG证据 / 规则判断）
- 可执行建议列表（每条含优先级）
- 需要就医标记（true/false + 原因）

### 3.3 不处理 RAG 上下文为空的情况

当 `rag_context` 为空字符串时，prompt 中 `【RAG 检索医学证据】` 后面跟空白，模型会困惑。

**修复**：空值时整个 RAG 段落不渲染，或写为"（暂无检索到的医学证据，建议基于通用知识给出保守建议）"。

---

## 四、PLAN_PROMPT

### 4.1 输出格式过于简陋

```json
{"tasks": [{"task": "任务名称", "time": "HH:MM"}]}
```

缺少关键字段：

| 缺失字段 | 说明 |
|----------|------|
| 任务类型 | 用药 / 运动 / 饮食 / 监测 / 复查 |
| 优先级 | 哪些任务不能跳过 |
| 注意事项 | 如"饭后服用""测量前静坐5分钟" |
| 备用方案 | 如"下雨则改室内" |

### 4.2 没有注入 memory_context

Plan 是最需要用户偏好的地方（preferences.md 里的"不喜欢早上运动""喜欢饭后散步"等），但 `PLAN_PROMPT` 完全没有使用 `memory_context`，导致生成的计划无法个性化。

**修复**：`PLAN_PROMPT` 增加 `{memory_context}` 占位符，`plan_draft_node.py` 注入。

---

## 五、缺失的提示词

| 缺失场景 | 说明 |
|----------|------|
| Response 汇总 | 多个分支结果（记录结果 + 建议 + 计划确认 + 提醒创建）如何整合成一段自然的回复？ |
| 计划冲突解释 | 冲突检测失败时，如何向用户解释"为什么这个新计划和现有计划冲突"？ |
| 追问对话 | `missing_fields` 非空时，如何自然追问而不会让用户觉得被审问？ |
| 紧急响应 | risk_engine 判定 urgent 时，如何措辞严肃但有分寸地建议立即就医？ |
| 历史查询翻译 | 用户查历史数据时，如何把 DB 查询结果翻译成自然语言总结？ |

---

## 六、优化建议汇总

### P0 —— 必须修

1. **PARSER_PROMPT 注入当前日期**：加 `{current_date}` 占位符
2. **补上 `need_rag` 路由标志**：让 RAG Node 的条件判断真正生效
3. **System message 按节点拆分**：Parser / Advice / Plan 各自使用不同的 system prompt
4. **Advice 实际 prompt 收敛到 prompts.py**：删除死代码 `ADVICE_PROMPT`，迁入实际使用的版本

### P1 —— 应该修

5. **PARSER_PROMPT 增加边缘示例**：闲聊、紧急、模糊、多轮修正
6. **PARSER_PROMPT JSON Schema 瘦身**：只输出非 null 字段，减少 token 浪费
7. **PLAN_PROMPT 注入 memory_context**：个性化计划生成
8. **Advice 输出结构化**：分结论/依据/建议/就医标记

### P2 —— 可以优化

9. **区分 `enable_thinking`**：Parser 关闭、Advice/Plan 开启
10. **利用 `confidence` 做低置信度回退**：<0.6 时触发追问确认
11. **补充缺失 prompt**：Response汇总、冲突解释、追问、紧急响应、历史查询
12. **output_parser 增加 JSON Schema 校验**：不只正则提取，还要验证必填字段完整性
