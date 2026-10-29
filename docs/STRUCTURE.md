
---

#  Chronic Care Agent 项目结构设计（STRUCTURE.md）

## 1. 项目结构概览

```text
chronic-care-agent/
│
├── README.md                  # 项目简介 + 快速启动
├── requirements.txt
├── .env.example
│
├── docs/                      # 文档
│   ├── ARCHITECTURE.md
│   ├── WORKFLOW.md
│   └── STRUCTURE.md
│
├── app/                       # 主应用代码（核心）
│
├── data/                      # 数据（本地开发）
│   ├── sqlite/
│   ├── vector_store/
│   ├── raw_docs/
│   └── memory/               # 用户画像文件
│       └── users/
│           └── {user_id}/
│               ├── profile.md
│               ├── preferences.md
│               └── care_context.md
│
├── scripts/                   # 工具脚本
│
└── tests/                     # 测试
```

---

## 2. 核心代码结构（app/）

```text
app/
├── main.py                   # FastAPI 应用入口，注册路由与启动服务
│
├── api/                      # API 层：负责 HTTP 请求与响应
│   ├── routes.py             # 定义接口路由，例如 /api/chat
│   └── schemas.py            # 定义 API 请求/响应的数据结构
│
├── graph/                    # LangGraph 工作流编排层（最核心）
│   ├── state.py              # 定义 ClinicalState，全流程共享状态
│   ├── builder.py            # 构建主图 DAG，连接各个节点
│   ├── plan_reminder_graph.py # 计划+提醒子图，独立编译后嵌入主图
│   ├── routing.py            # 主图条件路由逻辑
│   ├── normalizer.py         # 意图归一化，补全依赖关系
│   └── workflow.py           # 工作流统一入口，供 API 调用
│
├── nodes/                    # 工作流节点层：每个文件对应一个业务节点
│   ├── parser_node.py        # 解析用户输入，识别多意图并抽取健康信息
│   ├── record_node.py        # 将血糖、血压、症状等健康数据写入数据库
│   ├── history_node.py       # 查询用户历史健康记录与趋势数据
│   ├── risk_node.py          # 调用规则引擎进行风险等级判断
│   ├── rag_node.py           # 调用外部 RAG 服务检索医学知识
│   ├── advice_node.py        # 基于数据、风险和 RAG 结果生成健康建议
│   ├── plan_draft_node.py    # 根据健康建议生成计划草稿
│   ├── plan_conflict_node.py # 检查新计划与已有计划是否冲突
│   ├── user_confirm_node.py  # 用户确认节点，用于计划/提醒执行前审阅
│   ├── plan_archive_node.py  # 用户确认后归档计划并创建计划提醒
│   ├── reminder_router_node.py # 提醒链路入口
│   ├── direct_reminder_node.py # 处理用户直接提出的提醒需求
│   ├── reminder_create_node.py # 调用调度服务创建提醒任务
│   └── response_node.py      # 汇总各节点结果，生成最终回复
│
├── core/                     # 核心能力层：封装 LLM、规则和工具
│   ├── llm/                  # 大模型调用相关模块
│   │   ├── client.py         # OpenAI-compatible LLM 调用客户端
│   │   ├── prompts.py        # Prompt 模板集中管理
│   │   └── output_parser.py  # 解析 LLM 输出，尤其是 JSON 输出
│   │
│   ├── rules/                # 规则引擎层：医疗风险和计划冲突控制
│   │   ├── risk_engine.py    # 风险规则总入口，整合血糖/血压风险
│   │   ├── glucose_rules.py  # 血糖风险判断规则
│   │   ├── blood_pressure_rules.py # 血压风险判断规则
│   │   └── plan_conflict_rules.py  # 计划冲突检测规则
│   │
│   └── tools/                # 通用工具函数
│       ├── time_parser.py    # 时间表达解析，如“今晚9点”
│       ├── stats_tool.py     # 健康数据统计工具
│       └── id_generator.py   # 生成记录、计划、提醒等唯一 ID
│
├── rag_client/               # RAG 服务调用层
│   ├── client.py             # 调用外部 RAG API 的客户端
│   └── schemas.py            # RAG 请求与响应结构定义
│
├── database/                 # 数据访问层
│   ├── connection.py         # 数据库连接初始化
│   └── models.py             # 新版用户、观测、计划、提醒、会话与审计模型
│
├── service/                  # 业务与事务边界
│   ├── auth_service.py       # 登录、JWT、可撤销会话
│   ├── conversation_service.py # 会话与计划确认恢复
│   ├── health_service.py     # 健康观测与趋势统计
│   ├── plan_service.py       # 计划状态机
│   └── reminder_service.py   # 提醒与 outbox 写入
│
├── worker/                   # 独立后台任务
│   └── reminder_worker.py    # outbox 投递、重试和去重
│
├── config/                   # 配置管理
│   ├── settings.py           # 从 .env 读取 API Key、模型、数据库等配置
│   └── constants.py          # 全局常量，如节点名、状态名、风险等级
│
└── memory/                   # 用户记忆系统（轻量用户画像）
    ├── service.py            # 对外统一接口（memory_service 单例）
    ├── store.py              # 登录用户写数据库；未登录测试 fixture 可使用本地 md
    ├── updater.py            # 从 session summary 提取候选记忆并写入
    └── schemas.py            # MemoryContext / MemoryCandidate 数据结构
```

---

## 3. 模块职责说明

---

### 3.1 api/

```text
职责：
- 接收用户请求
- 调用 LangGraph workflow
- 返回结果
```

---

### 3.2 graph/（系统核心）

```text
职责：
- 构建工作流（DAG）
- 控制执行路径
- 管理状态流转
```

#### 关键文件：

```text
state.py        → 定义 ClinicalState
builder.py      → 定义节点连接关系
routing.py      → 控制节点是否执行
normalizer.py   → 补全意图依赖
workflow.py     → 工作流入口
```

---

### 3.3 nodes/

```text
职责：
- 每个 Node 负责一个业务步骤
- 不负责流程控制
```

#### 设计原则：

```text
✔ 单一职责
✔ 无副作用（除 DB 写入）
✔ 可独立测试
```

---

### 3.4 core/

```text
职责：
- 封装核心能力
```

#### 子模块：

##### llm/

```text
- 模型调用
- prompt 管理
- 输出解析
```

##### rules/

```text
- 风险判断（血压 / 血糖）
- 计划冲突检测
```

##### tools/

```text
- 时间解析
- 工具函数
```

---

### 3.5 rag_client/

```text
职责：
- 调用外部 RAG 服务
- 获取医学知识
```

---

### 3.6 database/

```text
职责：
- 存储健康记录
- 存储计划
- 存储提醒
```

---

### 3.7 service/

```text
职责：
- 统一业务规则与事务边界
- 实现用户数据隔离、幂等和状态机
```

---

### 3.8 worker/

```text
职责：
- 扫描 notification_outbox
- 执行提醒投递、重试和去重
```

---

### 3.9 config/

```text
职责：
- 管理配置
- API Key
- 环境变量
```

---

## 4. 模块调用关系

```text
API
 ↓
Graph（workflow）
 ↓
Nodes（主图：解析/记录/分析/建议）
 ↓
plan_reminder_sub（子图：计划+提醒）
 ↓
Core / RAG / DB / Scheduler / Memory
```

---

## 5. 数据流

### 写入数据

```text
User → Parser → Record → DB
```

---

### 获取建议

```text
User → History → Risk → RAG → Advice
```

---

### 计划生成

```text
Advice → Plan Draft → Confirm → Archive
```

---

### 提醒创建

```text
Confirmed Plan → Reminder → Scheduler
```

---

## 6. 关键设计原则

```text
1. LangGraph 只负责流程控制
2. Node 只负责业务逻辑
3. LLM 只负责认知（理解/生成）
4. Rule 负责安全控制
5. RAG 独立为外部服务
6. Reminder 只能基于确认后的计划
```

---

## 7. 一句话总结

> 本项目采用模块化架构，将工作流编排、节点逻辑、核心能力和外部服务解耦，实现一个可扩展、可测试、可维护的慢性病管理系统。

---

