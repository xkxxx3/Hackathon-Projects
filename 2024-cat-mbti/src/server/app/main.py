from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import analyze, llm, video
from app.core.config import settings

# Python's default root level is WARNING, so app.* INFO logs are dropped before
# they hit uvicorn's stdout. Uvicorn configures its own (`uvicorn`, `uvicorn.
# access`) loggers separately — that's why request lines show but our pipeline
# progress doesn't. Force-level the `app` tree to INFO so polling / chunk /
# stream-complete logs are visible during debugging.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logging.getLogger("app").setLevel(logging.INFO)

logger = logging.getLogger(__name__)


# Built frontend lives next to the server tree at src/web/dist/. If you haven't
# run `npm run build` yet, this directory won't exist and we fall back to API-
# only mode (Vite dev server handles the UI via its /api proxy).
WEB_DIST = Path(__file__).resolve().parent.parent.parent / "web" / "dist"


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API routes MUST be added before the SPA catch-all below, otherwise the
    # catch-all swallows /api/* and serves index.html instead of routing.
    app.include_router(analyze.router, prefix=settings.api_prefix, tags=["analyze"])
    app.include_router(video.router, prefix=settings.api_prefix, tags=["video"])
    app.include_router(llm.router, prefix=settings.api_prefix, tags=["llm"])

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    if WEB_DIST.exists():
        logger.warning("SPA mode: serving frontend from %s", WEB_DIST)
        # Hashed asset bundles served raw.
        app.mount(
            "/assets",
            StaticFiles(directory=WEB_DIST / "assets"),
            name="assets",
        )

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa(full_path: str):
            # Don't let the SPA catch-all eat /api/* — return a real 404 so
            # the frontend's stream parser surfaces it instead of receiving
            # HTML and choking on "non-JSON line".
            if full_path == "api" or full_path.startswith("api/"):
                raise HTTPException(status_code=404)
            requested = WEB_DIST / full_path
            if full_path and requested.is_file():
                return FileResponse(requested)
            # Unknown path → let React Router handle it client-side.
            return FileResponse(WEB_DIST / "index.html")
    else:
        logger.warning(
            "SPA mode DISABLED: %s does not exist. "
            "Run `npm run build` in src/web/ to enable frontend serving.",
            WEB_DIST,
        )

    return app


app = create_app()
