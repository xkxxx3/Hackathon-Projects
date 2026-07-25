"""In-memory job store for the two-stage video generation pipeline.

The original ``POST /api/video/generate`` held a single NDJSON stream open
for the entire 3-8 min pipeline. That works on desktop but dies on mobile
the moment the screen locks / the carrier NAT collapses the idle TCP /
the Wi-Fi roams. Splitting it into ``start`` (fire-and-forget) +
``status`` (short polling) makes the user-visible HTTP requests <1s each,
so connection lifetime stops mattering.

The pipeline itself (``core.video_gen.generate_streaming``) is unchanged
— this module just consumes its events on a background thread and stamps
the current progress into a job record keyed by ``job_id``.

Storage is in-process memory. For a hackathon demo that's fine: the
worker process is the same one the API runs in, jobs live ~5 min, and we
LRU-evict above ``MAX_JOBS``. If we ever scale to multiple workers, swap
``_jobs`` for Redis.
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Optional

from app.core import video_gen
from app.models.schemas import VideoGenerationRequest

logger = logging.getLogger(__name__)


JobStatus = Literal["running", "done", "error"]
JobPhase = Literal["script", "render", "done", "error"]


@dataclass
class JobState:
    job_id: str
    status: JobStatus = "running"
    phase: JobPhase = "script"

    # Mirror the fields the frontend's Progress shape consumes. Names use
    # snake_case so asdict() lands as plain JSON.
    script_chunks: int = 0
    script_size: int = 0
    render_chunks: int = 0
    render_size: int = 0
    poll_attempt: int = 0
    poll_elapsed_sec: int = 0
    # Last 300 chars of the asyncdata polling body. Visible through
    # GET /api/video/status/{job_id} so we can curl it to diagnose why an
    # asyncdata task isn't yielding an MP4 URL — most common cause is a
    # JSON-escaped URL or a CDN URL without an .mp4 extension.
    last_poll_preview: Optional[str] = None

    # Filled when the script-writing stage completes (preview shown under the
    # render progress card). Subset of VideoScript: title / scene /
    # expression_style / spoken_script.
    script: Optional[dict] = None

    # Set on terminal success — full VideoGenerationResponse serialized.
    # NOTE: ``result.video_url`` is rewritten to our same-origin proxy path
    # (``/api/video/file/{job_id}``) so the phone never has to fetch the
    # cross-border CDN directly. The original upstream URL is kept in
    # ``upstream_video_url`` for the proxy route to read.
    result: Optional[dict] = None
    upstream_video_url: Optional[str] = None

    # Set on terminal failure.
    error: Optional[str] = None
    upstream_body: Any = None
    exception_type: Optional[str] = None

    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


_jobs: "OrderedDict[str, JobState]" = OrderedDict()
_lock = threading.Lock()

# Keep job records for ~last 100 generations. Each is <10KB so this is a
# negligible memory footprint, and a hackathon server gets restarted often
# enough that we don't need real expiry.
MAX_JOBS = 100


def create_job(req: VideoGenerationRequest) -> str:
    job_id = uuid.uuid4().hex
    state = JobState(job_id=job_id)
    with _lock:
        _jobs[job_id] = state
        while len(_jobs) > MAX_JOBS:
            evicted_id, _ = _jobs.popitem(last=False)
            logger.info("evicting old job: %s", evicted_id)

    # daemon=True so the worker thread doesn't keep the process alive on
    # shutdown. The thread captures `req` by value so the caller can return
    # immediately.
    t = threading.Thread(target=_run_job, args=(job_id, req), daemon=True,
                         name=f"video-job-{job_id[:8]}")
    t.start()
    logger.info("started video job %s (mbti=%s)", job_id, req.mbti)
    return job_id


def get_snapshot(job_id: str) -> Optional[dict]:
    """Return a thread-safe snapshot of a job's current state, or None."""
    with _lock:
        state = _jobs.get(job_id)
        if state is None:
            return None
        return asdict(state)


def _update(job_id: str, **fields_: Any) -> None:
    with _lock:
        state = _jobs.get(job_id)
        if state is None:
            return
        for k, v in fields_.items():
            setattr(state, k, v)
        state.updated_at = time.time()


def _apply_event(job_id: str, ev: dict) -> None:
    """Map a video_gen progress event onto the job record."""
    e = ev.get("event")
    data = ev.get("data") or {}

    if e == "writing_script":
        _update(job_id, phase="script")
    elif e == "script_chunk":
        _update(job_id, phase="script",
                script_chunks=int(data.get("chunks", 0)),
                script_size=int(data.get("size", 0)))
    elif e == "script":
        # Emitted by generate_streaming between the two stages with a small
        # preview dict (title/scene/expression_style/spoken_script).
        _update(job_id, phase="render", script=dict(data))
    elif e == "rendering":
        _update(job_id, phase="render", render_chunks=0, render_size=0)
    elif e == "render_chunk":
        _update(job_id, phase="render",
                render_chunks=int(data.get("chunks", 0)),
                render_size=int(data.get("size", 0)))
    elif e == "polling":
        _update(job_id, phase="render",
                poll_attempt=int(data.get("attempt", 0)),
                poll_elapsed_sec=int(data.get("elapsed_sec", 0)),
                last_poll_preview=str(data.get("preview", ""))[:300] or None)
    # ping / heartbeat events are server-internal — ignore here. The streaming
    # endpoint needed them to keep CDNs awake; for job mode there's no long
    # connection to keep alive.


def _run_job(job_id: str, req: VideoGenerationRequest) -> None:
    try:
        gen = video_gen.generate_streaming(req)
        try:
            while True:
                ev = next(gen)
                _apply_event(job_id, ev)
        except StopIteration as stop:
            result = stop.value  # VideoGenerationResponse
            upstream_url = result.video_url
            result_dict = result.model_dump(mode="json")
            # Frontend feeds result.video_url directly into <video src>.
            # Swap to our same-origin proxy path; the original cross-border
            # CDN URL is kept on the job record for the proxy route to read.
            result_dict["video_url"] = f"/api/video/file/{job_id}"
            _update(job_id,
                    status="done",
                    phase="done",
                    result=result_dict,
                    upstream_video_url=upstream_url)
            logger.info("video job %s done (upstream=%s)", job_id, upstream_url)
    except Exception as exc:  # noqa: BLE001
        logger.exception("video job %s crashed", job_id)
        _update(job_id,
                status="error",
                phase="error",
                error=str(exc),
                exception_type=type(exc).__name__,
                upstream_body=getattr(exc, "body", None))
