好，这里给你一版**最终整理好的 `docs/WORKFLOW.md`（完整工程版）**，已经和你现在的设计完全对齐（多意图 + 条件路由 + Plan确认 + Reminder机制），可以直接用。

---

# 🔄 Chronic Care Agent 工作流设计（WORKFLOW.md）

## 1. 工作流概述

本系统基于 **LangGraph** 构建工作流，核心特点：

* 支持**多意图组合执行**（记录 / 建议 / 计划 / 提醒）
* 支持**条件节点执行（按需跳过）**
* 支持**人机协同（计划必须确认）**
* 支持**动态路径组合（非固定流水线）**

---

## 2. 主流程结构

```text
User Input
   ↓
[Memory] load_user_memory → memory_context 注入 State
   ↓
Parser Node（LLM）
   ↓
Intent Normalize Node
   ↓
Router（条件路由）
   ↓
──────────── 条件执行区 ────────────
│                                 │
│ [记录数据]                       │
│   Record Node → DB              │
│                                 │
│ [健康分析]                       │
│   History → Risk → RAG          │
│                  ↓              │
│              Advice Node        │
│                                 │
│ [计划+提醒子图 plan_reminder_sub]│
│   Plan Draft → Conflict Check   │
│   → User Confirm → Archive      │
│   → Reminder Router             │
│   → direct / plan Reminder      │
│   → Reminder Create             │
│                                 │
──────────── 汇聚 ────────────────
        ↓
Response Node
        ↓
[Memory] update_from_session_summary
        ↓
Output
```

---

## 3. 多意图机制

Parser Node 输出：

```json
{
  "need_record": true,
  "need_advice": true,
  "need_plan": false,
  "need_reminder": true,
  "need_history": true
}
```

---

## 4. 意图归一化（Intent Normalize）

用于补全依赖关系：

```text
need_plan → need_advice

need_advice →
    need_history
    need_risk
    need_rag

need_reminder →
    判断来源：
    - direct_reminder
    - plan_reminder
```

---

## 5. 条件执行逻辑

系统不是固定流程，而是按需执行节点。

---

### 5.1 数据记录分支

```text
条件：
need_record=True

流程：
Record Node → Database
```

---

### 5.2 健康建议分支

```text
条件：
need_advice=True

流程：
History Node
→ Risk Node
→ RAG Node
→ Advice Node
```

说明：

* History：获取历史数据
* Risk：规则判断风险
* RAG：检索医学知识
* Advice：生成建议

---

### 5.3 计划生成分支（核心流程）

```text
条件：
need_plan=True

流程：
Plan Draft Node
→ Plan Conflict Check Node
→ User Confirm Node
→ Plan Archive Node
```

---

#### 关键规则：

```text
1. Plan Draft 只生成草稿（draft）
2. 必须经过用户确认
3. 才能归档（active）
4. Reminder 只能基于 confirmed plan 创建
```

---

### 5.4 提醒流程

#### 情况1：直接创建提醒

```text
条件：
need_reminder=True 且 need_plan=False

流程：
Direct Reminder Node
→ User Confirm Node
→ Reminder Create Node
```

---

#### 情况2：基于计划创建提醒

```text
条件：
need_plan=True 且 user_confirmed=True

流程：
从 confirmed_plan 提取时间点
→ Reminder Create Node
```

---

## 6. 人机交互节点（User Confirm）

User Confirm Node 是关键中断点：

### 返回结果：

```text
confirm   → 继续流程
reject    → 终止计划
modify    → 返回 Plan Draft
```

---

## 7. 典型执行路径

---

### 7.1 只记录数据

```text
Parser → Normalize → Record → Response
```

---

### 7.2 只咨询建议

```text
Parser → Normalize
→ History → Risk → RAG → Advice
→ Response
```

---

### 7.3 生成计划

```text
Parser → Normalize
→ History → Risk → RAG → Advice
→ Plan Draft → Conflict → Confirm → Archive
→ Response
```

---

### 7.4 创建提醒

```text
Parser → Normalize
→ Direct Reminder → Confirm → Create
→ Response
```

---

### 7.5 全流程（最复杂）

```text
Parser → Normalize → Record
→ History → Risk → RAG → Advice
→ Plan Draft → Conflict → Confirm → Archive
→ Reminder Create
→ Response
```

---

## 8. 执行特点总结

```text
✔ 多意图组合执行（不是单一路径）
✔ 节点按需跳过（条件路由）
✔ Plan 必须确认后才能生效
✔ Reminder 依赖 confirmed plan
✔ 支持 direct 和 plan 两种提醒模式
✔ 工作流可中断（Human-in-the-loop）
✔ 计划+提醒抽成独立子图（plan_reminder_sub）
✔ 工作流入口/出口挂接用户画像记忆系统
```

---

## 9. 关键依赖关系

```text
Advice 依赖：
History + Risk + RAG

Plan 依赖：
Advice

Reminder 依赖：
direct 或 confirmed_plan
```

---

## 10. 一句话总结

> 本系统通过 Parser 识别多意图，通过 Normalize 补全依赖，通过 Router 控制节点执行，实现一个支持动态路径组合的人机协同健康管理工作流。

---

如果你下一步要落代码，最关键就是：

👉 把这个 WORKFLOW → `graph/builder.py`

你直接说：

👉 **“写 builder.py”**

我帮你把整个流程转成 LangGraph DAG（这一步是核心）。
