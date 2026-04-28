from __future__ import annotations

import asyncio
import pathlib
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.settings import get_settings
from src.api.routers.auth import router as auth_router
from src.api.routers.devices import router as devices_router
from src.api.routers.jobs import router as jobs_router
from src.api.routers.runs import router as runs_router
from src.api.routers.applications import router as applications_router
from src.api.routers.pipeline import router as pipeline_router
from src.api.routers.ws import router as ws_router, pubsub_bridge
from src.api.routers.integrations import router as integrations_router
from src.api.middleware.idempotency import IdempotencyMiddleware
from src.api.core.deps import get_current_device


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(pubsub_bridge())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    from src.api.core.redis_dep import _close_redis
    await _close_redis()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Job Automation AI",
        version=settings.app_version,
        docs_url=None if settings.environment == "production" else "/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(IdempotencyMiddleware)

    _static = pathlib.Path("static")
    if _static.is_dir():
        app.mount("/static", StaticFiles(directory=str(_static)), name="static")

    @app.get("/health", include_in_schema=False)
    async def health_check():
        return {"status": "ok"}

    @app.get("/api/v1/status")
    async def status(_device=Depends(get_current_device)):
        from src.api.core.redis_dep import get_redis
        redis = get_redis()
        info = await redis.info("server")
        return {"redis_version": info.get("redis_version"), "status": "ok"}

    app.include_router(auth_router,         prefix="/api/v1/auth",         tags=["auth"])
    app.include_router(devices_router,      prefix="/api/v1/devices",      tags=["devices"])
    app.include_router(jobs_router,         prefix="/api/v1/jobs",         tags=["jobs"])
    app.include_router(runs_router,         prefix="/api/v1/runs",         tags=["runs"])
    app.include_router(applications_router, prefix="/api/v1/applications", tags=["applications"])
    app.include_router(pipeline_router,     prefix="/api/v1/pipeline",     tags=["pipeline"])
    app.include_router(ws_router,           prefix="/api/v1",              tags=["ws"])
    app.include_router(integrations_router, prefix="/api/v1/integrations", tags=["integrations"])

    # SPA catch-all — MUST be last so all /api/v1/* routes match first
    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_catch_all(full_path: str):
        index = _static / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return {"detail": "Operator console not yet deployed"}

    return app
