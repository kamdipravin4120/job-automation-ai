from __future__ import annotations

import asyncio
import json

import jwt as pyjwt
from fastapi import APIRouter
from starlette.websockets import WebSocket, WebSocketDisconnect

from src.api.core.connection_manager import manager
from src.api.core.security import decode_jwt
from src.api.core.redis_dep import get_redis

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, token: str):
    try:
        payload = decode_jwt(token)
    except pyjwt.exceptions.PyJWTError:
        await ws.close(code=4001)
        return

    device_id = payload["sub"]
    redis = get_redis()

    # Check JTI revocation
    if await redis.exists(f"revoked:jti:{payload['jti']}"):
        await ws.close(code=4001)
        return

    await manager.connect(device_id, ws)
    try:
        while True:
            # Keep connection alive; client messages are ignored
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(device_id, ws)


async def pubsub_bridge() -> None:
    import redis.asyncio as aioredis
    from src.settings import get_settings

    # Create a dedicated connection for pubsub — avoids sharing the singleton
    # across event loops (important for TestClient isolation in tests).
    redis = aioredis.from_url(get_settings().celery_broker_url, decode_responses=True)
    try:
        pubsub = redis.pubsub()
        await pubsub.psubscribe("events:*")
        async for msg in pubsub.listen():
            if msg.get("type") != "pmessage":
                continue
            channel = msg["channel"]
            device_id = channel.split(":", 1)[1]
            try:
                data = json.loads(msg["data"])
            except (json.JSONDecodeError, TypeError):
                continue
            await manager.send(device_id, data)
    finally:
        try:
            await redis.aclose()
        except Exception:
            pass
