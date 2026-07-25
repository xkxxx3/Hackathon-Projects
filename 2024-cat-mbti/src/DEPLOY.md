# 部署指南 — 从 git clone 到拿到公网 URL

让别人(同事 / 评委 / 朋友)用手机直接访问你本地跑的 demo。整个流程 10 分钟。

## 架构

```
       手机 / 任何外网设备
              │  (访问 https://xxx.trycloudflare.com)
              ▼
        Cloudflare 边缘
              │  (cloudflared 隧道,无需公网 IP / 开端口)
              ▼
        你的电脑 (127.0.0.1:8000)
              │
              ▼
       FastAPI · uvicorn
       ├─ /api/*         API 接口
       └─ /              托管 web/dist/ 编译后的前端(同源,免 CORS)
```

- **后端**: FastAPI on `0.0.0.0:8000`,同时提供 `/api/*` 接口和编译后的前端静态文件
- **前端**: React + Vite,`npm run build` 编译进 `web/dist/`,由后端托管
- **公网**: cloudflared quick tunnel 把本地 8000 暴露成 `https://*.trycloudflare.com`,免费、无需账号、无需开端口

---

## 0. 前置条件

| 依赖 | 版本 | 备注 |
| --- | --- | --- |
| Python | 3.11+ | 项目用了 PEP 604 联合类型 |
| Node.js | 18+(推荐 20) | 装前端构建 |
| cloudflared | 任意近期版本 | 见 §2 安装 |
| 一把 OpenAI 兼容的 Gemini 代理 key | — | 见 §3 |

下面命令都假设你在仓库根目录(`Hackathon-cat-mbti/`),Windows 用 PowerShell。

---

## 1. Clone 仓库

```bash
git clone <这个仓库的 URL>
cd Hackathon-cat-mbti
```

---

## 2. 装 cloudflared(只装一次)

cloudflared 是 Cloudflare 官方的隧道工具,免费、不要账号、不要域名。

```powershell
winget install --id Cloudflare.cloudflared
cloudflared --version
```

**国内 winget 装不上**(报 `0x80072efd InternetOpenUrl() failed`)是因为它从 GitHub 拉 release。三个备选:

```powershell
# A. 从 GitHub 镜像下载 exe(任选一个能用就行,然后放到 PATH 目录)
curl.exe -L -o cloudflared.exe https://mirror.ghproxy.com/https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe
curl.exe -L -o cloudflared.exe https://gh-proxy.com/https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe

# B. 让 winget 走系统代理(Clash/V2Ray 端口按实际改)
$env:HTTPS_PROXY = "http://127.0.0.1:7890"
winget install --id Cloudflare.cloudflared

# C. 完全不用 cloudflared,用 pinggy(Windows 自带 SSH,零下载)
ssh -p 443 -R0:localhost:8000 a.pinggy.io
# 注意:pinggy 免费版每 session 60 分钟自动断开,断开后 URL 会变
```

macOS:`brew install cloudflared`。Linux:`apt install cloudflared` 或从 [Cloudflare 官网](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) 拿包。

---

## 3. 配置自己的 API key ⚠️ 必看

后端调 Gemini 视频理解 + 视频生成,都走 **OpenAI 兼容协议的 AI 代理**。代码不绑死任何一家代理。

### 3.1 去哪里搞 key

最常用的:[openai-next.com](https://api.openai-next.com)(项目默认 base_url)。其他任意支持 `chat/completions` + `response_format=json_object` + `stream=true` 的代理都行。

注册账号 → 充值 → 后台拿一条 `sk-` 开头的 key。

> **不要用别人发你的 key,也不要照搬 `.env.example` 里那条** —— 那只是占位字符串,额度可能早就空了或者被禁了。

### 3.2 把 key 填进 .env

```powershell
# Windows
copy src\server\.env.example src\server\.env

# macOS / Linux
# cp src/server/.env.example src/server/.env
```

打开 [src/server/.env](server/.env),改这几行:

```dotenv
GEMINI_API_KEY=sk-你自己的key
GEMINI_BASE_URL=https://api.openai-next.com/v1   # 改成你代理的 v1 端点,保留 /v1 后缀
GEMINI_MODEL=gemini-3.1-pro-preview              # 你代理「可用模型」列表里的 ID
VIDEO_MODEL=doubao-seedance-2-0-fast-260128      # 见下面的"视频模型选哪个"
```

#### 视频模型选哪个

| 模型 | 状态 | 备注 |
| --- | --- | --- |
| `doubao-seedance-2-0-fast-260128`(字节 Seedance 2.0) | ✅ 推荐 | 国内通道,稳 |
| `veo3.1-pro`(Google Veo) | ⚠️ 经常被拒 | Google 反滥用系统会对代理出口 IP 触发 `reCAPTCHA evaluation failed / PUBLIC_ERROR_UNUSUAL_ACTIVITY`。代理共用账号时高频报错,建议优先用 Seedance |

> 不填 `GEMINI_API_KEY` 也能跑 demo —— 后端会用 hash stub 生成假的 MBTI 信号,前端流程完全通。但视频生成必须有 key。

---

## 4. 装依赖(只装一次)

### 4.1 后端

```powershell
cd src\server
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
cd ..\..
```

### 4.2 前端

```powershell
cd src\web
npm install
cd ..\..
```

> 如果 `npm run build` 报 `Cannot find module 'node:path'` / `Cannot find name '__dirname'`,补一条 `npm install -D @types/node` 就行。

---

## 5. 起服务(每次发布做这两步)

### 步骤 1 — 构建前端 + 启动后端(窗口 ①)

**最简单**:在仓库根目录双击 [src/build_and_start.bat](build_and_start.bat),它会自动 `npm install && npm run build` + 启动 uvicorn on `0.0.0.0:8000`。

**手动两步**:

```powershell
# 1) 构建前端
cd src\web
npm run build
# 验证: ls dist 应该看到 index.html + assets/

# 2) 启动后端
cd ..\server
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**关键校验** — 启动后看终端日志:

✅ 正确:
```
WARNING:app.main:SPA mode: serving frontend from .../src/web/dist
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

❌ 错误(手机访问会 404):
```
WARNING:app.main:SPA mode DISABLED: ... does not exist.
```

看到 `DISABLED` 说明 `web/dist/` 没构建好 —— 回去重新跑 `npm run build` 看完整输出有没有报错。

**本机自检**:

```powershell
curl http://127.0.0.1:8000/            # 应返回一坨 HTML(index.html)
curl http://127.0.0.1:8000/api/llm/ping # 应返回 {"ok": true, ...}
```

**保持这个窗口不关。**

---

### 步骤 2 — 起 cloudflared 隧道(窗口 ②)

```powershell
cloudflared tunnel --url http://127.0.0.1:8000
```

⚠️ **必须用 `127.0.0.1`,不能用 `localhost`** — Windows 下 cloudflared 解析 `localhost` 会优先走 IPv6(`::1`),而 uvicorn `--host 0.0.0.0` 只绑 IPv4,会报:
```
dial tcp [::1]:8000: connectex: No connection could be made because the target machine actively refused it.
```

几秒后会打印:
```
+--------------------------------------------------------+
|  Your quick Tunnel has been created! Visit it at:      |
|  https://random-words-xxxx.trycloudflare.com           |
+--------------------------------------------------------+
```

**保持这个窗口也不关。**

---

### 步骤 3 — 把链接发给别人

把那条 `https://...trycloudflare.com` 发给同事/朋友,他们手机浏览器直接打开就能用。

---

## 6. 关闭

两个窗口分别按 Ctrl+C。下次再启动重新跑步骤 1+2(`npm install`、`pip install`、装 cloudflared、填 .env 这些一次性的不用再做)。

---

## 7. 故障排查

### LLM 通道相关

| 现象 | 原因 | 修复 |
| --- | --- | --- |
| `curl /api/llm/ping` 返回 503 `无可用渠道 xxx` | `.env` 里 `GEMINI_MODEL` 写错或代理没开通 | 改成代理「可用模型」列表里的 ID 重启 |
| 返回 401 / 412 | API key 错、没填或没充值 | 检查 `.env` 的 `GEMINI_API_KEY` |
| 视频生成报 `reCAPTCHA evaluation failed / PUBLIC_ERROR_UNUSUAL_ACTIVITY` | 上游 Google Veo 把代理出口 IP 风控了 | 把 `VIDEO_MODEL` 换成 `doubao-seedance-2-0-fast-260128`(Seedance,不经 Google) |
| 报 `ModuleNotFoundError: No module named 'app.core.config'` | `src/server/app/core/config.py` 缺失 | 这个文件是必需的,确认 git pull 完整 |

### 手机访问 → 404 Not Found

按顺序排查:

| 终端看到 | 原因 | 修复 |
|---|---|---|
| `SPA mode DISABLED` | `web/dist/` 没构建 | `cd src/web && npm run build` |
| `SPA mode: serving frontend from ...` 但 `GET /` 还 404 | dist 里 `index.html` 缺失 | 重新 `npm run build` 看输出 |
| `npm run build` 报 `Cannot find module 'node:path'` | 缺 `@types/node` | `npm install -D @types/node` |
| `npm run build` 报别的 ts/vite 错 | 代码本身有问题 | 看具体报错 |

### cloudflared 报 `actively refused`

| 错误 | 原因 | 修复 |
|---|---|---|
| `dial tcp [::1]:8000: ... actively refused` | 用了 `localhost`,Windows 走 IPv6 但 uvicorn 只绑 IPv4 | 把命令里 `localhost` 换成 `127.0.0.1` |
| `dial tcp 127.0.0.1:8000: ... actively refused` | 8000 端口没人监听 — uvicorn 没起或已崩 | `netstat -ano \| findstr ":8000"` 看有没有 LISTENING;没有就回去手动跑 uvicorn 看完整报错 |

### cloudflared 下载失败 `0x80072efd`

见 §2 装 cloudflared 里的 A/B/C 三种备选。

### 隧道 URL 每次都变?

是的,quick tunnel 是临时的(机器/cloudflared 重启 URL 就变)。要固定域名得注册 Cloudflare 账号 + 绑域名 + `cloudflared tunnel create <name>`。Demo 场景临时 URL 完全够。

### 视频上传/生成在隧道下很慢?

cloudflared 上行带宽吃你本机的上传速度。家庭宽带通常上行 20-50 Mbps,够用。视频生成本身的耗时(60-180s)主要在 Veo / Seedance 模型本身,跟隧道无关。

### 多少人能同时用?

uvicorn 默认单 worker,但流式响应不阻塞,每个请求是独立 async task。瓶颈一般是上游模型 API 的 QPS 限制(你的代理套餐),不是本地 server。如果担心改成多 worker:

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 想换公网工具不用 cloudflared?

机制相同的等价品:

- **ngrok**(要注册): `ngrok http 8000`
- **localtunnel**(零配置): `npx localtunnel --port 8000`
- **pinggy**(零下载,SSH): `ssh -p 443 -R0:localhost:8000 a.pinggy.io`

### 不发到公网,只在同 WiFi 内访问?

跳过步骤 2,告诉对方访问 `http://<你的电脑内网IP>:8000`。

- 内网 IP: `ipconfig` 看 `IPv4 地址`(192.168.x.x 或 10.x.x.x)
- 第一次连接 Windows 防火墙会弹窗,选"允许专用网络访问"
- 前端 fetch 的 `/api` 是相对路径,会自动指向同一 host,不用改代码

---

## 8. 安全提醒

- **不要当生产用**: 没有鉴权,任何拿到 URL 的人都能调你的 API,消耗你的代理额度
- Demo 完务必关掉 cloudflared(Ctrl+C),URL 会立刻失效
- 上传目录 `server/uploads/` 会缓存用户视频,demo 完手动清一下
- `.env` 里的 API key **绝对不要提交进 git** —— [src/server/.gitignore](server/.gitignore) 已经把 `.env` 排除了,如果你新加目录记得跟上
- 仓库里 `.env.example` 那条示例 key 没有任何保证 —— 自己充值的 key 才稳
