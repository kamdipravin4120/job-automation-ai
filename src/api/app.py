from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.settings import get_settings
from src.api.routers.auth import router as auth_router


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

    @app.get("/health", include_in_schema=False)
    async def health_check():
        return {"status": "ok"}

    app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])

    return app
