"""Async SQLAlchemy engine and session factory. Engine is lazy + cached;
tests override DATABASE_URL via env before first access."""
from __future__ import annotations

from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.settings import get_settings


@lru_cache(maxsize=1)
def get_engine():
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        future=True,
        pool_pre_ping=True,
        echo=False,
    )


@lru_cache(maxsize=1)
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=get_engine(),
        expire_on_commit=False,
        class_=AsyncSession,
    )


def reset_engine_cache() -> None:
    """Invalidate the cached engine; tests call this after switching env vars."""
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()
