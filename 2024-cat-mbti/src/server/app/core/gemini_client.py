"""Calls a Gemini-via-OpenAI-compatible-proxy endpoint to score cat behavior.

The proxy speaks OpenAI chat completions (not Google's native Gemini API), so:
1. We extract N JPEG frames from the video (chat completions can't take video).
2. Send frames as `image_url` content blocks alongside the prompt.
3. Ask for JSON output via `response_format={"type": "json_object"}` —
   `json_schema` strict mode is unreliable across third-party proxies, so we
   inline the schema in the prompt and validate with Pydantic on parse.

Signals → MBTI judgement happens downstream in core.mbti, by design (see
docs/喵格MBTI映射规则.md). This module only describes what's in the video.
"""
from __future__ import annotations

import json
import logging
import re
import time

from app.core.config import settings
from app.core.signals import BehaviorSignals
from app.core.streaming_helpers import HEARTBEAT, with_heartbeat
from app.core.video_frames import FrameBundle

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """\
你是猫咪行为分析师。我会给你从一段 10–30 秒猫咪短视频中等距抽取的 N 张帧图像,
每张图像前面会用文字标出它在视频中的时间戳(如 "Frame 3 @ 7.5s")。
请逐项打分文档定义的行为信号,严格按 JSON schema 输出。

**规则**
1. 每个信号字段是整数 0–3:0 = 视频中未观察到,1 = 轻微迹象,2 = 明显,3 = 强烈。
2. 不要做 MBTI 判定,只如实描述观察到的行为强度。
3. 对每个维度(ei/sn/tf/jp)给出 0–1 的 confidence:抽帧画面是否足以支撑该维度判定。
4. **highlights 字段填 2–3 条**:每条 {"time_sec": 数字, "caption": "一句话描述"},
   time_sec 必须是上面图像标注的真实时间戳之一,caption 描述当时画面发生了什么。
5. notes 字段可以空,留作兜底。
6. **只输出 JSON,不要 markdown 代码块包裹,不要任何解释文字。**

**信号说明**

E/I 维度(社交性 / 外部刺激反应):
- approach_camera_or_person, excited_to_stimuli, hide_from_stimuli
- vocal_frequent, vocal_silent
- wide_exploration, stay_in_corner
- enjoy_petting, avoid_petting

S/N 维度(注意力对象):
- direct_pounce, observe_before_act
- chases_invisible (追逐影子/空气)
- short_staring, long_staring_distant
- sniff_new_object, observe_new_object_from_distance
- repetitive_behavior

T/F 维度(情绪表达):
- nuzzle_frequent, nuzzle_rare
- self_play_when_ignored, meow_when_ignored
- long_eye_contact, short_eye_contact
- alone_adapts_well, alone_distressed
- emotional_reactions

J/P 维度(规律性 / 突发性,短视频中可能信息不足):
- fixed_sleep_location, random_sleep_location
- regular_meal_time, irregular_meal_time
- long_term_toy_preference, novelty_seeking_toys
- sensitive_to_env_change, indifferent_to_env_change
- few_sudden_bursts, many_sudden_bursts

**输出 JSON 字段示意(所有字段必填,数值范围如上)**:
{
  "approach_camera_or_person": 0, "excited_to_stimuli": 0, "hide_from_stimuli": 0,
  "vocal_frequent": 0, "vocal_silent": 0, "wide_exploration": 0,
  "stay_in_corner": 0, "enjoy_petting": 0, "avoid_petting": 0,
  "direct_pounce": 0, "observe_before_act": 0, "chases_invisible": 0,
  "short_staring": 0, "long_staring_distant": 0, "sniff_new_object": 0,
  "observe_new_object_from_distance": 0, "repetitive_behavior": 0,
  "nuzzle_frequent": 0, "nuzzle_rare": 0, "self_play_when_ignored": 0,
  "meow_when_ignored": 0, "long_eye_contact": 0, "short_eye_contact": 0,
  "alone_adapts_well": 0, "alone_distressed": 0, "emotional_reactions": 0,
  "fixed_sleep_location": 0, "random_sleep_location": 0,
  "regular_meal_time": 0, "irregular_meal_time": 0,
  "long_term_toy_preference": 0, "novelty_seeking_toys": 0,
  "sensitive_to_env_change": 0, "indifferent_to_env_change": 0,
  "few_sudden_bursts": 0, "many_sudden_bursts": 0,
  "confidence_ei": 0.5, "confidence_sn": 0.5,
  "confidence_tf": 0.5, "confidence_jp": 0.5,
  "highlights": [
    {"time_sec": 3.5, "caption": "猫主动凑到镜头前蹭手"},
    {"time_sec": 12.0, "caption": "扑向逗猫棒"}
  ],
  "notes": ""
}
"""


def is_enabled() -> bool:
    return bool(settings.gemini_api_key)


def _make_client():
    """Build an OpenAI client tuned for the Chinese-proxy + local-VPN scenario.

    - Long-ish timeouts: vision payloads (~1MB of base64 images) can be slow.
    - ``trust_env`` toggle: when False, ignore HTTP_PROXY / HTTPS_PROXY env
      vars. Useful because openai-next is in China; routing through a local
      Clash/V2Ray often makes TLS handshake flaky for large requests.
    """
    from openai import OpenAI
    import httpx

    timeout = httpx.Timeout(
        connect=settings.gemini_connect_timeout,
        read=settings.gemini_read_timeout,
        write=settings.gemini_write_timeout,
        pool=10.0,
    )
    http_client = httpx.Client(
        timeout=timeout,
        trust_env=settings.gemini_use_system_proxy,
    )
    return OpenAI(
        api_key=settings.gemini_api_key,
        base_url=settings.gemini_base_url,
        http_client=http_client,
        max_retries=2,
    )


def ping() -> dict:
    """Smallest possible round-trip to verify auth + model + quota.

    Used by ``GET /api/llm/ping`` — no video, no vision, just text in/out.
    Returns ``{ok: True, model, reply}`` on success or re-raises the SDK
    exception so the endpoint can surface the proxy's real error.

    Note: we deliberately do NOT set max_tokens. Gemini 2.5+/3.x have built-in
    thinking that consumes output token budget internally; a tight cap (e.g. 20)
    causes Gemini to spend the whole budget on reasoning and emit empty content,
    which the proxy surfaces as `empty_response`.
    """
    if not is_enabled():
        raise RuntimeError("GEMINI_API_KEY not set")

    client = _make_client()
    response = client.chat.completions.create(
        model=settings.gemini_model,
        messages=[{"role": "user", "content": "请回复:你好"}],
        temperature=0,
    )
    if isinstance(response, str) or not hasattr(response, "choices"):
        raise RuntimeError(f"代理返回非标响应: {response!r}"[:500])
    return {
        "ok": True,
        "base_url": settings.gemini_base_url,
        "model": settings.gemini_model,
        "reply": (response.choices[0].message.content or "").strip(),
    }


def extract_signals_streaming(bundle: FrameBundle):
    """Streaming variant: yields progress events, returns BehaviorSignals.

    Caller pattern::

        gen = extract_signals_streaming(bundle)
        for event in gen:
            ...           # ProgressEvent dicts
        # signals = gen.value is NOT how it works — use ``yield from`` to
        # capture the return value, or drain with the helper below.

    Events yielded:
        {"event": "analyzing", "message": "...", "data": {...}}
        {"event": "chunk",     "data": {"chunks": int, "size": int}}
    """
    if not is_enabled():
        raise RuntimeError("GEMINI_API_KEY not set")

    logger.info("calling %s @ %s with %d frames (duration=%.1fs)",
                settings.gemini_model, settings.gemini_base_url,
                len(bundle.frames), bundle.duration_sec)

    client = _make_client()

    user_content: list[dict] = [
        {"type": "text",
         "text": f"以下是从一段 {bundle.duration_sec:.1f} 秒猫咪视频中等距抽取的 "
                 f"{len(bundle.frames)} 张帧。每张前面标注了它在视频中的真实时间戳。"
                 f"请按规则输出 JSON,highlights 字段必须用下面这些真实时间戳。"}
    ]
    for i, fr in enumerate(bundle.frames, start=1):
        user_content.append({"type": "text", "text": f"Frame {i} @ {fr.time_sec}s:"})
        user_content.append({"type": "image_url", "image_url": {"url": fr.data_url}})

    yield {"event": "analyzing", "message": "AI 正在观察猫咪行为",
           "data": {"frame_count": len(bundle.frames),
                    "duration": bundle.duration_sec}}

    # Inner generator wraps BOTH the create() call (which blocks 10-30s while
    # Gemini ingests the multi-MB vision payload) AND the chunk iteration that
    # follows. with_heartbeat sees both warmup and inter-chunk gaps as silence
    # and emits HEARTBEAT, which we turn into a no-op `ping` NDJSON line so
    # Cloudflare's idle-stream timer never trips.
    def gemini_source():
        stream = client.chat.completions.create(
            model=settings.gemini_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            stream=True,
        )
        yield from stream

    chunks: list[str] = []
    chunk_count = 0
    total_size = 0
    heartbeat_count = 0
    for event in with_heartbeat(gemini_source(), interval=8.0):
        if event is HEARTBEAT:
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
        # Emit a progress event every 5 chunks so the UI can show real motion
        # without flooding the wire on the chatty Gemini stream.
        if chunk_count % 5 == 0:
            yield {"event": "chunk",
                   "data": {"chunks": chunk_count, "size": total_size}}

    full_text = "".join(chunks)
    if not full_text.strip():
        raise RuntimeError("Gemini 流式返回为空")

    logger.info("gemini stream complete: %d chunks, %d chars, %d heartbeats",
                chunk_count, total_size, heartbeat_count)

    payload = _extract_json(full_text)
    signals = BehaviorSignals.model_validate(payload)
    logger.info("confidence ei=%.2f sn=%.2f tf=%.2f jp=%.2f",
                signals.confidence_ei, signals.confidence_sn,
                signals.confidence_tf, signals.confidence_jp)
    return signals


def extract_signals_via_gemini(bundle: FrameBundle) -> BehaviorSignals:
    """Synchronous drain-wrapper kept for callers that don't need progress."""
    gen = extract_signals_streaming(bundle)
    try:
        while True:
            next(gen)
    except StopIteration as stop:
        return stop.value


# Some proxies still wrap JSON in ```json ... ``` despite the system prompt.
# Strip that and pick out the first balanced { ... } block.
_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def _extract_json(text: str) -> dict:
    cleaned = _FENCE_RE.sub("", text).strip()
    # Find the first { ... last }.
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise RuntimeError(f"模型未返回 JSON: {text[:200]}")
    return json.loads(cleaned[start:end + 1])
