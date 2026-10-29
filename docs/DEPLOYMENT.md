# 阿里云生产部署方案

> 适用范围:阿里云 ECS(Linux)+ 微信小程序正式环境。更新于 2026-10-25。

## 1. 架构总览

```text
微信小程序 / H5 ──HTTPS(443)──> Nginx ──┬─ /api/ ──> api:8000 (docker) ──> 通义 DashScope API(公网)
                                        │               │
                                        │               ├──> Medical_Lora 意图服务 127.0.0.1:8020(宿主机 systemd,GPU)
                                        │               ├──> RAG 检索服务 127.0.0.1:8010(宿主机 systemd,CPU)
                                        │               ├──> PostgreSQL (docker 内部)
                                        │               └──> Redis (docker 内部)
                                        │               worker (docker) 定时投递提醒
                                        └─ /(静态文件) ──> /var/www/h5(前端 build 产物)
```

对外只暴露 443 一个端口:API 与 H5 页面同域名,由 Nginx 按路径分流(反向代理)。

- **本项目**(api + worker + postgres + redis):docker compose 一键拉起,无 GPU 要求。
- **RAG 服务**:CPU 即可,与 api 同机部署。
- **Medical_Lora 意图服务**:Qwen2.5-7B + LoRA(4bit 量化),需要约 8GB 显存,必须部署在 GPU 实例上(可同机也可内网跨机)。意图服务是工作流必需依赖,不可降级绕过。
- **LLM 生成**:走通义 DashScope API,国内直连,无需自建。

### 1.1 单机部署(起步推荐)

三个项目可以整体部署在**一台 GPU ECS** 上,资源估算:

| 服务 | 显存 | 内存 |
|------|------|------|
| Medical_Lora(7B LoRA,4bit) | ~8GB(推理含激活值) | 加载峰值 15-20GB |
| RAG(FAISS 索引 MB 级) | 无 | 1-2GB |
| 本项目 docker 四件套 | 无 | ~2GB |
| **合计** | **≥8GB,推荐 16GB** | **推荐 32GB** |

**推荐选型**:阿里云 gn7i 系列(如 ecs.gn7i-c8g1.2xlarge:8 vCPU / 30GB / 16GB T4),按量付费起步验证后再转包月。8GB 显存是理论下限,峰值推理可能 OOM,不建议。

单机方案的优势:架构最简单;意图服务与 RAG 只监听 `127.0.0.1`,对外零暴露;compose 默认的 `host.docker.internal:8010/8020` 开箱即用,`.env` 无需额外配置。缺点是 GPU 实例成本高、模型与 api 共享内存,流量上来后需要把 api 侧拆分到普通实例。

多机方案(可选):api/RAG 放普通 CPU 实例,Medical_Lora 单独 GPU 实例,`.env` 里 `INTENT_BASE_URL`/`RAG_DOCKER_BASE_URL` 指向内网 IP,GPU 实例安全组仅放行 api 实例的内网网段访问 8020。

## 2. 前置条件

| 事项 | 说明 |
|------|------|
| 域名 + ICP 备案 | 微信小程序正式版强制要求:request 合法域名必须 HTTPS 且域名已备案。备案走阿里云备案系统(约 1-3 周,提前申请) |
| SSL 证书 | 阿里云数字证书管理服务免费证书,或服务器上 certbot 签 Let's Encrypt |
| ECS 实例 | 单机全量部署:GPU 实例(见下),8 vCPU / 30GB / 16GB 显存起;多机方案 api 侧 2C4G 起,RAG 同机则 4C8G 更稳 |
| GPU 实例 | Medical_Lora 需显存 ≥8GB,推荐 16GB T4(阿里云 gn7i 系列);单机部署时该实例同时承载三个项目 |
| 安全组 | 仅开放 22(SSH,建议限制来源 IP)、80、443;**不要**对公网开放 8000/8010/8020 |
| 微信 AppID/Secret | 小程序后台获取,配置到环境变量 |

## 3. 部署步骤

以下假设:域名 `api.example.com`,ECS 为 Ubuntu 22.04,代码目录 `/opt/chronic_care_agent_2`,三个项目均已在阿里云代码库或通过 git/上传方式落到服务器。

### 3.1 初始化服务器

```bash
# Docker 与 compose 插件
curl -fsSL https://get.docker.com | sh
# 阿里云地域建议配置 docker 镜像加速(容器镜像服务 ACR 个人实例)

# Nginx
apt install -y nginx git
```

### 3.2 部署本项目(api + worker + postgres + redis)

```bash
cd /opt/chronic_care_agent_2

# 生产环境变量(不要提交到 git)
cat > .env <<'EOF'
POSTGRES_PASSWORD=<随机强密码>
JWT_SECRET_KEY=<随机 ≥32 位字符串>
LLM_API_KEY=<DashScope API Key>
WX_APPID=<小程序 AppID>
WX_SECRET=<小程序 Secret>
# 同机部署外部服务时保持默认即可(compose 已配 host.docker.internal:host-gateway)
# INTENT_BASE_URL=http://host.docker.internal:8020
# RAG_DOCKER_BASE_URL=http://host.docker.internal:8010
EOF

docker compose up -d --build
docker compose ps                  # migrate 应已成功退出,其余服务 running
curl -s http://127.0.0.1:8000/readyz
```

compose 中 `migrate` 服务自动执行 `alembic upgrade head`,`APP_ENV=prod` 会强制校验:`JWT_SECRET_KEY` ≥32 位、`REDIS_URL` 非空、`ALLOW_DEV_LOGIN=false`,任一不满足 api 直接拒绝启动。

若 RAG/意图服务部署在**另一台机器**,在 `.env` 显式指定内网地址:

```bash
INTENT_BASE_URL=http://10.0.0.2:8020
RAG_DOCKER_BASE_URL=http://10.0.0.3:8010
```

### 3.3 部署 RAG 服务(宿主机 systemd)

```bash
cd /opt/RAG
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

cat > /etc/systemd/system/rag.service <<'EOF'
[Unit]
Description=Chronic-care RAG service
After=network.target

[Service]
WorkingDirectory=/opt/RAG
ExecStart=/opt/RAG/.venv/bin/python -m uvicorn service_app:app --host 127.0.0.1 --port 8010
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload && systemctl enable --now rag
curl -s http://127.0.0.1:8010/healthz
```

### 3.4 部署 Medical_Lora 意图服务(GPU 机器 systemd)

```bash
cd /opt/Medical_Lora
python3 -m venv .venv
.venv/bin/pip install -r service_requirements.txt

cat > /etc/systemd/system/intent.service <<'EOF'
[Unit]
Description=Chronic-care intent service (Qwen 7B LoRA)
After=network.target

[Service]
WorkingDirectory=/opt/Medical_Lora
ExecStart=/opt/Medical_Lora/.venv/bin/python -m uvicorn service_app:app --host 127.0.0.1 --port 8020
Restart=always
# 模型加载到显存,放宽启动超时
TimeoutStartSec=1800

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload && systemctl enable --now intent
curl -s http://127.0.0.1:8020/healthz   # 冷启动加载 7B 模型,可能需数分钟
```

单机部署时 `127.0.0.1` 即可,对外零暴露。若 api 部署在另一台机器,把 `--host` 改为 `0.0.0.0`,并用安全组限制 8020 仅内网网段可达(不放行公网入方向)。

### 3.5 前端 H5 构建与上传

本地构建 uni-app H5(需要 miniprogram/ 目录已 `npm install`):

```bash
cd miniprogram
npm run build:h5
# 产物在 dist/build/h5/
scp -r dist/build/h5/* root@<服务器>:/var/www/h5/
```

### 3.6 Nginx 反向代理 + HTTPS(前后端同端口)

```nginx
server {
    listen 80;
    server_name api.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name api.example.com;

    ssl_certificate     /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;

    # API 统一走 /api/v1 前缀(前端 baseURL 已带),转发给后端
    location /api/ {
        proxy_pass http://127.0.0.1:8000;    # 不带路径,原样转发 /api/v1/...
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        # 对话类请求最长 300s(真实 LLM 15s~190s),必须放宽
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }

    # H5 静态文件(uni-app build 产物)
    location / {
        root /var/www/h5;
        try_files $uri $uri/ /index.html;    # SPA 路由刷新回退
    }
}
```

### 3.7 上线验证清单

1. `curl https://api.example.com/readyz` 返回 200。
2. `curl https://api.example.com/dependencies` 两项均为 `up`。
3. 浏览器打开 `https://api.example.com/` 能看到 H5 登录页,刷新任意路由不 404(SPA 回退生效)。
4. 关闭开发登录:确认 `ALLOW_DEV_LOGIN` 未开启(prod 校验会强制),`POST /api/v1/auth/wechat-login` 的 `dev-` 前缀登录在生产返回错误。
5. 小程序后台「开发管理-服务器域名」配置 `https://api.example.com` 为 request 合法域名。
6. 真实对话端到端:小程序发一条"今天早餐后血糖 7.2",确认意图路由 + RAG 检索 + LLM 生成全链路返回。
7. 提醒 worker:`docker compose logs worker` 无异常刷屏。

## 4. 运维

### 备份

```bash
# 每日凌晨 3 点备份 PostgreSQL 到 /opt/backups
0 3 * * * docker compose -f /opt/chronic_care_agent_2/docker-compose.yml exec -T postgres \
  pg_dump -U chronic_care chronic_care | gzip > /opt/backups/chronic_care_$(date +\%F).sql.gz
```

备份文件建议同步到 OSS 或另一台机器;`pg_data`、`redis_data` 卷在 compose 中已持久化,重装时保留卷即可恢复。

### 日志与监控

- 日志:`docker compose logs -f api` / `docker compose logs -f worker`;RAG 与意图服务看 `journalctl -u rag -f` / `journalctl -u intent -f`。
- 健康检查:`/readyz`(api)、`/healthz`(两个外部服务);阿里云云监控可对 `https://api.example.com/readyz` 做拨测告警。
- 服务自愈:compose `restart: unless-stopped` + systemd `Restart=always`,机器重启后均自动拉起。

### 更新发布

```bash
cd /opt/chronic_care_agent_2
git pull
docker compose up -d --build     # migrate 自动执行增量迁移
```

注意:api 重建期间 `/readyz` 短暂不可用,建议在低峰期发布;数据库大版本升级前先备份。

### 安全基线

- 安全组最小开放:22(限 IP)/80/443;8010/8020 仅内网。
- `JWT_SECRET_KEY`、`POSTGRES_PASSWORD`、`LLM_API_KEY`、`WX_SECRET` 只存在于服务器 `.env`,确认 `.gitignore` 已排除。
- 生产 `CORS_ORIGINS` 按需收紧为小程序来源(如不需要跨域可保持默认)。
- `RAG_FAIL_OPEN=true` 为业务连续性设计;若合规要求更严格可置 false(服务不可用时建议/计划链直接报错)。
