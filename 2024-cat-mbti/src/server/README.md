# CatMBTI Server

FastAPI 后端,负责视频上传、抽帧后调用 Gemini(OpenAI 兼容代理)提取行为信号、规则引擎判定 MBTI、网红猫匹配。

## 环境

- Python 3.11+
- OpenAI 兼容协议的 AI 代理(用来调 Gemini 3.1 Pro);本项目国内场景通过 sk- 形式的代理 key 接入

## 配置环境变量

复制 `.env.example` 为 `.env`(**注意**:代码读 `.env`,不读 `.env.example`):

```bash
copy .env.example .env       # Windows
# cp .env.example .env       # macOS / Linux
```

```dotenv
GEMINI_API_KEY=sk-xxxxxxxx                # 代理 key
GEMINI_BASE_URL=https://your-proxy.com/v1 # 代理的 OpenAI 兼容地址,末尾通常是 /v1
GEMINI_MODEL=gemini-3.1-pro
GEMINI_MIN_CONFIDENCE=0.4
VIDEO_FRAME_COUNT=8                       # 抽多少帧送给模型(越多越准但请求越大)
VIDEO_FRAME_JPEG_QUALITY=70
```

> 不填 `GEMINI_API_KEY` 时,后端会用确定性的 hash stub 生成行为信号 ——
> 适合本地无网调试,UI 流程完全可跑通。

## 运行

```bash
cd idea2/src/server
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt

uvicorn app.main:app --reload --port 8000
```

打开 http://localhost:8000/docs 看自动生成的 OpenAPI 文档。

## 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/analyze` | multipart 上传视频,返回 MBTI 报告 + 关键帧(base64) |
| POST | `/api/video/generate` | 两阶段:LLM 写脚本 → Seedance 2.0 出视频,返回 MP4 URL |
| GET  | `/api/llm/ping` | 不传视频,验证 LLM 代理通道 / model 是否可用 |
| GET  | `/healthz` | 健康检查 |

## 模块说明

```
app/
├── main.py              # FastAPI 实例 + CORS + 路由挂载
├── api/
│   ├── analyze.py       # POST /api/analyze
│   ├── video.py         # POST /api/video/generate  ★ 新
│   └── llm.py           # GET  /api/llm/ping
├── core/
│   ├── config.py        # Settings(读 .env)
│   ├── video_frames.py  # OpenCV 抽帧 → base64 JPEG + 时间戳 + 关键帧
│   ├── gemini_client.py # OpenAI SDK 调代理: 行为信号提取
│   ├── video_gen.py     # ★ 新: 脚本生成 (LLM) + Veo 3.1 Pro 调用
│   ├── signals.py       # 行为信号 schema + 加权打分表
│   └── mbti.py          # 规则引擎 + 16 型档案 + 兜底
└── models/schemas.py    # Pydantic 响应模型(含 VideoScript / VideoGenerationResponse)
```

## 数据流

### M1 MBTI 评测

```
POST /api/analyze (multipart 视频)
  │
  ▼
analyze.py: 落盘 → video_frames.extract_frames(path) → FrameBundle
  │
  ├── frames → gemini_client.extract_signals_via_gemini(bundle)
  │              chat.completions(model=gemini-3.1-pro,
  │                  messages=[system, user(text + N×image_url)],
  │                  response_format=json_object)
  │             → BehaviorSignals (~35 项 0-3 强度 + 4 confidence + highlights)
  │             → mbti.build_report() 加权 + 平票兜底 → MBTIReport
  │
  └── bundle.keyframe()  → 中间帧 base64 JPEG
                         → 返回前端,供 M3 用
  │
  ▼
AnalyzeResponse(analysis_id, report, keyframe_data_url)
```

### M3 视频生成(让 TA 开口对你说话)

```
POST /api/video/generate {mbti, keyframe_data_url, duration, cat_name, owner_name}
  │
  ▼
video_gen.generate(req):
  │
  ├── generate_script(req)
  │     chat.completions(model=gemini-3.1-pro,
  │         messages=[system=生成视频MBTI规则.md, user=形象规则模板填充],
  │         response_format=json_object,
  │         temperature=0.8)
  │     → VideoScript {title, theme, scene, spoken_script,
  │                    cat_visual_behavior, shot_plan,
  │                    video_prompt, negative_prompt}
  │
  └── generate_video(req, script)
        chat.completions(model=$VIDEO_MODEL,        # 默认 seedance-2.0
            messages=[user(text=script.video_prompt, image_url=keyframe)],
            stream=True)                            # 必走流式,绕过 CF 524
        → 用正则从拼接后的 text 抽 MP4 URL
        → 返回 video_url
  │
  ▼
VideoGenerationResponse(script, video_url)
```

## 与映射规则文档的对齐点

[docs/喵格MBTI映射规则.md](../../docs/喵格MBTI映射规则.md) 是单一真相源,代码改动需同步:

| 文档章节 | 代码位置 |
| --- | --- |
| §1 行为信号清单(每维度的信号 + 权重) | [app/core/signals.py](app/core/signals.py) `BehaviorSignals` + `SCORING_TABLE` |
| §1 平票时的默认极(I/S/F/P) | [signals.py](app/core/signals.py) `default_pole` 字段 + `TIE_THRESHOLD` |
| §2 16 型猫格昵称 / 关键词 | [mbti.py](app/core/mbti.py) `TYPE_PROFILE` |
| §3 打分算法 | [mbti.py](app/core/mbti.py) `_axis_score` / `_pick_pole` |
| §4 兜底:信息不足 → ISFP | [mbti.py](app/core/mbti.py) `_fallback_report` |

## 排错:模型名 / 通道问题

代理返回类似 `无可用渠道 gemini-3.1-pro` 这种 503,**99% 是 `GEMINI_MODEL` 写错或没开通**。

**最快验证方法**:不用传视频,直接 ping 一下通道。

```bash
curl http://localhost:8000/api/llm/ping
```

成功返回:
```json
{"ok": true, "base_url": "https://api.openai-next.com/v1", "model": "gemini-2.5-pro", "reply": "你好"}
```

失败返回 502 + 代理给的原始错误,直接照着改 `.env` 里的 `GEMINI_MODEL`:
```json
{"detail": {"upstream_status": 503, "upstream_body": {"error": {"message": "无可用渠道 gemini-3.1-pro"}}}}
```

### Gemini 在常见代理里的 ID

`gemini-3.1-pro` 这种写法基本不对 —— Google 的 API ID 通常长这样:

```
gemini-2.5-pro
gemini-2.5-pro-preview
gemini-2.5-flash
gemini-2.0-flash
gemini-2.0-flash-exp
gemini-1.5-pro / gemini-1.5-pro-latest
```

具体可用 ID 取决于代理服务商;openai-next 在「可用模型」页可以查到。挨个改 `.env`
里的 `GEMINI_MODEL`,重启 uvicorn,再 ping 一次。

### 上传视频后报 "AI 分析失败"

现在错误会带上代理给的原始 message,看 report 卡底部 `兜底输出 · ...` 那一行,以及后端日志里的 traceback。常见原因:

| 现象 | 原因 |
| --- | --- |
| `503 无可用渠道 xxx` | model ID 错或未开通 → 见上方 |
| `401 Unauthorized` | API key 错或没充值 |
| `413 Request Entity Too Large` | 抽帧数量太多 → 调小 `VIDEO_FRAME_COUNT` 或 `VIDEO_FRAME_JPEG_QUALITY` |
| `JSON 解析失败` | 代理返回的不是合法 JSON → 看看代理是否支持 `response_format=json_object` |
| `cv2 无法打开视频` | 视频编码不支持 → 转成标准 H.264 mp4 |


- **想换模型**:改 `.env` 的 `GEMINI_MODEL`,代码无需改。
- **想换代理**:改 `.env` 的 `GEMINI_BASE_URL` 和 `GEMINI_API_KEY`。
- **抽帧太少 / 太多导致代理 413**:调 `.env` 的 `VIDEO_FRAME_COUNT` 和 `VIDEO_FRAME_JPEG_QUALITY`。
- **想加信号**:在 [signals.py](app/core/signals.py) `BehaviorSignals` 加字段、`SCORING_TABLE` 加权重,然后在 [gemini_client.py](app/core/gemini_client.py) 的 `SYSTEM_PROMPT` 字段示意里加一行。
- **想换权重 / 平票阈值**:改 [signals.py](app/core/signals.py),其他不动。
- **想换回 Gemini 原生协议(File API + 视频直传)**:在 [gemini_client.py](app/core/gemini_client.py) 旁边新加 `gemini_native_client.py` 用 `google-genai` SDK,在 [mbti.py](app/core/mbti.py) `build_report` 里换调用即可,下游算法不变。
