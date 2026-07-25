from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.core import video_jobs
from app.models.schemas import VideoGenerationRequest

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/video/start")
def start_video(req: VideoGenerationRequest) -> dict:
    """Kick off a video generation job and return its id immediately.

    Replaces the old streaming ``POST /video/generate``: that endpoint held
    one HTTP connection open for the entire 3-8 min pipeline, which is fatal
    on mobile (screen lock, carrier NAT, Wi-Fi roam all close the socket).
    The work itself runs unchanged on a background thread; the client just
    polls ``GET /video/status/{job_id}`` every few seconds for progress.
    """
    job_id = video_jobs.create_job(req)
    return {"job_id": job_id}


@router.get("/video/status/{job_id}")
def video_status(job_id: str) -> dict:
    """Return the current snapshot of a job. Frontend polls this on a timer.

    Shape mirrors core.video_jobs.JobState as JSON. The frontend looks at
    ``status`` (running / done / error) to decide whether to keep polling,
    and at ``phase`` + the chunk/poll counters to drive the progress UI.
    On terminal success, ``result`` is the full VideoGenerationResponse;
    on terminal failure, ``error`` + ``upstream_body`` mirror what the old
    streaming endpoint emitted.
    """
    snap = video_jobs.get_snapshot(job_id)
    if snap is None:
        raise HTTPException(status_code=404, detail="job not found")
    return snap


# Generous timeouts for proxying video bytes from a cross-border CDN. Connect
# can be slow over the wall, body chunks may arrive at human pace if the CDN
# is still warming. read=120 means "no individual chunk gap > 2min", not "the
# whole transfer must finish in 2min" — fine for an 8-15s clip (~5-15 MB).
_PROXY_TIMEOUT = httpx.Timeout(connect=15.0, read=120.0, write=15.0, pool=10.0)


@router.get("/video/file/{job_id}")
async def video_file(job_id: str, request: Request):
    """Same-origin proxy for the generated MP4.

    openai-next returns MP4 URLs on hosts like ``pro.filesystem.site`` that
    国内运营商网络拉不动 — TLS comes up but media bytes stall. The same phone
    already has a working pipe to our tunnel for /api/video/status, so we
    let it grab the video bytes through here too.

    Forwards the client's Range header so iOS Safari can probe metadata
    (Range: bytes=0-1) and scrub. Returns Accept-Ranges: bytes plus the
    upstream's Content-Length / Content-Range as-is so the player knows
    the real duration and chunk size.
    """
    snap = video_jobs.get_snapshot(job_id)
    if snap is None:
        raise HTTPException(404, "job not found")

    upstream = snap.get("upstream_video_url")
    if not upstream:
        # Job exists but render hasn't finished, or it errored.
        if snap.get("status") == "error":
            raise HTTPException(500, f"job errored: {snap.get('error')}")
        raise HTTPException(425, "video not ready yet")  # 425 Too Early

    # Forward Range only. Don't leak cookies / UA / our internal headers
    # to the upstream CDN — they don't need them and some CDNs 403 on
    # unexpected headers.
    fwd_headers: dict[str, str] = {}
    range_header = request.headers.get("range")
    if range_header:
        fwd_headers["Range"] = range_header

    client = httpx.AsyncClient(timeout=_PROXY_TIMEOUT, follow_redirects=True)
    try:
        upstream_req = client.build_request("GET", upstream, headers=fwd_headers)
        upstream_resp = await client.send(upstream_req, stream=True)
    except httpx.HTTPError as exc:
        await client.aclose()
        logger.exception("upstream CDN unreachable: %s", upstream)
        raise HTTPException(502, f"upstream CDN unreachable: {exc}") from exc

    if upstream_resp.status_code >= 400:
        body_preview = (await upstream_resp.aread())[:300]
        await upstream_resp.aclose()
        await client.aclose()
        logger.warning("upstream CDN %d for %s: %r",
                       upstream_resp.status_code, upstream, body_preview)
        raise HTTPException(
            status_code=upstream_resp.status_code,
            detail=f"upstream CDN error: {body_preview!r}",
        )

    # Headers iOS actually cares about for video playback:
    #   Content-Type: tells it which decoder to use
    #   Accept-Ranges: enables the seek bar at all
    #   Content-Length / Content-Range: lets the player compute duration
    #     and seek targets accurately
    out_headers: dict[str, str] = {
        "Content-Type": upstream_resp.headers.get("content-type", "video/mp4"),
        "Accept-Ranges": "bytes",
        # Cache for an hour at the browser. The job is one-shot but a scrub
        # back to t=0 shouldn't have to re-fetch from the CDN.
        "Cache-Control": "public, max-age=3600",
    }
    for k in ("content-length", "content-range"):
        v = upstream_resp.headers.get(k)
        if v:
            out_headers[k] = v

    async def stream_body():
        try:
            async for chunk in upstream_resp.aiter_bytes(64 * 1024):
                yield chunk
        finally:
            await upstream_resp.aclose()
            await client.aclose()

    return StreamingResponse(
        stream_body(),
        # Preserve 200 vs 206 — iOS treats Partial Content very differently
        # from a regular 200 when it comes to seeking.
        status_code=upstream_resp.status_code,
        headers=out_headers,
        media_type=out_headers["Content-Type"],
    )
