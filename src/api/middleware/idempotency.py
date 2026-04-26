from __future__ import annotations

import json

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

IDEMPOTENT_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
CACHE_TTL = 86400  # 24 hours


class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        idempotency_key = request.headers.get("Idempotency-Key")
        if request.method not in IDEMPOTENT_METHODS or not idempotency_key:
            return await call_next(request)

        from src.api.core.redis_dep import get_redis

        redis = get_redis()
        scope = getattr(request.state, "device_id", request.client.host if request.client else "anon")
        cache_key = f"idem:{scope}:{idempotency_key}"

        cached = await redis.get(cache_key)
        if cached:
            data = json.loads(cached)
            return Response(
                content=data["body"],
                status_code=data["status"],
                media_type="application/json",
            )

        response = await call_next(request)

        # Cache only 2xx responses
        if 200 <= response.status_code < 300:
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            await redis.setex(
                cache_key,
                CACHE_TTL,
                json.dumps({"status": response.status_code, "body": body.decode()}),
            )
            return Response(
                content=body,
                status_code=response.status_code,
                media_type="application/json",
                headers=dict(response.headers),
            )

        return response
