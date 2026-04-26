import asyncio
import json
import os
import secrets
import time
import pytest
from starlette.testclient import TestClient


def _ensure_schema(database_url: str) -> None:
    """Create all tables synchronously (in a fresh event loop) before TestClient starts."""
    from sqlalchemy.ext.asyncio import create_async_engine
    from src.data.models import Base

    async def _create():
        engine = create_async_engine(database_url, future=True)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(_create())


def _sync_pair(client, redis_url: str) -> str:
    """Synchronous pairing flow using sync redis for test setup."""
    import redis as syncredis
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding, NoEncryption, PrivateFormat, PublicFormat,
    )
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode()
    secret = secrets.token_bytes(32).hex()

    r = syncredis.from_url(redis_url)
    r.setex(f"bootstrap:{secret}", 600, json.dumps({"issued_at": 0}))
    r.close()

    resp = client.post("/api/v1/auth/challenge", json={"bootstrap_secret": secret})
    sig = priv.sign(bytes.fromhex(resp.json()["challenge"])).hex()
    resp = client.post("/api/v1/auth/pair", json={
        "bootstrap_secret": secret, "public_key": pub, "signature": sig,
    })
    return resp.json()["token"]


def test_ws_connect_and_receive_event(redis_container, pg_container):
    import redis as syncredis
    from src.data import db as _db_mod
    from src.settings import get_settings
    from src.api.app import create_app

    redis_url = (
        f"redis://{redis_container.get_container_host_ip()}"
        f":{redis_container.get_exposed_port(6379)}/0"
    )

    # Set env vars so the app (running in TestClient's loop) picks up the right URLs
    os.environ["CELERY_BROKER_URL"] = redis_url
    os.environ["CELERY_RESULT_BACKEND"] = redis_url

    sync_url = pg_container.get_connection_url()
    database_url = sync_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
    os.environ["DATABASE_URL"] = database_url

    # Ensure tables exist (runs in a fresh short-lived event loop)
    _ensure_schema(database_url)

    # Close any Redis client bound to the session event loop and clear all caches
    # so TestClient's event loop creates fresh connections.
    from src.api.core.redis_dep import _close_redis
    asyncio.run(_close_redis())
    get_settings.cache_clear()
    _db_mod.reset_engine_cache()

    app = create_app()
    with TestClient(app) as client:
        token = _sync_pair(client, redis_url)

        import jwt as pyjwt
        payload = pyjwt.decode(token, options={"verify_signature": False})
        device_id = payload["sub"]

        with client.websocket_connect(f"/api/v1/ws?token={token}") as ws:
            # Give the pubsub bridge a moment to subscribe before publishing
            time.sleep(0.1)

            # Publish an event via Redis
            r = syncredis.from_url(redis_url)
            r.publish(f"events:{device_id}", json.dumps({"type": "run.started", "run_id": "r-1"}))
            r.close()

            # Receive it
            data = ws.receive_json()
            assert data["type"] == "run.started"
