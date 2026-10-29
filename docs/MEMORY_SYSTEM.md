下面给你一版可以直接放进项目里的设计文档，文件名建议：

```text
docs/MEMORY_SYSTEM.md
```

---

# Simple Memory System 设计文档

## 1. 设计目标

本项目的记忆系统采用**轻量级用户画像文档方案**。

当前阶段不引入向量库、长期记忆检索、BM25、关键词图等复杂机制，而是通过几个可读、可编辑、可控的用户画像文档保存用户长期上下文。

记忆系统的核心目标是：

```text
1. 保存用户长期偏好
2. 保存用户健康管理画像
3. 保存用户慢病管理相关背景
4. 在每次对话时将用户画像放入上下文
5. 在对话结束后根据摘要按需更新画像
```

本项目原有结构中已经包含健康记录、计划、提醒、调度、RAG 等模块，因此记忆系统不应该承担这些业务模块的职责，而应该作为一个轻量上下文模块辅助 Agent 和 TaskManager 使用。当前项目结构中，健康记录、计划、提醒、调度已经分别由 `database/`、`scheduler/`、`nodes/` 等模块承担 。

---

## 2. 设计原则

### 2.1 简单优先

第一版不做复杂检索。

不使用：

```text
- 向量数据库
- BM25
- 关键词图
- 长期记忆召回
- 多层压缩记忆
```

第一版使用 Markdown 文件，因为：



---

### 2.2 画像和业务数据分离

记忆系统只保存长期上下文。

不保存具体业务数据。

| 数据类型        | 存储位置                      |
| ----------- | ------------------------- |
| 用户偏好        | MemorySystem              |
| 用户画像        | MemorySystem              |
| 长期健康管理背景    | MemorySystem              |
| 单次血压 / 血糖记录 | Health Database           |
| 单次提醒任务      | TaskManager / Reminder DB |
| 具体计划实例      | TaskManager / Plan DB     |
| RAG 医学知识    | RAG / Knowledge Base      |

一句话：

```text
健康记录、计划、提醒是业务数据；
用户偏好、长期习惯、画像摘要是记忆数据。
```

---

### 2.3 可控更新

记忆系统不能把所有对话都写入用户画像。

应该经过以下流程：

```text
对话原文
  ↓
Session Summary
  ↓
Memory Candidate
  ↓
Policy Filter
  ↓
User Memory Documents
```

这样可以避免把一次性数据、临时情绪、不确定推测写入用户画像。

---

## 3. 模块边界

### 3.1 MemorySystem 负责什么

MemorySystem 负责：

```text
1. 加载用户画像上下文
2. 管理用户偏好文档
3. 管理健康管理背景文档
4. 根据对话摘要更新画像
5. 接收业务模块提交的记忆事件
6. 为 Agent / TaskManager 提供可放入 prompt 的上下文
```

---

### 3.2 MemorySystem 不负责什么

MemorySystem 不负责：

```text
1. 不负责保存具体健康记录
2. 不负责创建提醒
3. 不负责调度任务
4. 不负责生成健康计划
5. 不负责医学知识检索
6. 不负责替代数据库
7. 不负责诊断用户疾病
```

例如：

```text
“明天早上 8 点提醒我测血压”
```

这不应该写入 MemorySystem，而应该交给 TaskManager / Reminder DB。

再例如：

```text
“今天血压 145/92”
```

这不应该写入 MemorySystem，而应该进入 Health Record DB。

---

## 4. 推荐目录结构

```text
app/
├── memory/
│   ├── __init__.py
│   ├── service.py          # 对外统一接口
│   ├── store.py            # 读写用户画像文档
│   ├── updater.py          # 根据摘要更新用户画像
│   ├── summarizer.py       # 对话摘要生成
│   ├── policy.py           # 判断哪些信息可以进入记忆
│   └── schemas.py          # 记忆系统数据结构
```

数据目录：

```text
data/
├── memory/
│   └── users/
│       └── {user_id}/
│           ├── profile.md
│           ├── preferences.md
│           └── care_context.md
```

---

## 5. 用户记忆文档设计

第一版建议只保留三个文档：

```text
profile.md
preferences.md
care_context.md
```

---

## 5.1 profile.md

### 作用

`profile.md` 保存用户相对稳定的画像信息。

例如：

```text
- 用户主要关注什么健康问题
- 用户长期健康目标
- 用户自述的慢病管理背景
- 用户常见健康管理场景
```

### 示例

```md
# User Profile

## Basic Context

- User ID: u001
- Main health focus: blood pressure management.
- Long-term goal: build a stable daily health management routine.

## Health Management Focus

- Focuses on blood pressure monitoring.
- Interested in diet control and regular exercise.
- Needs support for maintaining consistent health habits.

## Notes

- Avoid treating user-reported information as confirmed medical diagnosis unless explicitly verified.
- Prefer conservative and safety-aware health suggestions.
```

### 注意事项

不要写成：

```md
- User has hypertension.
```

除非用户明确说自己已经确诊。

更安全的写法是：

```md
- User focuses on hypertension-related management.
```

或者：

```md
- User reported a history of hypertension.
```

---

## 5.2 preferences.md

### 作用

`preferences.md` 保存用户偏好。

主要服务于：

```text
1. Advice Node
2. TaskManager
3. Reminder generation
4. Response style control
```

### 示例

```md
# User Preferences

## Reminder Preferences

- Prefers short and direct reminders.
- Does not like very late-night reminders.
- Prefers reminders that are not too frequent.

## Exercise Preferences

- Prefers walking after dinner.
- Avoids intense exercise plans.
- Prefers simple and easy-to-follow routines.

## Advice Style

- Prefers practical and concise advice.
- Likes step-by-step explanations.
- Does not need overly long theoretical explanations.
```

### 适合写入的内容

```text
- 用户不喜欢早上运动
- 用户喜欢晚饭后散步
- 用户希望提醒简短
- 用户不希望提醒太频繁
- 用户喜欢直接一点的建议
```

---

## 5.3 care_context.md

### 作用

`care_context.md` 保存慢病管理相关的长期上下文。

它不是具体健康记录，而是健康管理方向上的摘要。

### 示例

```md
# Care Context

## Current Management Focus

- Blood pressure monitoring.
- Diet control, especially salt reduction.
- Building regular exercise habits.

## Recent Stable Patterns

- User often asks about blood pressure records.
- User may need reminders for routine measurements.
- User appears to benefit from simple, actionable plans.

## Agent Notes

- Give conservative health advice.
- Encourage medical consultation when risk is high.
- Avoid making diagnosis-level claims.
```

---

## 6. 对外接口设计

MemorySystem 对外只暴露少量稳定接口。

推荐所有外部模块只 import：

```python
from app.memory.service import memory_service
```

不要让外部模块直接读写 `profile.md`、`preferences.md`、`care_context.md`。

---

## 6.1 load_user_memory

### 作用

加载用户记忆，并返回可以直接放入 prompt 的文本。

```python
def load_user_memory(user_id: str) -> str:
    """
    Load user memory documents and return prompt-ready memory context.
    """
```

### 返回示例

```text
[User Profile]
...

[User Preferences]
...

[Care Context]
...
```

### 使用位置

推荐在 LangGraph 工作流入口处调用：

```python
memory_context = memory_service.load_user_memory(user_id)

state = {
    "user_id": user_id,
    "user_input": user_input,
    "memory_context": memory_context,
}
```

---

## 6.2 get_task_preferences

### 作用

只加载和计划 / 提醒相关的用户偏好。

```python
def get_task_preferences(user_id: str) -> str:
    """
    Load task-related preferences for TaskManager.
    """
```

### 使用位置

TaskManager 生成计划和提醒前调用：

```python
task_preferences = memory_service.get_task_preferences(user_id)
```

例如生成计划时使用：

```python
plan = draft_plan(
    user_id=user_id,
    advice=advice,
    health_context=health_context,
    memory_context=task_preferences,
)
```

---

## 6.3 update_from_session_summary

### 作用

根据一轮对话摘要更新用户画像。

```python
def update_from_session_summary(
    user_id: str,
    session_summary: str,
) -> None:
    """
    Update memory documents from session summary.
    """
```

### 调用时机

推荐在一轮对话结束后调用：

```text
用户输入
  ↓
Agent 处理
  ↓
生成回复
  ↓
生成 session_summary
  ↓
更新 memory documents
```

---

## 6.4 add_memory_note

### 作用

业务模块主动写入一条记忆候选。

```python
def add_memory_note(
    user_id: str,
    category: str,
    note: str,
    source: str | None = None,
) -> None:
    """
    Add a memory note from business modules.
    """
```

### 使用场景

TaskManager 在用户确认计划后，可以写入：

```python
memory_service.add_memory_note(
    user_id=user_id,
    category="preferences",
    note="User accepted an after-dinner walking plan, suggesting this time slot is suitable.",
    source="task_manager",
)
```

---

## 7. 和 LangGraph 的关系

MemorySystem 不应该变成一个复杂的 LangGraph 节点链。

更推荐：

```text
1. 工作流开始前加载 memory_context
2. 把 memory_context 放入 ClinicalState
3. parser / advice / task_node 按需读取
4. 工作流结束后更新记忆
```

---

## 7.1 ClinicalState 增加字段

可以在 `ClinicalState` 中增加：

```python
class ClinicalState(TypedDict, total=False):
    user_id: str
    user_input: str

    memory_context: str
    task_preferences: str

    intent: dict
    health_context: dict
    advice: str
    response: str
```

---

## 7.2 工作流入口示例

```python
def run_workflow(user_id: str, user_input: str):
    memory_context = memory_service.load_user_memory(user_id)
    task_preferences = memory_service.get_task_preferences(user_id)

    initial_state = {
        "user_id": user_id,
        "user_input": user_input,
        "memory_context": memory_context,
        "task_preferences": task_preferences,
    }

    result = graph.invoke(initial_state)

    session_summary = build_session_summary(result)

    memory_service.update_from_session_summary(
        user_id=user_id,
        session_summary=session_summary,
    )

    return result
```

---

## 8. 和 TaskManager 的关系

TaskManager 负责：

```text
1. 计划生成
2. 计划冲突检测
3. 用户确认
4. 计划归档
5. 提醒创建
6. 调度执行
```

MemorySystem 只提供上下文。

推荐关系：

```text
TaskManager
  ↓
读取 MemorySystem 的 preferences
  ↓
生成更符合用户偏好的计划 / 提醒
  ↓
用户确认后，把长期偏好反馈给 MemorySystem
```

---

## 8.1 TaskManager 使用示例

```python
def handle_task_request(payload: TaskRequest):
    task_preferences = memory_service.get_task_preferences(payload.user_id)

    result = create_plan_or_reminder(
        payload=payload,
        task_preferences=task_preferences,
    )

    if result.user_confirmed_preference:
        memory_service.add_memory_note(
            user_id=payload.user_id,
            category="preferences",
            note=result.preference_note,
            source="task_manager",
        )

    return result
```

---

## 9. 记忆更新策略

### 9.1 可以写入记忆的信息

可以写入：

```text
长期偏好：
- 用户不喜欢早上运动
- 用户喜欢饭后散步
- 用户希望提醒简短

长期习惯：
- 用户通常早上测血压
- 用户一般晚上吃饭后有空

长期目标：
- 用户想控制血压
- 用户想减少盐摄入
- 用户想养成规律运动习惯

健康管理关注点：
- 用户主要关注血压管理
- 用户经常询问饮食控制
- 用户需要提醒辅助记录指标
```

---

### 9.2 不应该写入记忆的信息

不写入：

```text
一次性提醒：
- 明天 8 点提醒我测血压

一次性健康数据：
- 今天血压 145/92

临时情绪：
- 今天很烦
- 今天不想运动

不确定推测：
- 用户可能有高血压
- 用户好像不喜欢运动

具体计划实例：
- 2026-05-07 创建的运动计划
```

这些应该进入对应业务模块，而不是 MemorySystem。

---

## 10. Session Summary 设计

对话结束后，可以生成一个简单摘要。

### 示例

```text
User said they usually have time to exercise after dinner and prefer simple reminders.
The assistant suggested a walking plan and the user accepted the after-dinner schedule.
No confirmed medical diagnosis was added.
```

然后从摘要中提取候选记忆：

```text
Candidate 1:
category = preferences
content = User prefers exercising after dinner.

Candidate 2:
category = preferences
content = User prefers simple reminders.
```

---

## 11. Memory Policy 设计

`policy.py` 负责判断哪些候选可以写入。

### 简单规则

```python
ALLOW_KEYWORDS = [
    "usually",
    "generally",
    "prefer",
    "does not like",
    "often",
    "long-term goal",
    "habit",
]

DENY_KEYWORDS = [
    "today",
    "tomorrow",
    "this morning",
    "this evening",
    "blood pressure reading",
    "glucose reading",
    "remind me at",
]
```

中文可以对应：

```python
ALLOW_KEYWORDS_ZH = [
    "一般",
    "通常",
    "习惯",
    "不喜欢",
    "喜欢",
    "以后",
    "长期",
    "目标",
]

DENY_KEYWORDS_ZH = [
    "今天",
    "明天",
    "今晚",
    "这次",
    "提醒我",
    "血压是",
    "血糖是",
]
```

---

## 12. Prompt 使用方式

在 Advice Node 中：

```text
你是慢性病健康管理助手。

以下是用户长期上下文：

{memory_context}

以下是本轮健康上下文：

{health_context}

请生成安全、保守、可执行的健康建议。
```

在 TaskManager 中：

```text
你正在为用户生成计划或提醒。

以下是用户偏好：

{task_preferences}

请避免安排用户不喜欢的时间段。
请优先选择用户更容易执行的计划形式。
```

---

## 13. 第一版最小实现

第一版可以只实现 4 个文件：

```text
app/memory/
├── service.py
├── store.py
├── updater.py
└── schemas.py
```

### service.py

负责对外接口：

```text
- load_user_memory
- get_task_preferences
- update_from_session_summary
- add_memory_note
```

### store.py

负责文件读写：

```text
- read_profile
- read_preferences
- read_care_context
- write_profile
- write_preferences
- write_care_context
```

### updater.py

负责根据摘要更新文档：

```text
- extract_memory_candidates
- filter_candidates
- merge_into_documents
```

### schemas.py

定义数据结构：

```text
- MemoryContext
- MemoryCandidate
- MemoryUpdateResult
```

---

## 14. 后续可扩展方向

当前不做长期记忆检索，但以后可以扩展：

```text
1. 从 Markdown 切换到 SQLite
2. 增加记忆版本历史
3. 增加人工审核机制
4. 增加向量检索
5. 增加记忆置信度
6. 增加 memory diff 记录
7. 增加多用户隔离
```

但第一版不建议做这些。

---

## 15. 总结

本项目的 MemorySystem 应该是一个**轻量用户画像系统**，而不是完整长期记忆检索系统。

核心方案：

```text
1. 使用 profile.md 保存用户画像
2. 使用 preferences.md 保存用户偏好
3. 使用 care_context.md 保存慢病管理背景
4. 每次对话开始加载这些文档进上下文
5. 每次对话结束根据摘要按需更新
6. TaskManager 可以读取 preferences.md 辅助生成计划和提醒
7. 具体健康记录、计划、提醒仍然进入业务数据库
```

一句话：

```text
MemorySystem 管用户长期上下文，TaskManager 管具体任务，Health Database 管健康数据。
```
