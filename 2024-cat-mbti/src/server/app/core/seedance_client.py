"""Async-task client for ByteDance Volcengine ark (Seedance / doubao-seedance-*).

Seedance does NOT speak the OpenAI chat/completions protocol, so the existing
``video_gen.py`` path (which uses ``client.chat.completions.create(stream=True)``)
hits 404 on the proxy. This module talks to the real ark task API exposed via
openai-next's ``/seedance/api/v3/...`` path.

Flow:
1. ``POST /contents/generations/tasks`` with ``{model, content:[text+image], ...}``
   → returns ``{id: "task_xxx", status: "queued"}``.
2. Poll ``GET /contents/generations/tasks/{id}`` every 5s until ``status``
   becomes ``"succeeded"`` (``content.video_url`` is then the MP4 URL,
   signed TOS) or ``"failed"`` (``error`` carries the reason).

The yielded events match ``video_gen.generate_video_streaming``'s shape so the
job state machine and frontend UI work without changes.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Iterator

import httpx

from app.core.config import settings
from app.models.schemas import VideoGenerationRequest, VideoScript

logger = logging.getLogger(__name__)


def is_seedance_model(model: str) -> bool:
    """Decide whether to route this model through the ark task API.

    Names like ``doubao-seedance-2-0-260128`` / ``doubao-seedance-2-0-fast-260128``
    all use the task-based API. Anything else (Veo / Kling / Pika / Sora / ...)
    keeps using OpenAI chat/completions.
    """
    return model.lower().startswith("doubao-seedance")


def _build_content(req: VideoGenerationRequest, script: VideoScript) -> list[dict]:
    """Map our existing VideoScript onto Seedance's ``content`` array.

    Seedance accepts a text block + 0-N image_url blocks. We pass the keyframe
    with ``role: "first_frame"`` so it's used as the starting frame of the
    generated clip (image-to-video), matching how Veo uses the same keyframe.

    Negative prompts are appended to the text body with the ``--np`` token —
    Seedance's documented way of expressing them inline. Audio is requested via
    the top-level ``generate_audio=True`` instead of inline directives because
    Seedance ignores Veo-style "[Audio] ..." prose blocks.
    """
    text = (
        f"{script.video_prompt}\n\n"
        f'猫对主人说:"{script.spoken_script}"\n'
        f"猫嘴部自然口型与台词同步,声音温暖、轻微沙哑的猫咪音色,"
        f"普通话,中间穿插自然的呼噜或喵叫。\n\n"
        f"[时长] {req.duration} 秒\n"
        f"[猫名] {req.cat_name}\n"
        f"[语言] 普通话\n"
        f"[风格] {script.expression_style}\n"
        f"--np {script.negative_prompt}"
    )

    content: list[dict] = [{"type": "text", "text": text}]
    if req.keyframe_data_url:
        content.append({
            "type": "image_url",
            "image_url": {"url": req.keyframe_data_url},
            "role": "first_frame",
        })
    return content


def _create_task(req: VideoGenerationRequest, script: VideoScript) -> str:
    """POST a new generation task. Returns the task_id on success."""
    url = f"{settings.seedance_base_url.rstrip('/')}/contents/generations/tasks"
    body = {
        "model": settings.video_model,
        "content": _build_content(req, script),
        # 9:16 matches the portrait frame the frontend renders into.
        # Seedance 2.0 supports 5/8/10/12s; 8s aligns with the existing default.
        "ratio": "9:16",
        "duration": req.duration,
        "generate_audio": True,
        # Demo content shouldn't carry a vendor watermark.
        "watermark": False,
    }
    logger.info("creating seedance task: model=%s duration=%s with_image=%s",
                settings.video_model, req.duration, bool(req.keyframe_data_url))
    r = httpx.post(
        url,
        headers={
            "Authorization": f"Bearer {settings.gemini_api_key}",
            "Content-Type": "application/json",
        },
        content=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        timeout=httpx.Timeout(connect=settings.gemini_connect_timeout,
                              read=60.0, write=settings.gemini_write_timeout,
                              pool=10.0),
    )
    if r.status_code >= 400:
        # Try to surface the upstream's error body verbatim so the UI shows the
        # real reason ("无可用渠道", quota exceeded, ...) instead of "生成失败".
        raise RuntimeError(f"create task failed: {r.status_code} {r.text[:400]}")

    payload = r.json()
    task_id = payload.get("id") or payload.get("task_id")
    if not task_id:
        raise RuntimeError(f"create task returned no id: {payload!r}")
    logger.info("seedance task created: %s (initial status=%s)",
                task_id, payload.get("status"))
    return task_id


# Terminal statuses we've observed from the ark API. Anything else (queued /
# processing / running / ...) means keep polling.
_TERMINAL_SUCCESS = {"succeeded", "success"}
_TERMINAL_FAILURE = {"failed", "error", "cancelled", "canceled", "timeout"}


def _poll_task(task_id: str,
               *,
               interval: float = 5.0,
               timeout: float = 900.0) -> Iterator[dict[str, Any]]:
    """Poll until the task reaches a terminal status. Yields ``polling``
    progress events; on success yields a final ``done`` dict carrying the
    video URL (caller picks that up to break the loop).
    """
    url = f"{settings.seedance_base_url.rstrip('/')}/contents/generations/tasks/{task_id}"
    started = time.time()
    attempts = 0

    with httpx.Client(timeout=20.0) as http:
        while True:
            attempts += 1
            elapsed = time.time() - started
            try:
                resp = http.get(
                    url,
                    headers={"Authorization": f"Bearer {settings.gemini_api_key}"},
                )
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPError as exc:
                # Transient blip — keep going until the overall budget elapses.
                logger.warning("seedance poll error (attempt %d): %s", attempts, exc)
                data = {}

            status = (data.get("status") or "").lower()

            if status in _TERMINAL_SUCCESS:
                # Success payload looks like:
                #   {"status":"succeeded", "content":{"video_url":"https://..."}, ...}
                content = data.get("content") or {}
                video_url = content.get("video_url") or data.get("video_url")
                if not video_url:
                    raise RuntimeError(
                        f"seedance succeeded but no video_url: {data!r}"
                    )
                logger.info("seedance task done after %.1fs / %d polls",
                            elapsed, attempts)
                yield {"_done": True, "video_url": video_url}
                return

            if status in _TERMINAL_FAILURE:
                err = data.get("error") or {}
                msg = err.get("message") if isinstance(err, dict) else str(err)
                raise RuntimeError(
                    f"seedance task {status}: {msg or json.dumps(data)[:300]}"
                )

            if elapsed > timeout:
                raise RuntimeError(
                    f"seedance task timed out at {int(elapsed)}s "
                    f"(last status={status!r}, {attempts} polls)"
                )

            logger.info("seedance poll #%d at %ds — status=%s",
                        attempts, int(elapsed), status or "?")
            preview = json.dumps(data)[:300] if data else ""
            yield {
                "event": "polling",
                "data": {
                    "attempt": attempts,
                    "elapsed_sec": int(elapsed),
                    "preview": preview,
                },
            }
            time.sleep(interval)


def generate_video_streaming(req: VideoGenerationRequest, script: VideoScript):
    """Generator: yields the same shape of progress events as
    ``video_gen.generate_video_streaming`` and returns the MP4 URL via
    ``StopIteration.value``."""
    logger.info("calling seedance model=%s base=%s",
                settings.video_model, settings.seedance_base_url)
    yield {"event": "rendering",
           "message": f"{settings.video_model} 渲染中,通常 60-180s",
           "data": {"model": settings.video_model,
                    "with_keyframe": bool(req.keyframe_data_url)}}

    task_id = _create_task(req, script)
    yield {"event": "polling",
           "message": "视频任务排队中,等待 Seedance 渲染",
           "data": {"task_id": task_id, "attempt": 0, "elapsed_sec": 0}}

    video_url: str = ""
    for ev in _poll_task(task_id):
        if ev.get("_done"):
            video_url = ev["video_url"]
            break
        yield ev

    if not video_url:
        raise RuntimeError("seedance polling exited without a video URL")

    logger.info("seedance video url: %s", video_url[:120] + "...")
    return video_url
