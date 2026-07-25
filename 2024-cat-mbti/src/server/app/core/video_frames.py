"""Extract evenly-spaced frames from a video as base64 JPEG data URLs.

Why: OpenAI-compatible chat completions (used by most Chinese AI proxies that
route to Gemini) don't accept video — they accept `image_url` content with
either an HTTP URL or `data:image/...;base64,...`. We sample N frames evenly
across the clip so the model still sees the temporal arc, and we tag each
frame with its real timestamp so the model can call out moments by time.
"""
from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from pathlib import Path

import cv2

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ExtractedFrame:
    data_url: str       # "data:image/jpeg;base64,..."
    time_sec: float     # real timestamp within the video


@dataclass
class FrameBundle:
    frames: list[ExtractedFrame]
    duration_sec: float

    def keyframe(self) -> str:
        """Pick a representative frame for image-to-video generation.
        Middle frame is usually well-lit and centered for short clips."""
        if not self.frames:
            return ""
        return self.frames[len(self.frames) // 2].data_url


def extract_frames(video_path: Path, n_frames: int | None = None) -> FrameBundle:
    n = n_frames or settings.video_frame_count
    quality = settings.video_frame_jpeg_quality

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"无法打开视频: {video_path}")

    try:
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0  # fallback for broken headers
        if total <= 0:
            raise RuntimeError("视频帧数为 0,可能编码不被支持")
        duration = total / fps

        # Evenly-spaced indices; bias slightly inward to skip leading/trailing
        # black frames common in mobile recordings.
        step = total / (n + 1)
        indices = [int(step * (i + 1)) for i in range(n)]

        out: list[ExtractedFrame] = []
        for idx in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = cap.read()
            if not ok:
                logger.warning("frame %d unreadable, skipping", idx)
                continue
            ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
            if not ok:
                continue
            b64 = base64.b64encode(buf.tobytes()).decode("ascii")
            out.append(ExtractedFrame(
                data_url=f"data:image/jpeg;base64,{b64}",
                time_sec=round(idx / fps, 1),
            ))
    finally:
        cap.release()

    if not out:
        raise RuntimeError("抽帧全部失败")
    logger.info("extracted %d frames from %s (duration=%.1fs)",
                len(out), video_path.name, duration)
    return FrameBundle(frames=out, duration_sec=round(duration, 1))
