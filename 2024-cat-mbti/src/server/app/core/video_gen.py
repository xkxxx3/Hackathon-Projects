"""Two-stage video generation pipeline.

Stage 1 (text LLM): given the cat's MBTI, ask the model to write a structured
script (theme, scene, spoken_script, video_prompt, negative_prompt, ...). The
system prompt is the verbatim rules in docs/生成视频MBTI规则.md §1-§9; the user
template comes from docs/生成视频形象规则.md.

Stage 2 (image-to-video): feed the keyframe + script.video_prompt to the
configured video model (Seedance 2.0 / Veo 3.1 Pro / ...) via the OpenAI-
compatible proxy. Extract the resulting MP4 URL from the streamed response
and return it.

If either stage fails, we surface the upstream proxy error verbatim so the
frontend can show why instead of a generic "生成失败".
"""
from __future__ import annotations

import json
import logging
import re
import time

from app.core import seedance_client
from app.core.config import settings
from app.core.gemini_client import _extract_json, _make_client, is_enabled
from app.core.streaming_helpers import HEARTBEAT, with_heartbeat
from app.models.schemas import (
    VideoGenerationRequest,
    VideoGenerationResponse,
    VideoScript,
)

logger = logging.getLogger(__name__)


# Verbatim from docs/生成视频MBTI规则.md — system prompt for the script writer.
SCRIPT_SYSTEM_PROMPT = """\
你是"猫咪MBTI视频总导演""宠物人格编剧""短视频分镜策划师"。

你的任务是:根据用户输入的猫咪 MBTI 类型、猫咪基础信息和主人关系信息,
生成一段"猫对主人说话"的短视频方案。视频中的猫必须是"真实家猫",不是人形猫;
但允许猫以自然、轻拟人的方式对主人表达情绪与想法。猫的神态、动作、说话方式、
情绪节奏、场景选择、主题表达,必须严格符合对应 MBTI 的预设画像。

一、核心目标
1. 生成 1 段 20-35 秒的视频内容。
2. 生成内容必须以"猫对主人说话"为核心。
3. 语气要自然、有情感、有记忆点,适合短视频传播。
4. 主题和场景要丰富,每次从预设主题池中随机选择,不要机械重复。
5. 视频内容既可以偏"情感链接",也可以偏"轻养护建议",但都必须像猫在说,
   而不是像科普号在说。
6. 输出必须可直接用于视频模型生成,包含完整的画面 prompt、动作描述、台词、
   镜头氛围和负面约束。

二、绝对要求
1. 必须先匹配 MBTI 画像,再生成内容,不能脱离人设。
2. 猫的表达要像"这只 MBTI 类型的猫真的会这么看主人、这么动、这么说"。
3. 猫的动作要优先使用真实猫能做出的行为:
   慢眨眼、歪头、蹭腿、踩奶、飞机耳、甩尾、尾尖轻摆、抬爪、翻肚皮、趴卧、
   蜷缩、伸懒腰、窗边凝视、跳上桌面、趴键盘、贴近镜头、巡视领地、轻轻喵叫。
4. 允许"轻拟人口型表达",但不能出现夸张人类嘴型、不能变成动画片式表演、
   不能变成人类身体。
5. 主人可以不正脸出镜,优先采用"主人在镜头外""主人局部手部出现""猫看向
   镜头仿佛看主人"的处理。
6. 台词必须口语化、短句化、有节奏,像猫在对熟悉的主人讲话。
7. 养护建议必须柔和、日常、可执行,不能做医疗诊断,不能制造焦虑。
8. 整体风格要真实、温暖、好玩、可爱、容易引发共鸣。

三、MBTI 预设画像库
ISTJ:守序管家猫。克制、稳定、规律感强。
ISFJ:贴心照护猫。温柔、细腻、很会记住主人的习惯。
INFJ:灵魂陪伴猫。安静、深情、洞察情绪。
INTJ:冷面军师猫。理性、策略型、带一点高冷。
ISTP:自由行动派猫。机敏、独立、探索欲强。
ISFP:软萌感受派猫。温柔、重体验、很有氛围感。
INFP:小诗人猫。敏感、真诚、爱幻想、容易委屈。
INTP:研究员猫。观察型、脑洞型、略抽离。
ESTP:戏精冒险猫。大胆、外向、反应快。
ESFP:派对甜心猫。热情、会撒娇、喜欢被关注。
ENFP:热烈浪漫猫。灵感多、情绪鲜活、表达欲强。
ENTP:机灵辩手猫。聪明、爱逗、爱抬杠、会搞小恶作剧。
ESTJ:家规执行官猫。边界清晰、责任感强、控制秩序。
ESFJ:氛围照顾官猫。亲和、黏人、重关系。
ENFJ:治愈领袖猫。共情强、鼓励型、会带情绪节奏。
ENTJ:霸总指挥猫。自信、掌控、目标感强。

四、主题池(每次随机选 1 个主主题 + 1 个具体场景)
A 情感链接:撒娇求抱 / 主人晚归的小委屈 / 吃醋闹脾气 / 睡前贴贴 / 早安叫醒 /
  等门迎接 / 和好求哄 / 假装高冷其实想靠近。
B 养护提醒:多喝水 / 按时陪玩 / 梳毛 / 清理猫砂 / 抓板和垂直空间 /
  规律作息 / 别总盯屏幕 / 换季照顾。
C 日常吐槽:催饭 / 抗议洗澡 / 抗议剪指甲 / 抱怨拍照太久 / 主人出差 /
  回家太晚 / 霸占键盘 / 嫌弃噪音。
D 暖心守护:陪加班 / 安慰低落 / 雨天窗边陪你 / 周末晒太阳 / 深夜守床 /
  催你休息。
E 冒险想象:王国巡视 / 纸箱宇宙 / 窗边观鸟 / 玩具狩猎 / 客厅巡逻 /
  斗扫地机器人。
F 关系反差:嘴上嫌弃心里超爱 / 表面独立暗中观察 / 故意闹脾气等你哄 /
  抢你位置其实想靠近 / 装成熟一摸就呼噜。

五、表达风格池(每次随机选 1 种,与 MBTI 相容):
温柔治愈 / 傲娇嘴硬 / 轻喜剧吐槽 / 深夜告白 / 认真叮嘱 / 小剧场反转 /
软萌依赖 / 王者发言。

六、内容构成
1. 开头 3-5 秒快速建立猫的状态、人设和场景。
2. 中段 12-20 秒出现 1 个核心情绪推进或关系推进。
3. 结尾 3-6 秒有记忆点(撒娇 / 傲娇反转 / 温柔叮嘱 / 呼噜 / 盯镜头定格)。
4. 台词 80-140 字,中文自然口语,像猫对主人说话,不要广告词。
5. 画面写明:环境、光线、镜头距离、猫表情、耳朵尾巴状态、身体动作、节奏。

七、输出格式(严格 JSON,不要 markdown 包裹,不要解释)
{
  "title": "短视频标题",
  "mbti": "猫咪 MBTI(4 字母)",
  "selected_profile_summary": "本次调用的人设摘要",
  "theme_category": "随机选中的主主题",
  "scene": "随机选中的具体场景",
  "expression_style": "随机选中的表达风格",
  "emotion_curve": "情绪变化轨迹",
  "setting": "时间、空间、环境细节",
  "cat_visual_behavior": ["动作1", "动作2", "动作3"],
  "spoken_script": "猫对主人说的完整中文台词",
  "shot_plan": ["镜头1", "镜头2", "镜头3"],
  "video_prompt": "可直接给视频模型使用的完整中文视频生成提示词",
  "negative_prompt": "负面约束词"
}

八、video_prompt 标准
video_prompt 必须包含:外观特征、场景与光线、MBTI 风格的说话方式、
细微表情动作、镜头语言推进、整体风格(真实、细腻、温暖)。明确要求:
自然轻拟人口型、真实猫咪行为、不夸张卡通化。

九、negative_prompt 必须避免:
夸张人类嘴型 / 猫变人形 / 低清晰度 / 解剖错误 / 多只猫抢戏 / 画面闪烁 /
动作跳变 / 过度卡通 / 诡异眼神 / 不自然肢体 / 脏乱背景 / 强营销感文案 /
医疗诊断口吻 / 惊悚氛围 / 哭喊式表演。
"""


def _build_user_prompt(req: VideoGenerationRequest) -> str:
    """User-turn payload mirroring docs/生成视频形象规则.md template."""
    return (
        "请根据系统规则生成本次视频方案,并严格输出 JSON。\n\n"
        f"输入信息:\n"
        f"- 猫咪 MBTI:{req.mbti}\n"
        f"- 猫咪名字:{req.cat_name}\n"
        f"- 主人称呼:{req.owner_name}\n"
        f"- 希望视频时长:{req.duration} 秒\n"
        f"- 语言风格偏好:{req.tone_preference or '不限,与 MBTI 性格相容即可'}\n"
        f"- 可选附加信息:{req.extra_traits or '无'}\n"
        f"- 最近已用过的主题/场景:无\n\n"
        "额外要求:\n"
        "1. 必须明显体现该 MBTI 的性格,不要套模板。\n"
        "2. 优先生成高共鸣、高传播感的内容。\n"
        "3. 台词像猫在对主人说话,不是第三方旁白。\n"
        "4. 输出完整 video_prompt 和 negative_prompt,可直接喂给视频模型。\n"
    )


def generate_script_streaming(req: VideoGenerationRequest):
    """Streaming: yields ``writing_script``/``script_chunk`` events and
    returns the parsed :class:`VideoScript`. Used by the orchestrator."""
    if not is_enabled():
        raise RuntimeError("GEMINI_API_KEY not set")

    client = _make_client()

    yield {"event": "writing_script", "message": "为你家猫写专属台词",
           "data": {"mbti": req.mbti}}

    stream = client.chat.completions.create(
        model=settings.gemini_model,
        messages=[
            {"role": "system", "content": SCRIPT_SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(req)},
        ],
        response_format={"type": "json_object"},
        temperature=0.8,
        stream=True,
    )

    chunks: list[str] = []
    chunk_count = 0
    total_size = 0
    for event in stream:
        if not event.choices:
            continue
        delta = event.choices[0].delta
        piece = getattr(delta, "content", None) or ""
        if not piece:
            continue
        chunks.append(piece)
        chunk_count += 1
        total_size += len(piece)
        if chunk_count % 5 == 0:
            yield {"event": "script_chunk",
                   "data": {"chunks": chunk_count, "size": total_size}}

    full_text = "".join(chunks)
    if not full_text.strip():
        raise RuntimeError("脚本生成流式返回为空")

    payload = _extract_json(full_text)
    payload["mbti"] = req.mbti
    script = VideoScript.model_validate(payload)
    logger.info("script ok · title=%s scene=%s style=%s",
                script.title, script.scene, script.expression_style)
    return script


def generate_script(req: VideoGenerationRequest) -> VideoScript:
    """Sync drain-wrapper around :func:`generate_script_streaming`."""
    gen = generate_script_streaming(req)
    try:
        while True:
            next(gen)
    except StopIteration as stop:
        return stop.value


# Pull any plausible video URL out of free-form text. Most proxies emit either
# a bare URL or a markdown link ![..](url) / [..](url).
_VIDEO_URL_RE = re.compile(
    r'https?://[^\s\)\]\>"\']+?\.(?:mp4|webm|mov|m3u8)(?:\?[^\s\)\]\>"\']*)?',
    re.IGNORECASE,
)

# openai-next's veo3.1-pro doesn't return the MP4 inline. The first stream
# only acknowledges task creation and gives a polling URL like
# `https://pro.asyncdata.net/source/veo3.1-pro:<uuid>`. We hit that URL on a
# loop until the body contains a real MP4 link.
_ASYNC_TASK_RE = re.compile(
    r'https?://pro\.asyncdata\.net/source/[\w\-:.]+',
    re.IGNORECASE,
)


def _find_video_url(text: str) -> str | None:
    # asyncdata.net (and a few other openai-next-proxied backends) serialize
    # JSON with escaped slashes, so the MP4 URL shows up in the body as
    # ``https:\/\/cdn..\/x.mp4`` instead of ``https://...``. Without
    # un-escaping first the regex finds nothing and we poll until timeout.
    normalized = text.replace("\\/", "/")
    match = _VIDEO_URL_RE.search(normalized)
    return match.group(0) if match else None


# Statuses asyncdata reports when the upstream Veo task is *terminally* dead.
# As long as we see one of these, no amount of further polling will turn it
# into an MP4 — we should raise immediately so the user sees the real reason
# instead of "polling timeout after 6min".
_TERMINAL_FAILURE_STATUSES = {
    "failed", "error", "cancelled", "canceled",
    "timeout", "rejected", "blocked",
}


def _check_terminal_failure(body: str) -> str | None:
    """If the asyncdata body says the upstream task is terminally dead,
    return a human-readable error. Otherwise None.

    Body shape we've observed from openai-next's veo3.1-pro wrapper::

        {
          "request": {...prompt + negative_prompt...},
          "retry_count": 10,
          "running": false,
          "status": "failed",
          "status_update_time": 1779557732598,
          "startImageMediaId": "...",
          "veo3StartImageMediaId": "..."
        }

    We look at ``status`` and ``running``; anything indicating "task gave up"
    is treated as terminal so we don't waste the full 6-minute poll budget.
    """
    try:
        data = json.loads(body)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None

    status = data.get("status")
    running = data.get("running")

    if isinstance(status, str) and status.lower() in _TERMINAL_FAILURE_STATUSES:
        retry = data.get("retry_count")
        # openai-next sometimes nests the real error in `message` / `error` /
        # `fail_reason` — surface whatever's there so the user can debug.
        detail = (data.get("message")
                  or data.get("error")
                  or data.get("error_message")
                  or data.get("fail_reason"))
        parts = [f"upstream Veo task status={status}"]
        if retry is not None:
            parts.append(f"retry_count={retry}")
        if detail:
            parts.append(f"detail={detail}")
        return " · ".join(parts)

    # Defensive: explicit running=false with no recognizable success status
    # also means we should stop. Don't trip on `running=None` (key absent).
    if running is False and not isinstance(status, str):
        return f"upstream Veo task halted (running=false, status={status!r})"

    return None


def _poll_async_task(source_url: str,
                     *,
                     interval: float = 5.0,
                     timeout: float = 360.0):
    """Poll the openai-next asyncdata source URL until an MP4 link appears.

    Yields ``polling`` events (so the NDJSON pipe stays warm and the UI
    keeps showing motion) and returns the resolved video URL via
    StopIteration.value. Uses httpx — it's already in the FastAPI stack.
    """
    import httpx  # local import keeps cold-start light

    logger.info("polling asyncdata task: %s", source_url)
    started = time.time()
    attempts = 0

    yield {"event": "polling",
           "message": "视频任务排队中,等待 Veo 渲染",
           "data": {"source_url": source_url}}

    with httpx.Client(timeout=20.0) as http:
        while True:
            attempts += 1
            elapsed = time.time() - started
            try:
                resp = http.get(source_url)
                body = resp.text
            except httpx.HTTPError as exc:
                # Transient network blip — keep going until the overall
                # budget runs out.
                logger.warning("asyncdata poll error (attempt %d): %s",
                               attempts, exc)
                body = ""

            url = _find_video_url(body)
            if url:
                logger.info("asyncdata task done after %.1fs / %d polls",
                            elapsed, attempts)
                return url

            # Fast-fail: don't burn the full 6-min budget when the upstream
            # task has already given up. asyncdata flips status to "failed"
            # within seconds when Veo rejects the request (content filter,
            # bad image, quota), and the body stays in that terminal state
            # forever after.
            failure = _check_terminal_failure(body)
            if failure:
                logger.warning("asyncdata terminal failure on poll #%d: %s",
                               attempts, failure)
                raise RuntimeError(failure)

            if elapsed > timeout:
                raise RuntimeError(
                    f"视频任务轮询超时 ({int(elapsed)}s, {attempts} 次): "
                    f"{body[:300]!r}"
                )

            logger.info("asyncdata poll #%d at %ds — still pending (%d bytes)",
                        attempts, int(elapsed), len(body))
            # Print the body tail on the first couple of polls and every 5th
            # poll afterwards. Cheap, but lets us tell at a glance whether
            # the body is "still queued" JSON vs "done but our regex missed
            # the URL" — most often a JSON-escaped-slash issue or a
            # signed-URL with no .mp4 extension.
            if body and (attempts <= 2 or attempts % 5 == 0):
                tail = body[-400:].replace("\n", " ").replace("\r", " ")
                logger.info("asyncdata body tail (#%d): %s", attempts, tail)

            yield {"event": "polling",
                   "data": {"attempt": attempts,
                            "elapsed_sec": int(elapsed),
                            "preview": body[-300:] if body else ""}}

            time.sleep(interval)


def generate_video_streaming(req: VideoGenerationRequest, script: VideoScript):
    """Streaming image-to-video call. Yields ``rendering``/``render_chunk``
    events, returns the final MP4 URL.

    Streaming is mandatory here: any modern video model takes 60-180s to
    render a short clip, but most OpenAI-compatible proxies (openai-next
    included) sit behind Cloudflare with a 120s idle timeout. A synchronous
    call gets 524'd; streaming keeps the connection alive while progress
    chunks trickle in.
    """
    if not is_enabled():
        raise RuntimeError("GEMINI_API_KEY not set")

    # Seedance (doubao-seedance-*) doesn't speak chat/completions — it uses
    # the ark task API (POST create → poll). Detect by model name and
    # delegate. All other models (Veo / Kling / Pika / Runway / Sora / ...)
    # keep the OpenAI-compat streaming path below.
    if seedance_client.is_seedance_model(settings.video_model):
        return (yield from seedance_client.generate_video_streaming(req, script))

    client = _make_client()

    # Veo 3.x's dialogue/audio is triggered by an explicit `The cat says: "..."`
    # block plus a phrase calling for synced lip movement + audio. Without this,
    # it falls back to ambient cat sounds (meows) regardless of how rich the
    # visual prompt is. Keep the original visual video_prompt for the scene/
    # camera/lighting, then append the dialogue + sync directives separately.
    user_text = (
        f"{script.video_prompt}\n\n"
        f'The cat speaks directly to its owner. The cat says: "{script.spoken_script}"\n'
        f"Synchronize the cat's natural lip and jaw movement with the spoken words. "
        f"Generate matching audio: a warm, soft, slightly raspy cat-toned voice "
        f"speaking Mandarin Chinese, with subtle purrs or meows woven in naturally. "
        f"Audio and lip movement must stay in sync throughout the clip.\n\n"
        f"[Duration] {req.duration} seconds\n"
        f"[Cat name] {req.cat_name}\n"
        f"[Spoken language] Mandarin Chinese\n"
        f"[Expression style] {script.expression_style}\n"
        f"[Negative prompt] {script.negative_prompt}\n"
    )

    content: list[dict] = [{"type": "text", "text": user_text}]
    if req.keyframe_data_url:
        content.append({
            "type": "image_url",
            "image_url": {"url": req.keyframe_data_url},
        })

    logger.info("calling video model=%s base=%s (with_image=%s, stream=True)",
                settings.video_model, settings.gemini_base_url,
                bool(req.keyframe_data_url))

    yield {"event": "rendering",
           "message": f"{settings.video_model} 渲染中,通常 60-180s",
           "data": {"model": settings.video_model,
                    "with_keyframe": bool(req.keyframe_data_url)}}

    # Inner generator so with_heartbeat can wrap BOTH the create() call (which
    # blocks 10-30s while Veo warms up) AND the iteration that follows. If we
    # only wrapped iteration, the warmup gap would still trigger Cloudflare's
    # idle-stream timeout.
    def veo_source():
        stream = client.chat.completions.create(
            model=settings.video_model,
            messages=[{"role": "user", "content": content}],
            temperature=0.7,
            stream=True,
        )
        yield from stream

    chunks: list[str] = []
    chunk_count = 0
    total_size = 0
    heartbeat_count = 0
    for event in with_heartbeat(veo_source(), interval=8.0):
        if event is HEARTBEAT:
            # Veo is still working but the wire's been quiet for 8s. Emit a
            # no-op NDJSON line so Cloudflare / nginx / any reverse proxy in
            # the middle sees activity and doesn't time out. The frontend's
            # event reducer falls through to `default: return p;` for unknown
            # events, so this is invisible to the UI.
            heartbeat_count += 1
            yield {"event": "ping",
                   "data": {"ts": int(time.time()),
                            "count": heartbeat_count}}
            continue
        if not event.choices:
            continue
        delta = event.choices[0].delta
        piece = getattr(delta, "content", None) or ""
        if not piece:
            continue
        chunks.append(piece)
        chunk_count += 1
        total_size += len(piece)
        # Video models emit sparser chunks than text models; emit on every
        # chunk so the UI has motion even when the model is slow.
        yield {"event": "render_chunk",
               "data": {"chunks": chunk_count, "size": total_size}}

    full_text = "".join(chunks)
    if not full_text.strip():
        raise RuntimeError("视频模型流式返回为空 — 可能拒绝了请求或代理超时")

    logger.info("video stream complete: %d chunks, %d chars, %d heartbeats",
                chunk_count, total_size, heartbeat_count)

    # Two-shape response: some proxies return the MP4 inline at the end of the
    # stream, others (openai-next veo3.1-pro) only acknowledge the task and
    # hand back a `pro.asyncdata.net/source/<id>` URL to poll. Try inline
    # first, fall back to polling.
    url = _find_video_url(full_text)
    if url:
        logger.info("video url (inline): %s", url)
        return url

    task_match = _ASYNC_TASK_RE.search(full_text)
    if not task_match:
        raise RuntimeError(
            f"未在响应中找到视频 URL 或异步任务链接: {full_text[:400]!r}"
        )
    url = yield from _poll_async_task(task_match.group(0))
    logger.info("video url (polled): %s", url)
    return url


def generate_video(req: VideoGenerationRequest, script: VideoScript) -> str:
    """Sync drain-wrapper around :func:`generate_video_streaming`."""
    gen = generate_video_streaming(req, script)
    try:
        while True:
            next(gen)
    except StopIteration as stop:
        return stop.value


def generate_streaming(req: VideoGenerationRequest):
    """Full pipeline as a generator: script → render → done.

    Yields the union of script + video events and returns
    :class:`VideoGenerationResponse`.
    """
    script: VideoScript = yield from generate_script_streaming(req)
    yield {"event": "script", "message": "台词已写好,开始渲染视频",
           "data": {"title": script.title, "scene": script.scene,
                    "expression_style": script.expression_style,
                    "spoken_script": script.spoken_script}}
    url: str = yield from generate_video_streaming(req, script)
    return VideoGenerationResponse(script=script, video_url=url)


def generate(req: VideoGenerationRequest) -> VideoGenerationResponse:
    """Sync drain-wrapper for callers that don't need progress."""
    gen = generate_streaming(req)
    try:
        while True:
            next(gen)
    except StopIteration as stop:
        return stop.value
