"""Quick smoke test: ping each candidate video model via chat/completions
with a minimal text-only request. We're not generating videos here — just
checking which model IDs the proxy actually routes via this endpoint.

Costs are negligible (max_tokens=1 each, ~13 calls total) — but we DO want
to know which ones return 200 (or even 400 with a real error message) vs 404
(endpoint mismatch).

Run from src/server/ with the project's .venv active so we share the same
OpenAI client config as the real backend."""
from __future__ import annotations

import sys
sys.path.insert(0, ".")

from app.core.gemini_client import _make_client

CANDIDATES = [
    "doubao-seedance-2-0-260128",
    "doubao-seedance-2-0-fast-260128",
    "domo-img-to-video",
    "wan2.6-i2v",
    "wan2.7-i2v",
    "wan2.5-i2v-preview",
    "wanx2.1-i2v-plus",
    "kling-video-std-5s",
    "kling-video-pro-5s",
    "runway-video",
    "luma-video",
    "pika-1.5",
    "veo3.1-fast",
]


def probe(client, model: str) -> str:
    try:
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=1,
        )
        finish = r.choices[0].finish_reason if r.choices else "no-choices"
        content = (r.choices[0].message.content or "")[:40] if r.choices else ""
        return f"200 OK   finish={finish}  content={content!r}"
    except Exception as e:
        code = getattr(e, "status_code", "?")
        body = getattr(e, "body", None)
        if isinstance(body, dict):
            err = body.get("error") or {}
            msg = err.get("message") or err.get("type") or str(body)
        elif body:
            msg = str(body)
        else:
            msg = str(e)
        return f"{code}  {msg[:160]}"


def main() -> None:
    client = _make_client()
    print(f"{'model':<40}  result")
    print("-" * 100)
    for m in CANDIDATES:
        print(f"{m:<40}  ", end="", flush=True)
        print(probe(client, m), flush=True)


if __name__ == "__main__":
    main()
