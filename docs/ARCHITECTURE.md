
---

# 🧠 Chronic Care Agent 架构设计文档（ARCHITECTURE.md）

## 1. 项目概述

Chronic Care Agent 是一个面向慢性病管理的智能系统，支持用户通过自然语言完成以下任务：

* 健康数据记录（血压 / 血糖 / 症状等）
* 个性化健康建议生成
* 健康计划制定（饮食 / 运动 / 监测）
* 提醒任务创建与管理
* 长期健康状态跟踪

系统基于 **LangGraph 工作流架构** 构建，实现多意图解析、条件执行、可控推理以及人机协同决策。

---

## 2. 总体架构

系统采用分层设计：

```text
┌──────────────────────────────┐
│        API / UI 层           │
├──────────────────────────────┤
│     LangGraph 工作流层        │  ← 主图 + plan_reminder 子图
├──────────────────────────────┤
│   Memory 层（用户画像）       │  ← 长期上下文
├──────────────────────────────┤
│   Core 能力层（LLM / Rule）  │  ← 推理与规则
├──────────────────────────────┤
│ 外部服务层（RAG / DB / Scheduler） │ ← 数据与执行
└──────────────────────────────┘
```

---

## 3. 核心设计思想

### 3.1 职责分离

系统将能力拆分为三类：

```text
LLM（认知）
- 意图理解
- 信息抽取
- 建议生成
- 计划生成

Rule Engine（安全）
- 风险判断
- 规则约束
- 冲突检测

External Services（执行）
- 数据存储（DB）
- 知识检索（RAG）
- 提醒调度（Scheduler）
```

---

### 3.2 工作流驱动（LangGraph）

系统核心由 LangGraph 驱动：

```text
LangGraph = Workflow Orchestrator
```

职责：

* 控制节点执行顺序
* 支持条件跳转（skip node）
* 支持多意图并行执行
* 管理状态流转（State）

---

### 3.3 多意图执行机制

系统支持用户同时表达多个需求：

```text
例如：
“帮我记录血糖，并给点建议，顺便提醒我晚上再测一次”
```

系统处理为：

```python
intent = {
    "need_record": True,
    "need_advice": True,
    "need_plan": False,
    "need_reminder": True
}
```

然后通过 Router 控制执行路径。

---

### 3.4 意图归一化（Intent Normalize）

为避免流程不完整，引入 Normalize 层：

```text
need_plan → need_advice
need_advice → need_history + need_risk + need_rag
need_reminder → 判断 direct / plan
```

---

### 3.5 人机协同（Human-in-the-loop）

关键决策（计划执行）必须用户确认：

```text
Plan Draft → Conflict Check → User Confirm → Plan Archive
```

避免：

* 误执行
* 高风险建议直接生效

---

## 4. 工作流结构（概览）

```text
User Input
   ↓
Parser Node（LLM）
   ↓
Intent Normalize
   ↓
Router（条件路由）
   ↓
──────────条件执行──────────
│                         │
│ Record Node → DB        │
│                         │
│ History → Risk → RAG    │
│                ↓        │
│            Advice Node  │
│                         │
│ ┌── plan_reminder_sub ──┐│
│ │ Plan Draft → Conflict ││
│ │ → User Confirm → Archive│
│ │ → Reminder Create    ││
│ └──────────────────────┘│
──────────汇聚───────────
         ↓
Response Node
         ↓
Output
```

---

## 5. 核心模块划分

### 5.1 Graph 层（流程控制）

职责：

* 定义工作流 DAG
* 控制节点执行
* 管理状态（ClinicalState）

关键组件：

```text
state.py        → 状态定义（含 memory_context / task_preferences）
builder.py      → 构建主图 DAG
plan_reminder_graph.py → 计划+提醒子图（独立编译）
routing.py      → 主图条件路由
normalizer.py   → 意图补全
```

---

### 5.2 Nodes 层（执行单元）

每个 Node 只做一件事：

```text
Parser Node        → LLM 解析
Record Node        → 写数据库
History Node       → 查询历史
Risk Node          → 风险判断（Rule）
RAG Node           → 外部知识检索
Advice Node        → LLM生成建议
Plan Draft Node    → LLM生成计划
Conflict Node      → 冲突检测
User Confirm Node  → 人机交互
Plan Archive Node  → 存储计划
Reminder Node      → 创建提醒
Response Node      → 输出整合
```

---

### 5.3 Core 层（能力封装）

```text
LLM Layer
- prompt管理
- 模型调用

Rule Layer
- 风险判断
- 计划冲突检测

Tools
- 时间解析
- 数据处理
```

---

### 5.4 数据层（Database）

存储：

```text
- 健康记录（血压/血糖）
- 计划（draft / active / archived）
- 提醒任务
- 用户信息
```

---

### 5.5 RAG 服务（外部）

设计为独立服务：

```text
LangGraph → HTTP → RAG Service
```

功能：

* 医学知识检索
* 向量检索 + rerank
* 降低 LLM 幻觉

---

### 5.6 Scheduler（提醒系统）

职责：

```text
- 创建提醒
- 定时执行
- 管理任务状态
```

---

### 5.7 Memory（用户画像系统）

职责：

```text
- 加载用户长期上下文（profile / preferences / care_context）
- 为 Advice Node 和 plan_reminder 子图提供用户偏好
- 对话结束后从摘要提取候选记忆并写入文档
- 通过 policy 过滤，只保存长期偏好，不保存一次性数据
```

数据存储：

```text
data/memory/users/{user_id}/
├── profile.md        # 用户画像（健康关注点、长期目标）
├── preferences.md    # 用户偏好（提醒风格、运动习惯）
└── care_context.md   # 慢病管理背景（当前关注重点）
```

调用时机：

```text
工作流入口：load_user_memory → 注入 memory_context
工作流出口：update_from_session_summary → 按需更新画像
```

---

## 6. 状态管理（ClinicalState）

系统通过统一状态流转：

```python
class ClinicalState:
    user_input
    intent

    memory_context      # 用户画像（profile + preferences + care_context）
    task_preferences    # 计划/提醒子图专用偏好上下文

    extracted_data

    history_data
    risk_level

    rag_docs
    advice

    plan_draft
    plan_conflicts
    user_confirmed

    confirmed_plan
    reminder_created / reminder_result

    final_response
```

---

## 7. 计划系统设计

### 生命周期：

```text
draft → confirmed → active → archived / replaced / cancelled
```

---

### 关键规则：

```text
1. 计划必须用户确认后才能生效
2. Reminder 只能基于 confirmed_plan 创建
3. 新计划必须进行冲突检测
4. 冲突计划不能直接覆盖旧计划
```

---

## 8. 提醒系统设计

### 两种来源：

```text
1. direct_reminder
   用户直接创建提醒

2. plan_reminder
   从 confirmed_plan 自动生成
```

---

## 9. 数据流

### 写入：

```text
User → Parser → Record → DB
```

---

### 推理：

```text
User → History → Risk → RAG → Advice
```

---

### 计划：

```text
Advice → Plan Draft → Confirm → Archive
```

---

### 提醒：

```text
Confirmed Plan → Reminder → Scheduler
```

---

## 10. 系统特点总结

```text
✔ 基于 LangGraph 的可控工作流
✔ 多意图组合执行
✔ 人机协同确认机制
✔ RAG 外部化设计
✔ Rule + LLM 混合决策
✔ 可扩展节点架构
```

---

## 11. 扩展方向

```text
- CGM实时血糖接入
- 医生审核节点
- 多用户系统
- 健康预测模型
- 图数据库（GraphRAG）
```

---

# ✅ 一句话总结

> 本系统是一个基于 LangGraph 的慢性病管理工作流系统，通过多意图解析、条件路由、LLM推理、规则约束和RAG知识检索，实现可控、可扩展的人机协同健康管理。

