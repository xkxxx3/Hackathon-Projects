from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.core.mbti import build_report_streaming
from app.core.video_frames import extract_frames
from app.models.schemas import AnalyzeResponse

logger = logging.getLogger(__name__)
router = APIRouter()


def _ndjson(obj: dict) -> bytes:
    """Serialize one event as a newline-terminated JSON line."""
    return (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")


@router.post("/analyze")
async def analyze(video: UploadFile = File(...)) -> StreamingResponse:
    """Stream MBTI analysis progress as NDJSON.

    The frontend reads this with fetch + ReadableStream, parses each line, and
    drives a live step indicator. The terminal event is either
    ``{event:"done", data: AnalyzeResponse}`` or ``{event:"error", ...}``.
    """
    if video.content_type and not video.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="请上传视频文件")

    analysis_id = uuid.uuid4().hex
    suffix = Path(video.filename or "upload.mp4").suffix or ".mp4"
    saved_path = settings.upload_dir / f"{analysis_id}{suffix}"

    # Drain the upload into a temp file BEFORE the generator starts — we need
    # `await video.read()`, and StreamingResponse generators run sync in a
    # threadpool. Easier to consume the multipart here, then hand a Path off.
    size = 0
    max_bytes = settings.max_upload_mb * 1024 * 1024
    with saved_path.open("wb") as f:
        while chunk := await video.read(1024 * 1024):
            size += len(chunk)
            if size > max_bytes:
                saved_path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="视频过大")
            f.write(chunk)

    def event_stream():
        try:
            yield _ndjson({"event": "uploaded",
                           "message": "视频已上传",
                           "data": {"size_kb": size // 1024}})

            try:
                bundle = extract_frames(saved_path)
            except Exception as exc:  # noqa: BLE001 — frame extract failed
                logger.exception("frame extraction failed")
                bundle = None
                yield _ndjson({"event": "warn",
                               "message": f"抽帧失败,走 stub 模式: {exc}"})
            else:
                yield _ndjson({"event": "frames",
                               "message": f"等距抽 {len(bundle.frames)} 帧完成",
                               "data": {"frame_count": len(bundle.frames),
                                        "duration_sec": bundle.duration_sec}})

            # Drive the MBTI sub-generator and forward each event onto the wire.
            report_gen = build_report_streaming(bundle, seed_hint=analysis_id)
            try:
                while True:
                    ev = next(report_gen)
                    yield _ndjson(ev)
            except StopIteration as stop:
                report = stop.value

            keyframe = bundle.keyframe() if bundle else ""
            response = AnalyzeResponse(
                analysis_id=analysis_id,
                report=report,
                keyframe_data_url=keyframe,
            )
            yield _ndjson({"event": "done",
                           "data": response.model_dump(mode="json")})
        except Exception as exc:  # noqa: BLE001 — surface anything else
            logger.exception("analyze stream crashed")
            body = getattr(exc, "body", None)
            yield _ndjson({
                "event": "error",
                "message": str(exc),
                "data": {"exception": type(exc).__name__,
                         "upstream_status": getattr(exc, "status_code", None),
                         "upstream_body": body},
            })
        finally:
            try:
                saved_path.unlink(missing_ok=True)
            except OSError:
                logger.warning("failed to delete %s", saved_path, exc_info=True)

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        # Defeat proxy buffering. Cloudflare's quick tunnels (and most CDNs)
        # buffer responses they don't recognize as streaming; without these
        # headers the client sees 30-120s of nothing, then the whole NDJSON
        # blob arrives at once. `X-Accel-Buffering: no` is the lingua-franca
        # "don't buffer" hint that nginx + Cloudflare + most reverse proxies
        # honor. `no-transform` forbids gzip recompression in transit.
        headers={
            "Cache-Control": "no-cache, no-store, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
