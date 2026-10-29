# 慢性病管理 Agent

当前版本把原 LangGraph PoC 外围改造成可测试的 FastAPI 服务，保留规则、RAG 和工作流核心。

## 一键启动（Windows）

双击或命令行运行根目录 `start_all.bat`，脚本会依次：

1. 启动 RAG（`PycharmProjects\RAG`，8010）并等待 `/healthz` 就绪（最长 5 分钟）。
2. 启动意图服务（`PycharmProjects\Medical_Lora`，8020）并等待 `/healthz` 就绪（最长 10 分钟，7B 模型加载较慢）。
3. 若 `.env` 不存在则自动复制 `.env.example`，执行 `init_db`，启动本项目（8000）并等待 `/readyz` 就绪。
4. 启动前端 H5（`miniprogram/`，5173）：首次运行自动 `npm install`；若 5173 被占用会告警并检查 5174。

四个服务各自运行在独立命令行窗口，启动完成后访问 `http://127.0.0.1:8000/dependencies` 确认两项外部依赖均为 `up`，浏览器打开 `http://localhost:5173/` 使用前端（登录页输入不同昵称模拟不同测试账号）。脚本内服务目录与 venv 路径为当前机器硬编码，换机器需修改 `RAG_DIR` / `INTENT_DIR`。已监听对应端口的服务会自动跳过启动；重复运行前建议先双击 `stop_all.bat` 停掉旧进程再 `start_all.bat`。若脚本双击异常，按 [`docs/手动启动命令.md`](docs/手动启动命令.md) 逐窗口手动启动。

小程序端另需 `cd miniprogram && npm run build:mp-weixin` 构建后导入微信开发者工具（`dist/build/mp-weixin`），真机登录需在 `.env` 配置 `WX_APPID` / `WX_SECRET`。

## 本地三服务启动（手动）

1. 在 `C:\Users\gjh\PycharmProjects\RAG` 启动 RAG：`uvicorn service_app:app --host 127.0.0.1 --port 8010`，确认 `/readyz` 返回 200。
2. 在 `C:\Users\gjh\PycharmProjects\Medical_Lora` 启动意图服务，确认 `http://127.0.0.1:8020/healthz` 返回 200。
3. 本项目复制 `.env.example` 为 `.env`，安装依赖并执行 `python scripts/init_db.py`。
4. 启动本项目：`uvicorn app.main:app --reload --port 8000`。
5. 访问 `http://127.0.0.1:8000/dependencies` 确认外部服务连通，再通过 `http://127.0.0.1:8000/docs` 测试接口。

`/dependencies` 只执行外部服务健康端点的连通性检查，不代表一次真实检索已经成功。Docker Compose 默认通过 `http://host.docker.internal:8010` 访问运行在 Windows 宿主机上的 RAG；生产环境应通过内部 DNS 配置 `RAG_DOCKER_BASE_URL`。

开发登录使用 `POST /api/v1/auth/wechat-login`，请求体例如 `{"code":"dev-alice"}`。生产环境必须关闭 `ALLOW_DEV_LOGIN`，配置微信凭证、PostgreSQL、Redis 和高强度 JWT 密钥。

## 生产部署（阿里云）

完整方案见 [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)：本项目用 Docker Compose 拉起（postgres/redis/migrate/api/worker），RAG 与意图服务以 systemd 部署在宿主机（意图服务需 GPU ≥8GB 显存），Nginx 反代 HTTPS。微信小程序正式版要求域名已完成 ICP 备案。

## 数据库与 worker

- `alembic upgrade head`：初始化或升级新版数据库结构。
- `python scripts/run_reminder_worker.py`：运行提醒 outbox worker。站内提醒可直接投递，微信通道在模板与用户授权配置完成前会重试并最终标记失败。

## 测试

`pytest -q`

普通自动化测试不应调用真实 LLM。真实模型联调必须使用显式开关、独立测试密钥和虚构数据。
