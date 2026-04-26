from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.settings import get_settings
from src.api.routers.auth import router as auth_router
from src.api.routers.devices import router as devices_router
from src.api.routers.jobs import router as jobs_router
from src.api.routers.runs import router as runs_router
from src.api.middleware.idempotency import IdempotencyMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
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

    @app.get("/health", include_in_schema=False)
    async def health_check():
        return {"status": "ok"}

    app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(devices_router, prefix="/api/v1/devices", tags=["devices"])
    app.include_router(jobs_router, prefix="/api/v1/jobs", tags=["jobs"])
    app.include_router(runs_router, prefix="/api/v1/runs", tags=["runs"])

    return app
