# 修改日志

> 约定:每次代码修改必须在本文件追加记录,包含日期、类型、背景、改动文件、验证结果与遗留问题。
> 最新条目在顶部。

---

## 2026-10-29 修复 H5 网页文字无法选中复制

**类型**:缺陷修复

**背景**:用户反馈网页上无法选中、复制文字。排查发现项目代码无任何 `user-select` 设置,根因是 **uni-app H5 运行时默认样式**:编译产物中自带 `html, body { -webkit-user-select: none; user-select: none; ... }`(模拟原生 App 不可长按选中的手感),`user-select` 可继承,导致整页文字不可选。

**改动文件**:

| 文件 | 改动 |
|------|------|
| `miniprogram/src/App.vue` | 全局样式追加 `body, uni-page-body { -webkit-user-select: text; user-select: text; }` 覆盖框架默认值 |

**验证**:`npm run build:h5` 构建通过,编译产物中覆盖规则位于默认 `none` 规则之后(同特异性下后者生效),且 `uni-page-body` 显式设为 `text` 后子孙节点全部可选中。刷新页面即可复制。

---

## 2026-10-29 修复计划草稿为空 + 输出纯文本化 + 新增 SSE 流式输出与速度优化

**类型**:缺陷修复 + 新功能 + 性能优化

**背景**:用户提出四个问题:(1) 请求生成健康计划时计划草稿卡片为空;(2) 响应速度慢(全链路 2-3 分钟);(3) 回复里满是 `**`、`#` 等 Markdown 符号;(4) 要求流式输出。

**问题定位与修复**:

1. **计划草稿为空**:LLM 生成的计划项是 `{task, time}` 结构,而前端确认卡片读取 `{content, schedule_rule}` —— 后端落库时直接透传导致 `content` 为空。修复:统一归一化(`_normalize_plan_item` 兼容两种结构)。
2. **Markdown 符号**:提示词要求不用 Markdown 后模型仍偶尔输出,服务端加兜底 `strip_markdown` 强制清理;前端另加 `mdToText` 显示层清理。
3. **速度**:建议 LLM 限 `max_tokens=800` + 提示词要求 300 字以内;计划 LLM 限 `max_tokens=700`。
4. **流式输出**:新增 SSE 端点 `POST /api/v1/conversations/{id}/messages/stream`,节点通过 contextvar 队列推送 `status`(阶段进度)与 `token`(逐字回复)事件,20s 心跳保活;前端 H5 用 fetch + ReadableStream 逐字渲染,小程序端自动回退普通请求。
5. **排查中发现**:`RequestContextMiddleware` 原为 `BaseHTTPMiddleware`,会用内存流包装响应体、破坏 SSE 流式(最小复现确认),已改为纯 ASGI 中间件(直接包装 send,不触碰响应体;`request.state.request_id` 通过 `scope["state"]` 注入,Starlette 0.37 原生支持)。

**改动文件**:

| 文件 | 改动 |
|------|------|
| `app/service/conversation_service.py` | 拆出 `_persist_user_message`/`finalize_response` 供同步与流式共用;新增 `_plan_items`/`_normalize_plan_item` 统一计划项结构 |
| `app/service/plan_service.py` | `create_draft` 兼容 `{task,time}` 与 `{content,schedule_rule}` 两种计划项结构 |
| `app/nodes/parser_node.py` | 意图识别前推送状态事件 |
| `app/nodes/rag_node.py` | 检索前推送状态事件 |
| `app/nodes/advice_node.py` | 推送状态事件;流式请求下逐字推送回复;`max_tokens=800` + 提示词要求 300 字内且不用 Markdown;输出后 `strip_markdown` 兜底 |
| `app/nodes/plan_draft_node.py` | 推送状态事件;`max_tokens=700`;任务名清理 Markdown |
| `app/core/llm/client.py` | `invoke` 支持 `max_tokens`;新增 `invoke_stream`(逐字回调) |
| `app/core/llm/prompts.py` | PLAN_PROMPT 要求任务名纯文本 |
| `app/service/stream.py` | **新增**。contextvar 事件队列,`emit_status`/`emit_token` 无队列时为空操作(不影响测试),`run_workflow_streamed` 后台线程执行工作流 |
| `app/controller/v1/conversation.py` | **新增** SSE 端点(StreamingResponse,独立 SessionLocal 落库,与普通接口同一套持久化) |
| `app/middlewares/request_context.py` | 重写为纯 ASGI 中间件(修复流式缓冲) |
| `app/utils/text.py` | **新增** `strip_markdown` |
| `miniprogram/src/utils/md.js` | **新增** 前端 `mdToText` |
| `miniprogram/src/api/chat.js` | 新增 `sendMessageStream`(仅 H5,fetch + ReadableStream 解析 SSE) |
| `miniprogram/src/pages/index/index.vue` | H5 走流式发送(状态文案更新 + 逐字气泡),其余平台回退普通请求;气泡渲染 `mdToText` |
| `miniprogram/src/components/plan-confirm-card/plan-confirm-card.vue` | 计划项渲染 `mdToText` |
| `miniprogram/src/utils/request.js` | 导出 `BASE_URL` |

**验证**:pytest 36 通过;实测 SSE 全链路(登录→会话→流式发送「制定控压计划」):状态事件 0.0s 即达、逐字 token 实时推送、总耗时 ~25s、`final_response` 与计划项均无 Markdown 符号、计划项结构正确且 `status=waiting_confirmation` 带 interrupt_id/revision;Node fetch + ReadableStream(浏览器同款解析逻辑)验证通过;H5 `npm run build:h5` 构建通过。浏览器界面交互未自动化点击验证,建议在 http://localhost:5173/ 实际发一条消息确认。

**遗留**:意图服务(Medical_Lora)单次解析仍需 ~15-20s,是当前最长耗时环节,流式状态文案已覆盖等待体验;SSE 前端仅 H5 支持,小程序端仍为普通请求。

---

## 2026-10-29 修复 start_all.bat 双击闪退 + 启动脚本健壮性加固

**类型**:缺陷修复(高严重度)+ 工具/脚本增强

**背景**:用户双击 `start_all.bat` 后窗口一闪即退。逐项排查定位到三个独立问题:

1. **闪退根因**:脚本以 LF 换行 + UTF-8(带 BOM)编码写入,cmd.exe 对 LF 批处理的行标签(`:wait_health`/`call`)解析不可靠,且 BOM 会黏在首行导致 `@echo off` 失效(实测报 `'@echo' 不是内部或外部命令`);
2. **wait_health 不可靠**:`curl && (echo ... & exit /b 0)` 把 `exit /b` 写进 `&&` 括号块内,实测在 for 循环中无法正常退出,健康检查会空转 150 轮;
3. **块内 echo 含 ASCII 括号导致解析崩溃**:`if/else` 括号块内的 echo 文本若含英文括号(如 `(可能需要几分钟)`),嵌套层直接报「此时不应有 …。」终止脚本,外层则吞掉括号。

**改动文件**:

| 文件 | 改动 |
|------|------|
| `start_all.bat` | 编码改为 **GBK + CRLF**(去掉 BOM 与 chcp,中文 Windows 原生兼容);`wait_health` 改为 `curl → if not errorlevel 1 goto :ready` 标准写法;块内 echo 的括号全部改全角;新增**端口已在监听则跳过启动**逻辑(避免重复弹窗报错),后端未运行时才执行 init_db |
| `stop_all.bat` | 同样转为 GBK + CRLF 编码 |

**验证**:实测(本机 CLI 环境)前三步完整通过:端口检测 → 「已在运行,跳过启动」→ 健康检查「已就绪」,中文输出正常无乱码;第 4 步解析错误以最小复现脚本二分定位并修复(同结构修复版验证通过),完整双击实测建议用户下次冷启动时用 `stop_all.bat` → `start_all.bat` 顺序确认。

**遗留**:测试中发现本机 CLI 会话中由 bash 拉起 cmd 时存在间歇性「系统找不到指定的路径」环境故障(全路径调用 System32 的 netstat/ping 亦失败,bash 直接调用正常),与脚本无关,不影响资源管理器双击场景。

---

## 2026-10-29 新增手动启动命令文档

**类型**:文档

**背景**:`start_all.bat` 双击闪退问题在用户机器上复现但未定位(本机 CLI 环境无法完全还原双击场景),用户选择改用手动命令启动。

**改动文件**:

| 文件 | 改动 |
|------|------|
| `docs/手动启动命令.md` | **新增**。4 个服务的逐窗口启动命令(RAG 8010 / 意图 8020 / 后端 8000 / 前端 5173)、验证地址表、停止方法与常见问题 |
| `README.md` | 一键启动章节补充指向该文档 |
| `docs/CHANGELOG.md` | 本条记录 |

**遗留**:`start_all.bat` 双击闪退的根因仍需在用户机器上排查(候选方向:运行环境差异、安全软件拦截)。

---

## 2026-10-29 一键启动脚本升级为 4 服务 + 新增一键停止

**类型**:工具/脚本

**背景**:用户要求一键拉起全部服务(原先 `start_all.bat` 只拉起 RAG/意图/本项目三个后端,前端 H5 需手动启动)。

**改动文件**:

| 文件 | 改动 |
|------|------|
| `start_all.bat` | 新增第 4 步:启动前端 H5(`miniprogram/` 目录,`npm run dev:h5`);首次运行自动 `npm install`;5173 被占用时告警并回退检查 5174;最终提示输出前端地址与测试账号说明 |
| `stop_all.bat` | 新增:按端口(8000/8010/8020/5173/5174)查找 LISTENING 进程并 taskkill,一键停全部服务 |
| `README.md` | 一键启动章节更新为 4 服务;补充小程序构建与真机登录前提 |
| `docs/CHANGELOG.md` | 本条记录 |

**验证**:端口检测命令(`netstat -ano | findstr /R /C:":5173 .*LISTENING"`)在 cmd 语义下实测命中/未命中均正确(注意 git-bash 下需 MSYS_NO_PATHCONV,与本脚本无关);其余步骤沿用既有已验证的 wait_health 逻辑。未做完整双击实测(避免与当前已运行服务端口冲突),下次冷启动时验证。

**遗留**:前端 dev server 若因旧进程占端口漂移到 5174,`stop_all.bat` 已覆盖 5174;更多漂移端口(5175+)未覆盖。

---

## 2026-10-29 对话延迟优化:关闭 LLM 思考模式

**类型**:性能优化

**背景**:用户反馈对话反应慢。实测分解:端到端 79.9s = 意图服务(本地 7B,15-20s)+ RAG 检索(3.9s)+ LLM 生成(dashscope qwen3.6-plus 开启 thinking,单次 31s,reasoning 1682 tokens 而正文仅 87 tokens)+ 工作流开销。最大头是 LLM 思考模式(工作流内多次调用)。

**改动文件**:

| 文件 | 改动 |
|------|------|
| `.env` | `LLM_ENABLE_THINKING=true` → `false` |
| `docs/CHANGELOG.md` | 本条记录 |

**验证**:重启主服务后实测——记录类端到端 79.9s → **20.9s**,咨询类 79.9s → **37.8s**(均含意图服务 15-20s 固定开销),回复质量与内容结构无退化(咨询建议仍引用指南与 RAG 证据)。

**遗留**:意图服务本地 7B 推理 15-20s 为当前最大剩余瓶颈,属本机硬件限制(生产 GPU 实例会显著更快);意图+RAG 可并行化需改工作流图结构,未实施。意图服务 `MAX_NEW_TOKENS` 曾试 128/384 均导致 JSON 截断(128)或无明显收益(384),保持默认 512。

---

## 2026-10-29 H5 登录页支持多测试账号(昵称即身份)

**类型**:功能增强

**背景**:用户问「网页版没有注册选项,怎么区分不同人」。产品形态为微信小程序,正式身份即微信 openid(登录即注册,无需注册页);但 H5 开发预览此前固定 `dev-alice`,所有人同一账号,无法演示多用户与数据隔离。

**改动文件**:

| 文件 | 改动 |
|------|------|
| `miniprogram/src/pages/login/login.vue` | H5 分支新增昵称输入框(默认 `dev-alice`,可用 `VITE_DEV_LOGIN_CODE` 改默认值):登录时 code = `dev-<昵称>`,昵称存入 localStorage(`dev_nickname`)下次自动带出;不同昵称 → 不同 openid(后端 sha256 确定性映射)→ 不同账号;小程序分支不受影响(条件编译) |
| `miniprogram/dist/build/mp-weixin/` | 重新构建(同步登录页改动) |
| `docs/CHANGELOG.md` | 本条记录 |

**验证**:Edge headless + CDP 实测:「测试甲」登录 user_id=`f3f64f0f-…`,`测试乙`登录 user_id=`02a4d063-…`,两账号 token 与 user_id 均不同,隔离生效;同昵称重复登录命中同一 openid(后端确定性哈希,天然幂等)。

**遗留**:无。

---

## 2026-10-29 miniprogram 前端:补齐小程序平台依赖并构建

**类型**:配置/构建

**背景**:用户要求在微信中测试小程序。miniprogram/(最新前端,README 标注已对接真实后端,DEPLOYMENT.md 的 H5 构建源)缺 `@dcloudio/uni-mp-weixin` 平台包,无法执行 `build:mp-weixin`。

**改动文件**:

| 文件 | 改动 |
|------|------|
| `miniprogram/package.json` | 新增依赖 `@dcloudio/uni-mp-weixin: 3.0.0-alpha-5030320261021002`(与该目录其他 @dcloudio 包同版本) |
| `miniprogram/package-lock.json` | npm install 同步 |
| `miniprogram/src/pages/login/login.vue` | H5 分支 dev 模拟码由「随机生成(每次登录新用户)」改为固定 `import.meta.env.VITE_DEV_LOGIN_CODE || 'dev-alice'`,保证 H5 开发登录用户身份稳定 |
| `docs/CHANGELOG.md` | 本条记录 |

**验证**:`npm run build:mp-weixin` 成功,产物 `miniprogram/dist/build/mp-weixin/`(app.json/pages/components 齐全);H5 dev server 起在 5173,Edge headless + CDP 实测:点击「微信一键登录」→ hash 跳 `#/pages/index/index`,localStorage 写入 `token`/`user_id`,首页渲染快捷入口(测血糖/测血压/生成计划/设提醒)与 tabBar。

**遗留**:小程序端登录需后端配置微信凭证(见下条遗留);微信开发者工具导入 `dist/build/mp-weixin` 时需填 AppID 并勾选「不校验合法域名」。

---

## 2026-10-29 修复 H5 微信一键登录无反应

**类型**:缺陷修复

**背景**:前端 H5 登录页点击「微信一键登录」无任何反应。原因:`uni.login({ provider: 'weixin' })` 是小程序 API,H5 平台不支持(H5 微信登录需网页 OAuth 跳转),Promise 被 reject 且无 catch,失败静默。后端已支持开发登录(`allow_dev_login` 开启时,`dev-` 前缀 code 直接映射 openid),但前端从未走这条路。

**改动文件**:

| 文件 | 改动 |
|------|------|
| `frontend/src/pages/login/login.vue` | 登录函数加 try/catch 与失败 toast;用条件编译:`#ifdef H5` 直接使用 `import.meta.env.VITE_DEV_LOGIN_CODE || 'dev-alice'` 调用后端开发登录,`#ifndef H5` 保留原 `uni.login` 小程序流程 |
| `docs/CHANGELOG.md` | 本条记录 |

**验证**:编译产物确认 H5 分支保留、小程序分支剔除;Edge headless + CDP 实测:点击按钮后 hash 跳转 `#/pages/index/index`、localStorage 写入 `access_token`、首页渲染聊天界面与 tabBar。后端接口 `POST /api/v1/auth/wechat-login {"code":"dev-alice"}` 实测返回 token。

**遗留**:H5 生产环境微信登录需接入微信开放平台网页 OAuth(当前只有小程序 code 兑换链路),上线前必须补;小程序端 `uni.login` 流程未实机验证。

---

## 2026-10-29 修复前端 H5 白屏(缺 @dcloudio/uni-h5 依赖)

**类型**:缺陷修复

**背景**:启动前端 `npm run dev:h5` 后访问 http://localhost:5173/ 白屏。排查发现:uni CLI(`vite-plugin-uni` 的 `resolvePlugins`)只扫描项目 `package.json` 中声明的依赖来决定加载哪些平台插件;`@dcloudio/uni-h5` 不在依赖列表中,导致其代理加载的 `uni-h5-vite` 平台插件(含 `uni:h5-main-js`,负责把 main.js 转换为 `createApp().app.use(__plugin).mount("#app")` 的挂载代码)从未注册,Vue 应用不挂载、`#app` 恒为空。`@dcloudio/uni-h5` 仅作为传递依赖存在于 node_modules,故无缺包报错。

**改动文件**:

| 文件 | 改动 |
|------|------|
| `frontend/package.json` | dependencies 增加 `@dcloudio/uni-h5: 3.0.0-4020920240930001`(与其他 @dcloudio 包同版本) |
| `frontend/package-lock.json` | npm install 同步(uni-h5 由传递依赖转直接依赖) |
| `docs/CHANGELOG.md` | 本条记录 |

**验证**:重启 dev server 后,`/src/main.js` 响应已含 `import "/src/pages-json-js"`、`@dcloudio/uni-h5` 插件引入与 `createApp().app.use(__plugin).mount("#app")`;Edge headless 渲染页面标题为「登录」,DOM 含 uni-input×21、uni-button×49,截图字节数由 4.7KB(空白)增至 22.9KB(有内容)。

**遗留**:`dev:mp-weixin` / `build:mp-weixin` 脚本对应平台包 `@dcloudio/uni-mp-weixin` 同样不在 package.json 中(node_modules 中也没有),小程序构建前需补齐;本次未涉及。

---

## 2026-10-29 修复 init_db 直接执行时找不到 app 模块

**类型**:缺陷修复

**背景**:启动项目时发现 `python scripts/init_db.py` 直接运行报 `ModuleNotFoundError: No module named 'app'`。原因:Python 执行脚本时 sys.path[0] 为脚本所在目录(scripts/),项目根目录不在其中,`from app.database.connection import init_db` 导入失败。此前手动执行需 `PYTHONPATH=.` 绕过,`start_all.bat` 一键启动同样会踩中。

**改动文件**:

| 文件 | 改动 |
|------|------|
| `scripts/init_db.py` | 顶部插入项目根目录(`Path(__file__).resolve().parent.parent`)到 `sys.path`,随后原有导入不变 |

**验证**:不设 PYTHONPATH 直接执行 `python scripts/init_db.py`,输出「数据库结构初始化完成」;随后 `uvicorn app.main:app` 正常启动,`/dependencies` 返回 `intent_service: up`、`external_rag: up`。

**遗留**:`scripts/run_reminder_worker.py` 若同样直接运行导入 app 包,可能需同样处理(本次未涉及,未改动)。

---

## 2026-10-25 部署文档补充前端托管(前后端同端口)

**类型**:文档

**背景**:用户询问"前后端统一端口"技术。该方案即 Nginx 反向代理按路径分流:443 端口同时承载 H5 静态文件与 API(前端 baseURL 为 `/api/v1`,`location /api/` 转发后端 8000,`location /` 读 `/var/www/h5` 构建产物)。

**改动文件**:

| 文件 | 改动 |
|------|------|
| `docs/DEPLOYMENT.md` | 架构图更新为 H5/小程序 → Nginx 按路径分流;新增 3.5 节「前端 H5 构建与上传」(uni-app `build:h5` 产物 scp 到 `/var/www/h5`);3.6 节 Nginx 配置改为前后端同端口(保留原 300s 超时);3.7 验证清单增加 H5 页面与 SPA 回退检查 |

**验证**:未实跑;Nginx 配置基于前端实际代码(`frontend/src/utils/request.js` baseURL `/api/v1` 前缀)编写,`proxy_pass` 不带路径以原样转发。

**遗留**:无。

---

## 2026-10-25 部署文档补充单机全量方案

**类型**:文档

**背景**:用户询问三个项目能否整体部署在一台服务器。确认 Medical_Lora 为 4bit 量化加载(`load_in_4bit=True`)后,给出单机 GPU 实例的资源估算与选型,并调整文档以单机为默认场景。

**改动文件**:

| 文件 | 改动 |
|------|------|
| `docs/DEPLOYMENT.md` | 新增 1.1 节「单机部署(起步推荐)」:资源表(显存 ≥8GB 推荐 16GB、内存推荐 32GB)、gn7i 选型、单机/多机优劣;3.4 节意图服务默认改监听 `127.0.0.1`(跨机时改 `0.0.0.0` + 内网限制);前置条件表更新实例规格说明 |

**验证**:资源估算基于 4bit 量化配置与 FAISS 索引体量(远程历史中索引文件约 8MB);未实跑。

**遗留**:8GB 显存为理论下限,峰值推理可能 OOM,正式购买前建议按量付费 16GB 实例实测冷启动与并发推理显存占用。

---

## 2026-10-25 修复远程仓库历史被误回退

**类型**:缺陷修复(git 仓库)

**背景**:远程 GitHub main 被 force push 回退到 4 月旧历史(1ab601f),与本地历史无共同祖先,PyCharm push 报 non-fast-forward、merge 报 unrelated histories。远程旧历史中曾提交 `.env`(含 DASHSCOPE_API_KEY/LLM_API_KEY)。

**改动文件**:

| 文件 | 改动 |
|------|------|
| `.gitignore` | 新增忽略 `data/memory/`(用户健康数据)、`.claude/settings.local.json` |
| 仓库历史 | 本地最新历史(e3cf594)force push 覆盖远程旧历史;远程旧历史保留在本地 `backup-remote-old` 分支 |
| `docs/CHANGELOG.md` | 本条记录 |

**验证**:`git push --force origin main` 成功(1ab601f → e3cf594);`git status` 干净;本地与 origin/main 均指向 e3cf594;`.env`、`.venv`、`node_modules`、`*.db`、`data/memory/` 均未被纳入提交。

**遗留**:远程旧历史泄漏的 DashScope 密钥建议立即到控制台轮换(force push 后旧提交对象仍可能通过 SHA 在 GitHub 访问);确认无需旧历史后可删除 `backup-remote-old` 分支。

---

## 2026-10-25 阿里云生产部署方案

**类型**:文档 + 部署配置修复

**背景**:用户计划部署到阿里云服务器。梳理生产链路后发现 docker-compose 存在两个缺口:未传 `INTENT_BASE_URL`(容器内默认 `127.0.0.1:8020` 指向容器自身,意图调用必失败);`host.docker.internal` 在 Linux 下默认不可解析。同时所有常驻服务缺少重启策略。

**改动文件**:

| 文件 | 改动 |
|------|------|
| `docs/DEPLOYMENT.md` | **新增**。阿里云部署全案:架构总览(小程序→Nginx→api→DashScope/意图/RAG)、前置条件(ICP 备案、SSL、GPU ≥8GB、安全组)、分步部署(本项目 compose、RAG 与意图服务 systemd 单元、Nginx HTTPS 示例含 300s 超时)、上线验证清单、运维(备份 cron、日志、更新、安全基线) |
| `docker-compose.yml` | `app_env` 增加 `INTENT_BASE_URL`(默认 `http://host.docker.internal:8020`);`api` 增加 `extra_hosts: host.docker.internal:host-gateway`(Linux 兼容);postgres/redis/api/worker 增加 `restart: unless-stopped` |
| `README.md` | 新增「生产部署(阿里云)」章节,引用部署文档 |

**验证**:compose 语法未实跑(需 Linux + Docker 环境);配置项与 `app/config/settings.py` prod 校验(JWT ≥32、REDIS、关闭开发登录)一致。

**遗留**:RAG 与 Medical_Lora 项目自身无 Dockerfile,部署采用宿主机 venv + systemd(文档方案);若后续要容器化需在各自仓库补充。GPU 实例选型与备案周期需用户提前准备。

---

## 2026-10-25 新增一键启动脚本

**类型**:新功能(开发工具)

**背景**:三服务启动依赖手动依次执行,README 仅记录命令。新增 `start_all.bat` 一键拉起 RAG(8010)、意图服务(8020)、本项目(8000),每个服务独立窗口运行并轮询健康检查。

**改动文件**:

| 文件 | 改动 |
|------|------|
| `start_all.bat` | **新增**。依次启动 RAG、Medical_Lora(各自 `.venv` 的 python -m uvicorn)、本项目(自动复制 `.env.example`、执行 `init_db`、`--reload`);用 `curl -sf` 轮询 `/healthz`、`/readyz`(RAG 5 分钟、意图服务 10 分钟、本项目 2 分钟),任一失败即中止 |
| `README.md` | 新增「一键启动(Windows)」小节,原启动步骤改名为「本地三服务启动(手动)」 |

**验证**:未实跑(需要真实拉起 7B 模型);bat 语法与 README 记录的命令一致,健康端点与 docker-compose healthcheck、`docs/EXTERNAL_SERVICES.md` 契约一致。

**遗留**:脚本内 `RAG_DIR`/`INTENT_DIR` 为当前机器硬编码,换机器需修改;未提供 bash 版(`.sh`)。

---

## 2026-10-24 前端对接真实后端(8 页全量联调)

**类型**:新功能(前后端联调)

**背景**:用户评审测试界面后确认"开始和后端连接起来",删除 mock 层,将 8 个页面全部切换为真实 API 调用,并完成三服务(后端 :8000 + 意图 LoRA :8020 + 外部 RAG :8010)端到端验证。

**改动文件**:

| 文件 | 改动 |
|------|------|
| `miniprogram/src/utils/request.js` | **新增**。统一请求封装:`{code,data,message,request_id}` 契约、Bearer token、写操作自动 `Idempotency-Key`、`40002` 清 token 跳登录、对话类 300s 超时(真实 LLM 15s~190s);`fmtDateTime` 时区感知(naive 原样、+00:00/+08:00 转 +8 显示)、`nowLocalISO` |
| `miniprogram/src/api/{auth,chat,health,plan,reminder,me}.js` | **新增**。按模块封装 17 个端点 |
| `miniprogram/src/pages/login/login.vue` | H5 用 `dev-` 前缀模拟码走开发登录,小程序走 `uni.login` |
| `miniprogram/src/pages/index/index.vue` | 真实对话:会话创建/消息发送/中断恢复(确认/拒绝/修改)、历史恢复(含 `waiting_confirmation` 时按 `plan_id` 关联草稿计划)、🚨 紧急红卡 |
| `miniprogram/src/pages/record/record.vue` | 观察记录真实 CRUD(血糖/血压/体重/症状 四种 payload)+ 分页加载 |
| `miniprogram/src/pages/stats/stats.vue` | 趋势统计真实数据(SVG 折线 + 正常带) |
| `miniprogram/src/pages/plan/plan.vue` + `plan-detail/` | 计划三态列表 + 归档(409 冲突提示)+ 时间轴详情 |
| `miniprogram/src/pages/reminder/reminder.vue` | 提醒真实 CRUD + 取消(已发送 409 提示) |
| `miniprogram/src/pages/me/me.vue` | 资料读写(性别/生日/慢病标签,后端无昵称字段已移除) |
| `miniprogram/src/mock/` | **删除** |
| `miniprogram/README.md` | 重写:三服务启动、页面-接口映射表、核心机制、已知简化 |
| `app/controller/v1/conversation.py` | 新增 `GET /conversations/{id}/messages`(按 created_at 升序,限 500 条)——对话历史恢复必需,此前后端缺失 |
| `app/service/conversation_service.py` | 新增 `list_messages`/`serialize_message`(含 `structured_data` 透出) |
| `app/controller/v1/reminder.py` + `app/service/reminder_service.py` | **两处缺陷修复**(见下) |

**缺陷修复**:
1. 提醒创建 500:ReminderCreate schema 的 `next_run_at` 字段与 `create_reminder` 的显式参数重名,`**payload` 展开时 TypeError(multiple values)。修复:从 schema 移除该字段(schedule_rule 是唯一时间来源,符合 F3 语义),service 层再加防御性过滤。
2. `next_run_at` 序列化缺时区后缀:SQLite 存 naive UTC,原样返回 `2026-10-24T23:30:00`,前端会按本地时间误读(+8 小时偏差)。修复:新增 `_iso_utc()` 补 `+00:00`。

**验证**(curl 全链路,三服务真实运行):
- 开发登录 → `/me` → 资料更新 ✓
- 观察记录创建/列表(分页)/统计/删除 ✓
- 提醒创建(时间解析 `2026-10-25 07:30 +08:00` → 存储 `2026-10-24T23:30:00+00:00` ✓)/列表/取消 ✓
- 会话创建 → 消息历史列表 ✓
- **真实 LLM 对话**:"今天早餐后血糖 7.2" → 意图 LoRA 路由 + RAG 检索 + LLM 生成,返回 `{code:0, status:"completed", workflow:{need_record:true,...}, final_response:"✅ 已记录数据"}` ✓

**遗留**:
- 计划拒绝/修改的端到端覆盖未实测(后端该链路已修复,待前端走查)
- 提醒真实推送依赖后端 worker + 微信模板消息(未配置),页面仅管理提醒数据
- 趋势图为 SVG 手绘,正式期换 lime-echart
- 仅 H5 验证,mp-weixin 编译/微信开发者工具待验证

---

## 2026-10-24 去除"小艾"名称,统一为"慢性病管理助手"

**类型**:缺陷修复(文案)

**背景**:用户澄清"小艾"是打字错误,产品不应使用该名称。

**改动文件**(miniprogram/ 内 10 个文件,13 处):`index.html`(title)、`src/manifest.json`(name/title)、`src/pages.json`(导航标题)、`src/App.vue`(日志)、`src/mock/index.js`(欢迎语/提醒回复)、`src/pages/login/login.vue`(logo 与名称)、`src/pages/index/index.vue`(头像字)、`src/pages/plan/plan.vue`(空态文案)、`README.md`。统一改为"慢性病管理助手"(无品牌名,登录 logo 用"康"、对话头像用"助")。

**验证**:全库 grep 无"小艾"残留;H5 热更新编译通过,无报错。

---

## 2026-10-24 新增微信小程序测试界面(未连接后端)

**类型**:新功能(前端)

**背景**:用户要求先写一个可看的测试界面,暂不连接后端,用于评审 UI/交互。

**改动文件**:`miniprogram/` 目录(**新增**,uni-app Vue3 + Vite 工程,依赖版本 `3.0.0-alpha-5030320261021002` 全套对齐;注:官方模板 degit 拉取失败、npm vue3 latest tag 发布不完整,均手写规避):

| 文件 | 说明 |
|------|------|
| `miniprogram/src/pages/login/` | 登录页(模拟微信一键登录) |
| `miniprogram/src/pages/index/` | 对话页:消息气泡、思考中动画、🚨 紧急红色卡片、**计划确认卡片(确认/拒绝/修改,修改后新草稿版本+1)** |
| `miniprogram/src/pages/record/` | 记录页:血糖/血压/体重/症状 筛选、录入弹窗、删除(长按+二次确认)、趋势入口 |
| `miniprogram/src/pages/stats/` | 趋势页:SVG 手绘折线(暂代 ECharts),正常区间标注、超标红点、摘要卡片 |
| `miniprogram/src/pages/plan/` + `plan-detail/` | 计划三态列表(待确认/进行中/历史)、进度条、归档(二次确认)、时间轴详情 |
| `miniprogram/src/pages/reminder/` | 提醒列表(待提醒/已发送/已取消)、picker 新建、取消(二次确认) |
| `miniprogram/src/pages/me/` | 资料查看编辑(性别/生日/慢病标签)、免责声明、退出登录 |
| `miniprogram/src/components/plan-confirm-card/` | 计划确认卡片组件(easycom) |
| `miniprogram/src/mock/index.js` | **Mock 数据层**:按关键词返回对话剧本(血糖→✅记录、血压→🚨紧急、计划→两阶段确认、提醒→⏰),记录/计划/提醒/资料全本地数据,均带模拟延迟 |

**验证**:`npm install` 448 包安装成功;`npm run dev:h5` 启动于 http://127.0.0.1:5173;11 个模块全部编译通过(200),编译日志无错误。

**遗留**:仅 H5 浏览器验证,未在微信开发者工具/真机验证(mp-weixin 编译待 M1 里程碑);接入真实后端时删除 `src/mock/`、替换 `mockApi` 调用并新增 `utils/request.js`(见 miniprogram/README.md)。

---

## 2026-10-24 新增微信小程序前端开发计划书

**类型**:文档(规划)

**背景**:用户确定下一步为微信小程序前端开发,要求先出计划书。

**改动文件**:`docs/微信小程序前端开发计划书.md`(**新增**)。12 节:目标与验收标准、技术选型(uni-app Vue3 + Pinia + ECharts,沿用架构文档第 10 节决定)、页面与导航(4 tab + 4 子页)、核心模块设计(请求封装/登录态/对话状态机与计划确认卡片/记录/趋势/计划/提醒/我的)、**接口对接契约表(与 app/controller/v1/ 现有 17 个端点逐一核对)**、慢病人群 UI/UX 规范、目录结构、6 个里程碑(M1 骨架登录 → M6 联调验收,约 10-16 人日)、测试策略、风险与依赖(对话链路 15-190s 耗时、微信域名、提醒推送依赖等)、环境搭建、交付物。

**待办**:评审通过后按里程碑实施。

---

## 2026-10-24 新增 LangGraph 工作流详解子页面

**类型**:文档

**背景**:用户要求把 LangGraph 核心流程写成网页,并作为《慢性病管理Agent架构设计.html》的子页面,点击即可查看详细架构。

**改动文件**:

| 文件 | 改动 |
|------|------|
| `docs/LangGraph工作流详解.html` | **新增**。与主页面同款设计语言,11 节:工作流总览、主图结构与路由(builder.py/routing.py 全部路由函数)、意图归一化、计划/提醒子图(修复后语义)、ClinicalState 字段分组、14 个节点清单、人机协同协议(checkpoint 状态机)、提醒机制(outbox + 时间解析)、外部服务依赖、五条典型消息流(E2E 实测数据)、安全保障 |
| `docs/慢性病管理Agent架构设计.html` | 第 04 节新增 `.goto` 入口链接卡片(点击进入子页面);修正 4.1 节过时的「现状差距」callout(user_confirm 默认同意问题已于 2026-10-24 修复,现为 confirm_plan 确认机制);footer 引用补充子页面 |

**验证**:两页 HTML 标签配平校验通过;浏览器打开渲染正常;子页面内容与 `app/graph/`、`app/nodes/` 当前代码逐一核对一致。

---

## 2026-10-24 修复 F2/F3:计划提醒不创建、提醒时间不解析

**类型**:缺陷修复(高严重度)

**背景**:2026-10-24 三服务端到端联合测试(`docs/E2E_INTEGRATION_TEST_REPORT_2026-10-24.md`)发现两个高严重度缺陷:
- F2:API 确认计划后不创建计划提醒——`resume_interrupt(confirm)` 只翻转计划状态不重跑工作流,`plan_reminder` 链只在工作流单测路径可执行;
- F3:提醒时间未解析为绝对时间——原始时间文本透传落库,`create_reminder` 以 `next_run_at or now` 兜底,outbox 立即可投递。

### F2 修复

| 文件 | 改动 |
|------|------|
| `app/service/plan_service.py` | 新增 `confirm_plan(db, user_id, plan_id, revision)`:确认计划后按计划项创建提醒(`plan_item_id` 关联 + `dedupe_key=plan:{plan_id}:{item_id}` 幂等);无时间/解析失败的项不创建,放入 `skipped` 返回 |
| `app/service/conversation_service.py` | `resume_interrupt` 的 confirm 分支改用 `confirm_plan`,结果携带 `reminders`/`skipped` |
| `app/nodes/plan_archive_node.py` | 改用 `confirm_plan`,回写 `reminder_created`/`reminder_result` |
| `app/graph/plan_reminder_graph.py` | 路由重排:计划提醒改由确认服务创建,删除 `plan_reminder` 链;`user_confirm` 未确认且 `need_reminder` 时进入直接提醒链(修复多意图消息中直接提醒被丢弃),否则 END;`plan_archive → END` |
| `app/nodes/reminder_create_node.py` | 简化为仅处理直接提醒 |
| `app/nodes/plan_reminder_node.py` | **删除**(链路由已无引用) |
| `app/config/constants.py` | 删除 `NODE_PLAN_REMINDER`、`REMINDER_SOURCE_DIRECT/PLAN` |
| `app/graph/state.py` | 删除死字段 `reminder_tasks`、`plan_reminders` |

### F3 修复

| 文件 | 改动 |
|------|------|
| `app/core/tools/time_parser.py` | `parse_time_text` 支持 明早/明晚/今早;新增 `resolve_next_run_at(schedule_rule)`:自然语言/`HH:MM`/显式日期 → aware UTC(中国固定 +8),已过时刻顺延次日,解析失败返回 None |
| `app/service/reminder_service.py` | `create_reminder` 强制解析时间,失败抛 `ServiceException`(422"提醒时间无法解析"),禁止静默立即投递;`next_run_at` 落库,outbox `available_at = next_run_at` |

### 测试与文档

| 文件 | 改动 |
|------|------|
| `tests/test_e2e_three_services.py` | E2E-06/07 增加 `next_run_at` 回归断言;E2E-07 失败注释更新为已修复说明 |
| `docs/E2E_INTEGRATION_TEST_REPORT_2026-10-24.md` | 新增第 11 节:F2/F3 修复记录与复测结果 |
| `docs/STRUCTURE.md`、`docs/ARCHITECTURE.md` | 同步删除 `plan_reminder_node` 与 `reminder_tasks` 引用 |

### 验证

- 普通测试套件:36 passed、1 skipped;
- 三服务 E2E(真实意图 7B LoRA + 外部 RAG + 真实 LLM):**9 passed(370.8s)**,E2E-07 转绿;新增断言用例重跑 2 passed;
- 隔离库核查:确认后计划提醒落库(`plan_item_id` 非空);`notification_outbox` 中 `available_at <= now` 为 0 条;`明早8点` → 次日 00:00 UTC。

### 遗留

- reminder worker 真实投递未在线验证(需微信通道或替换 in_app 投递实现);
- 计划确认的 reject/modify 分支无 E2E 覆盖;
- F4(纯提问隐式添加记录意图)待产品决策。
