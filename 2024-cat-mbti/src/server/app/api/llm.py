from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.core import gemini_client

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/llm/ping")
def ping() -> dict:
    """Verify the LLM proxy is reachable + the configured model resolves.

    Curl example:
        curl http://localhost:8000/api/llm/ping

    On success returns `{ok, base_url, model, reply}`.
    On failure returns 502 with the upstream error body so you can read
    exactly what the proxy said (e.g. "无可用渠道 gemini-3.1-pro").
    """
    if not gemini_client.is_enabled():
        raise HTTPException(status_code=412, detail="GEMINI_API_KEY 未配置(.env 缺失或为空)")

    try:
        return gemini_client.ping()
    except Exception as exc:  # noqa: BLE001 — surfacing upstream error verbatim
        body = getattr(exc, "body", None)
        status = getattr(exc, "status_code", 502) or 502
        logger.warning("llm ping failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail={
                "upstream_status": status,
                "upstream_body": body,
                "exception": type(exc).__name__,
                "message": str(exc),
            },
        ) from exc
