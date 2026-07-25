# 喵格匹配 CatMBTI · 代码框架

> 抖音 AI 创变者计划 黑客松项目 ｜ 详细产品方案见 [../docs/喵格匹配_PRD.md](../docs/喵格匹配_PRD.md)

本目录实现 PRD 中:

- ✅ **M1 · 猫 MBTI 分析** — 视频上传 → Gemini 提信号 → 规则引擎打分 → 16 型报告卡
- ✅ **M3 · 视频生成** — Gemini 写脚本 → Seedance 2.0 图生视频 → "让 TA 开口对你说话"

> 想把网址发给朋友/同事在手机上玩,直接看 [DEPLOY.md](DEPLOY.md) — 那里有 cloudflared 公网隧道的完整流程。
> 本文档只覆盖本地开发(前后端两个窗口,localhost 访问)。

---

## 0. 前置条件

| 依赖 | 版本 | 检查命令 |
| --- | --- | --- |
| Python | 3.11+(项目用了 PEP 604 `X \| Y` 联合类型,3.10 以下不行) | `python --version` |
| Node.js | 18+(推荐 20) | `node --version` |
| Git | 任意近期版本 | `git --version` |
| 一把 OpenAI 兼容的 Gemini 代理 key | 见下面 §2 | — |

Windows 用户直接用 PowerShell 跑就行,下面命令都是跨平台的。

---

## 1. Clone 仓库

```bash
git clone <这个仓库的 URL>
cd Hackathon-cat-mbti
```

下面所有命令默认在仓库根目录运行。

---

## 2. 准备自己的 API key ⚠️ 必看

后端调 Gemini 视频理解 + 视频生成,都走 **OpenAI 兼容协议的 AI 代理**。代码本身不绑死任何一家代理。

### 2.1 去哪里搞 key

最常用的几家(国内可直连、按量计费、有 Gemini / Veo / Seedance 通道):

- [openai-next.com](https://api.openai-next.com)(项目默认 base_url)
- 其他任意支持 `chat/completions` + `response_format=json_object` + `stream=true` 的代理

注册账号 → 充值 → 后台拿一条 `sk-` 开头的 key。

> **不要用别人发你的 key**,也不要把仓库里 `.env.example` 里那条示例 key 当成能用的 —— 那条只是占位,额度可能早就耗光或被禁用。

### 2.2 把 key 填进 .env

```bash
# Windows
copy src\server\.env.example src\server\.env

# macOS / Linux
cp src/server/.env.example src/server/.env
```

打开 [src/server/.env](src/server/.env),改这几行:

```dotenv
GEMINI_API_KEY=sk-你自己的key
GEMINI_BASE_URL=https://api.openai-next.com/v1   # 改成你代理的 v1 端点,保留 /v1 后缀
GEMINI_MODEL=gemini-3.1-pro-preview              # 用你代理「可用模型」列表里的 ID
VIDEO_MODEL=doubao-seedance-2-0-fast-260128      # 见下面的"视频模型选哪个"
```

#### 视频模型选哪个

| 模型 | 状态 | 备注 |
| --- | --- | --- |
| `doubao-seedance-2-0-fast-260128`(字节 Seedance 2.0) | ✅ 推荐 | 国内通道,稳 |
| `veo3.1-pro`(Google Veo) | ⚠️ 经常被拒 | Google 反滥用系统会对代理出口 IP 触发 `reCAPTCHA evaluation failed / PUBLIC_ERROR_UNUSUAL_ACTIVITY`,代理共用一个账号时高频报错。如果一定要用就备好备用模型 |

> 不填 `GEMINI_API_KEY` 也能跑 —— 后端会用 hash stub 生成假的行为信号,UI 流程完全通,适合"我先把前端跑起来看一眼"。但视频生成必须有 key。

---

## 3. 装依赖 + 跑后端(窗口 ①)

```bash
cd src/server

# 建虚拟环境(强烈推荐,避免污染全局 site-packages)
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt

python -m uvicorn app.main:app --reload --port 8000
```

看到这两行就是 OK 了:

```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

**先单独 ping 一下 LLM 通道**,确认 key + 代理 + model ID 没问题:

```bash
curl http://localhost:8000/api/llm/ping
```

成功长这样:
```json
{"ok": true, "base_url": "https://api.openai-next.com/v1", "model": "gemini-3.1-pro-preview", "reply": "你好"}
```

失败长这样(就回去改 `.env` 的 `GEMINI_MODEL` 或 `GEMINI_BASE_URL`):
```json
{"detail": {"upstream_status": 503, "upstream_body": {"error": {"message": "无可用渠道 xxx"}}}}
```

其他常用入口:
- API 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/healthz

**保持这个窗口开着。**

---

## 4. 跑前端(窗口 ②)

```bash
cd src/web
npm install
npm run dev
```

打开 http://localhost:5173 —— Vite 已经把 `/api/*` 代理到后端 8000,无需 CORS 配置。

> 移动端调试:Vite dev server 默认监听 `0.0.0.0`,同一 WiFi 下手机直接访问 `http://<你电脑的IPv4>:5173` 就行。`ipconfig`(Windows) / `ifconfig`(mac/linux)看 IP。

---

## 5. 想把链接发给别人在手机上玩?

跳到 [DEPLOY.md](DEPLOY.md) —— 用 cloudflared 起一条临时公网隧道,出来一个 `https://*.trycloudflare.com` 给对方就行,5 分钟搞定。

---

## 6. 目录结构

```
src/
├── README.md                # ← 你正在看
├── DEPLOY.md                # 公网部署 / cloudflared 隧道流程
├── build_and_start.bat      # 一键构建前端 + 启后端(Windows)
│
├── server/                  # Python FastAPI 后端
│   ├── .env.example         # 把它复制成 .env,填自己的 key
│   ├── app/
│   │   ├── main.py          # FastAPI 实例 + CORS + 路由
│   │   ├── api/
│   │   │   ├── analyze.py   # POST /api/analyze 视频上传 + MBTI 分析
│   │   │   ├── video.py     # POST /api/video/start  视频生成 job + 同源代理
│   │   │   └── llm.py       # GET  /api/llm/ping     LLM 通道自检
│   │   ├── core/
│   │   │   ├── config.py        # pydantic-settings 读 .env
│   │   │   ├── gemini_client.py # 行为信号提取(OpenAI SDK 调代理)
│   │   │   ├── video_gen.py     # LLM 写脚本 + 图生视频
│   │   │   ├── video_jobs.py    # 异步 job 存储 + 同源 MP4 代理
│   │   │   ├── video_frames.py  # OpenCV 等距抽帧 + 时间戳 + 关键帧
│   │   │   ├── signals.py       # 行为信号 schema + 加权打分表
│   │   │   └── mbti.py          # 规则引擎 + 16 型档案 + ISFP 兜底
│   │   └── models/schemas.py    # Pydantic 响应模型
│   ├── requirements.txt
│   └── README.md
│
└── web/                     # React 前端
    ├── src/
    │   ├── pages/           # Upload / Analyzing / Report / Video
    │   ├── components/      # ReportCard
    │   ├── data/samples.ts  # 3 张示例猫(无需后端即可演示)
    │   ├── api/client.ts    # axios 封装
    │   ├── store/analysis.ts# Zustand store
    │   └── types/api.ts     # 与后端 schema 对齐
    ├── package.json
    └── README.md
```

---

## 7. 核心链路

```
[M1 MBTI 评测]
┌─────────────┐    POST /api/analyze     ┌─────────────────────┐
│  Upload 页  │  ───────────────────────▶│ FastAPI             │
│ (视频文件)  │                          │ ├─ video_frames.py  │
└──────┬──────┘                          │ │   抽 8 帧 + 时间戳│
       │                                 │ ├─ gemini_client.py │
       ▼                                 │ │   信号打分        │
┌─────────────┐                          │ ├─ mbti.py          │
│ Analyzing   │                          │ │   规则引擎 → MBTI │
│ Loading 动画│◀──── 返回报告 + keyframe ┤ └─ ISFP 兜底        │
└──────┬──────┘                          └─────────────────────┘
       ▼
┌─────────────┐
│ Report 报告 │
│ + 保存 PNG  │
│ + 让 TA 开口│───┐
└──────┬──────┘   │
       │  [M3 视频生成]
       ▼          ▼
┌─────────────┐  POST /api/video/start      ┌─────────────────────────┐
│ Video 页    │ ──────────────────────────▶ │ video_gen.py            │
│ Loading 动画│                             │ ├─ generate_script:     │
└──────┬──────┘  GET /api/video/status      │ │   gemini-3.1-pro      │
       │  (轮询)                            │ │   生成 VideoScript    │
       ▼                                    │ │   (台词+分镜+prompt)  │
┌─────────────┐  GET /api/video/file/{id}   │ └─ generate_video:      │
│ 视频播放    │◀──── 同源代理 MP4 ──────────│     $VIDEO_MODEL        │
│ + 重生成    │                             │     默认 Seedance 2.0   │
└─────────────┘                             └─────────────────────────┘
```

---

## 8. 常见坑

| 现象 | 原因 | 修复 |
| --- | --- | --- |
| 后端启动报 `ModuleNotFoundError: No module named 'app.core.config'` | `src/server/app/core/config.py` 不见了 | 重新 pull / 确认这个文件存在,它是必需的 |
| `curl /api/llm/ping` 返回 503 `无可用渠道 xxx` | `.env` 里的 `GEMINI_MODEL` 写错或代理没开通 | 改成代理「可用模型」列表里的 ID 重启 |
| 视频生成失败 `reCAPTCHA evaluation failed / PUBLIC_ERROR_UNUSUAL_ACTIVITY` | 上游 Google Veo 把代理出口 IP 风控了 | 把 `VIDEO_MODEL` 换成 `doubao-seedance-2-0-fast-260128`(Seedance,不经 Google) |
| `npm run build` 报 `Cannot find module 'node:path'` | 缺 `@types/node` | `cd src/web && npm install -D @types/node` |
| 上传视频 → "AI 分析失败" | 看 [src/server/README.md](server/README.md) §"排错"那一节 | — |

---

## 9. 扩展点

| 想做的事 | 改哪里 |
| --- | --- |
| 换文本/视觉理解模型 | `.env` 里的 `GEMINI_MODEL` |
| 换视频生成模型(Seedance / Veo / ...) | `.env` 里的 `VIDEO_MODEL` |
| 改 MBTI 判定权重 / 平票阈值 | [server/app/core/signals.py](server/app/core/signals.py) `SCORING_TABLE` / `TIE_THRESHOLD` |
| 改视频脚本生成的 system prompt | [server/app/core/video_gen.py](server/app/core/video_gen.py) `SCRIPT_SYSTEM_PROMPT` |
| 调 LLM 温度 / 重试 | [server/app/core/video_gen.py](server/app/core/video_gen.py) 里的 `chat.completions` 参数 |
| 加新行为信号 | [server/app/core/signals.py](server/app/core/signals.py) 加字段 + 权重,[server/app/core/gemini_client.py](server/app/core/gemini_client.py) 的 prompt 加描述 |
| 16 型详细文案 | [server/app/core/mbti.py](server/app/core/mbti.py) `TYPE_PROFILE` |
| 报告卡视觉升级 | [web/src/components/ReportCard.tsx](web/src/components/ReportCard.tsx) |
| 加示例猫卡片 | [web/src/data/samples.ts](web/src/data/samples.ts) |
