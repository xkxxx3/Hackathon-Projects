"""Heartbeat helper for keeping streaming HTTP responses warm.

Cloudflare Quick Tunnel (and most CDN reverse proxies) will close a streaming
response that goes quiet for too long, even if the upstream is still working.
Veo's image-to-video stream is the canonical example: ``create(stream=True)``
blocks 10-30s while the model spins up, then chunks arrive 5-30s apart. From
the edge's point of view that looks like a hung response.

`with_heartbeat` wraps any (sync) iterator. It runs the source in a daemon
thread; the main thread reads from a queue with a timeout, and emits the
``HEARTBEAT`` sentinel whenever the source has been quiet for ``interval``
seconds. The caller turns each sentinel into a no-op NDJSON line, which
keeps the wire busy without changing the visible UI state.
"""
from __future__ import annotations

import queue
import threading
from typing import Iterator, TypeVar

T = TypeVar("T")

# Compare against this with `is`, not `==`. It's an opaque marker, never a
# value the underlying stream would naturally produce.
HEARTBEAT = object()


def with_heartbeat(source: Iterator[T], interval: float = 8.0) -> Iterator[T]:
    """Iterate `source`, yielding HEARTBEAT during silences of >= `interval`s.

    Exceptions raised by the source propagate to the caller. The consumer
    thread is a daemon so it doesn't keep the process alive on shutdown.
    """
    q: queue.Queue = queue.Queue()
    DONE = object()

    def consumer() -> None:
        try:
            for item in source:
                q.put(item)
        except BaseException as exc:  # noqa: BLE001 — re-raised in caller
            q.put(exc)
        finally:
            q.put(DONE)

    threading.Thread(target=consumer, daemon=True).start()

    while True:
        try:
            item = q.get(timeout=interval)
        except queue.Empty:
            yield HEARTBEAT  # type: ignore[misc]
            continue
        if item is DONE:
            return
        if isinstance(item, BaseException):
            raise item
        yield item
