# 慢性病管理助手(小程序前端)

uni-app(Vue 3 + Vite)患者端,**已对接真实后端** `http://127.0.0.1:8000/api/v1`。

## 启动

```bash
# 1. 后端(仓库根目录)
uvicorn app.main:app --host 127.0.0.1 --port 8000   # 默认 dev 环境,ALLOW_DEV_LOGIN=true
#    依赖服务:意图服务 Medical_Lora(8020)+ 外部 RAG(8010),对话链路需要

# 2. 前端(本目录)
npm install
npm run dev:h5
# 浏览器打开 http://127.0.0.1:5173
```

真机调试时把 `src/utils/request.js` 的 `BASE_URL` 改成局域网 IP;微信开发者工具需勾选「不校验合法域名」。

## 页面一览

| 页面 | 路径 | 对接接口 |
|------|------|----------|
| 登录 | `/pages/login/login` | POST `/auth/wechat-login`(H5 用 `dev-` 前缀模拟码;小程序端走 uni.login) |
| 对话 | `/pages/index/index` | POST `/conversations`、GET `/conversations/{id}`、GET/POST `/conversations/{id}/messages`、POST `/{id}/interrupts/{interrupt_id}/resume` |
| 记录 | `/pages/record/record` | GET/POST `/health/observations`、DELETE `/health/observations/{id}` |
| 趋势 | `/pages/stats/stats` | GET `/health/stats?metric_type=` |
| 计划 | `/pages/plan/plan` | GET `/plans`、POST `/plans/{id}/archive` |
| 计划详情 | `/pages/plan-detail/plan-detail` | GET `/plans`(按 plan_id 关联) |
| 提醒 | `/pages/reminder/reminder` | GET/POST `/reminders`、POST `/reminders/{id}/cancel` |
| 我的 | `/pages/me/me` | GET/PUT `/me`、POST `/auth/logout` |

## 核心机制

- `utils/request.js`:统一契约 `{code,data,message,request_id}`;code===0 成功;`40002` 清 token 跳登录;写操作(记录/提醒/发消息)自动携带 `Idempotency-Key`;对话类请求 300s 超时(真实 LLM 15s~190s)
- 对话状态机:`waiting_confirmation` 渲染计划确认卡片(确认/拒绝/修改);修改走后端重新生成(新 interrupt_id/revision)
- 历史恢复:进对话页拉取消息列表 + 会话状态;待确认时按 `plan_id` 关联草稿计划项
- 紧急消息(`final_response` 含 🚨)红色高亮卡片
- 提醒时间由后端解析为绝对时间(无法解析返回 422,前端 picker 天然规避)

## 目录结构

```
src/
├── pages/            # 8 个页面
├── components/plan-confirm-card/   # 计划确认卡片(easycom 自动注册)
├── api/              # 按模块封装:auth/chat/health/plan/reminder/me
├── utils/request.js  # 统一请求封装 + 时间格式化
├── pages.json / manifest.json / App.vue / main.js
```

## 已知简化(联调阶段)

- 趋势图为 SVG 手绘折线,正式期换 lime-echart
- 录入记录的 measured_at 使用客户端本地时间(无时区)
- 计划「进行中」无进度数据(后端暂无执行进度字段)
- 消息推送触达依赖后端 worker + 微信模板(未配置),页面仅管理提醒数据
