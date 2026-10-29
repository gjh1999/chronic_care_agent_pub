# 1.0 版本代码审阅报告

审阅日期：2026-05-01

本报告基于当前仓库代码进行静态审阅，并执行了基础验证命令：

- `.venv\Scripts\python.exe -m compileall app tests -q`
- `.venv\Scripts\python.exe -m pytest -q`

## 总体结论

当前代码可以通过 Python 语法编译检查，但测试无法稳定运行，主要原因是测试直接依赖真实 LLM/RAG 外部服务和环境变量。

从应用行为看，优先级最高的问题集中在 FastAPI 入口缺失、用户确认逻辑失效、计划归档后无条件创建提醒，以及测试缺少 mock 隔离。

## 问题清单

### 1. FastAPI 应用入口为空

位置：

- `app/main.py`
- `app/api/routes.py`

现象：

`app/main.py` 当前为空文件。虽然 `app/api/routes.py` 中定义了 `router`，但项目没有创建 `FastAPI()` 实例，也没有将路由挂载到应用上。

影响：

使用常见启动方式时，例如：

```powershell
uvicorn app.main:app --reload
```

会因为 `app` 对象不存在而无法启动服务。

建议：

在 `app/main.py` 中创建 FastAPI 实例，并 include API router。

### 2. 用户确认逻辑失效，且默认自动确认

位置：

- `app/api/routes.py`
- `app/graph/workflow.py`
- `app/nodes/user_confirm_node.py`

现象：

`app/api/routes.py` 中先调用 `run_workflow()`，之后才把 `request.user_confirmed` 写入 `result`。但此时工作流已经执行结束，该字段不会影响路由判断。

同时，`user_confirm_node` 会直接执行：

```python
state["user_confirmed"] = True
```

这意味着用户没有确认，甚至明确拒绝时，流程仍可能被当作确认处理。

影响：

计划可能被自动归档，违背用户意愿。对于健康管理场景，这是较高风险的行为问题。

建议：

让 `run_workflow()` 接收 `user_confirmed` 参数，并在 initial state 中传入；`user_confirm_node` 应读取已有 state，而不是强制写成 True。

### 3. 计划归档后会无条件进入提醒流程

位置：

- `app/graph/builder.py`
- `app/graph/routing.py`

现象：

`builder.py` 中存在如下边：

```python
graph.add_edge(NODE_PLAN_ARCHIVE, NODE_REMINDER_ROUTER)
```

这会导致计划归档后总是进入提醒路由。

`routing.py` 中已有 `route_after_plan_archive()`，可以根据 `need_reminder` 判断是否需要提醒，但当前没有接入图。

影响：

用户只要求生成健康计划时，也可能被创建计划提醒。

建议：

将 `NODE_PLAN_ARCHIVE` 后的无条件边改为条件边，使用 `route_after_plan_archive()` 判断下一步是提醒流程还是响应结束。

### 4. 测试直接依赖真实外部服务

位置：

- `tests/test_workflow_basic.py`
- `tests/test_rag_integration.py`
- `app/core/llm/client.py`
- `app/services/rag_service.py`

现象：

执行：

```powershell
.venv\Scripts\python.exe -m pytest -q
```

结果为：

```text
6 failed
```

主要失败原因：

- workflow 测试会真实调用 LLM Chat Completions API。
- RAG 测试会初始化真实 embedding/reranker，并要求 `DASHSCOPE_API_KEY`。
- 当前环境网络受限时会出现 `openai.APIConnectionError`。
- 未配置 `DASHSCOPE_API_KEY` 时会出现 `ValueError: 请设置 DASHSCOPE_API_KEY 环境变量，或传入 api_key`。

影响：

测试不能作为本地回归验证工具使用，也不适合 CI。任何没有外部凭证或网络权限的环境都会失败。

建议：

将基础 workflow 测试改为 mock LLM 输出和 mock RAG 输出；真实外部服务测试单独标记为 integration，并在缺少环境变量时 skip。

### 5. requirements.txt 缺少 pydantic-settings

位置：

- `app/config/settings.py`
- `requirements.txt`

现象：

`settings.py` 使用：

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
```

但 `requirements.txt` 中没有声明 `pydantic-settings`。

影响：

在干净环境安装依赖后，应用可能因为缺包而导入失败。

建议：

在 `requirements.txt` 中补充固定版本的 `pydantic-settings`，并清理重复依赖项。

### 6. .gitignore 是目录，不是文件

位置：

- `.gitignore`

现象：

当前 `.gitignore` 在文件系统中表现为目录。执行 Git 状态检查时出现：

```text
warning: unable to access '.gitignore': Permission denied
```

同时仓库中存在大量应被忽略的运行产物：

- `__pycache__/`
- `.pytest_cache/`
- `data/sqlite/chronic_care.db`
- `data/rag_index/`
- `data/cache/`

影响：

Git 忽略规则无法正常生效，运行产物、缓存、数据库和索引文件容易进入版本管理。

建议：

将 `.gitignore` 修正为普通文件，并加入 Python、虚拟环境、缓存、数据库和 RAG 索引相关忽略规则。

### 7. 中文文本存在编码损坏

位置：

- 多个源码文件和测试文件

现象：

大量中文注释、prompt、响应文本出现 mojibake，例如：

```text
鍋ュ悍绠＄悊璁″垝
鎻愰啋
```

影响：

这不只是显示问题。prompt、用户响应、测试输入如果已经被错误编码保存，会直接影响 LLM 理解和最终用户体验。

建议：

确认原始编码来源，统一以 UTF-8 保存源码文件。对 prompt、响应文案和测试样例做一次集中修复。

## 建议修复顺序

1. 补齐 `app/main.py`，保证服务可以启动。
2. 修复 `user_confirmed` 传递链路，去掉默认自动确认。
3. 修复计划归档后的提醒路由，避免无条件创建提醒。
4. 为 workflow 测试增加 LLM/RAG mock，使基础测试离线可跑。
5. 补齐 `requirements.txt` 中缺失依赖。
6. 修正 `.gitignore`，清理缓存和运行产物。
7. 统一修复中文编码问题。

## 当前验证结果

语法编译：

```text
通过
```

测试：

```text
6 failed
```

失败原因不是单一断言错误，而是测试设计依赖真实外部服务、缺少环境变量和网络权限。
