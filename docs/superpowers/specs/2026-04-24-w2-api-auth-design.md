# W2 — API + Auth Design Spec

**Project:** Job Automation AI — FastAPI backend + device auth  
**Status:** Approved (brainstorming session 2026-04-24, security review incorporated)  
**Author:** System architect (Claude Sonnet 4.6)  
**Date:** 2026-04-24  
**Supersedes:** §4.2 of `2026-04-21-production-web-app-design.md` (auth model replaced: opaque tokens → EdDSA JWT; WebAuthn deferred to W3+)

---

## 0. Scope

W2 delivers the FastAPI backend with device-pairing auth, the full read/trigger REST API, a WebSocket event bridge, and idempotency middleware. Mobile companion and operator console consume this surface.

Out of scope for W2: operator web console (W3), self-correcting mechanisms (W4), Gmail/LinkedIn automation (W5), ops hardening (W6).

---

## 1. Directory Structure

New tree under `src/api/` — sits alongside existing `src/data/`, `src/tasks/`, etc.

```
src/api/
  __init__.py
  app.py                      # create_app() factory
  core/
    security.py               # JWT encode/decode (EdDSA), Ed25519 helpers
    deps.py                   # get_current_device() FastAPI dependency
    connection_manager.py     # WebSocket ConnectionManager
  middleware/
    idempotency.py            # Idempotency-Key middleware
    cors.py                   # CORS config
  routers/
    auth.py                   # POST /auth/challenge, POST /auth/pair
    devices.py                # DELETE /devices/{device_id}
    jobs.py
    runs.py
    applications.py
    pipeline.py               # POST /pipeline/trigger
    ws.py                     # WS /ws
  services/
    auth.py                   # bootstrap, challenge, pairing logic
    devices.py                # last_seen update, revocation
  schemas/
    auth.py                   # PairRequest, TokenResponse, ChallengeResponse
    jobs.py
    runs.py
    applications.py
    common.py                 # PaginatedResponse[T], ErrorResponse
```

Existing infrastructure reused as-is:
- `src/data/repositories/` — all DB access goes through existing repos
- `src/data/db.py` — `get_async_session()` dependency
- `src/settings.py` — new fields appended (see §3)
- `src/observability/logging.py` — structlog, correlation_id

---

## 2. App Factory

```python
# src/api/app.py
def create_app() -> FastAPI:
    app = FastAPI(
        title="Job Automation AI",
        version=settings.app_version,
        docs_url=None if settings.environment == "production" else "/docs",
        redoc_url=None,
    )
    app.add_middleware(CORSMiddleware, **cors_config())
    app.add_middleware(IdempotencyMiddleware)
    app.include_router(auth_router,   prefix="/api/v1/auth",         tags=["auth"])
    app.include_router(devices_router,prefix="/api/v1/devices",      tags=["devices"])
    app.include_router(jobs_router,   prefix="/api/v1/jobs",         tags=["jobs"])
    app.include_router(runs_router,   prefix="/api/v1/runs",         tags=["runs"])
    app.include_router(apps_router,   prefix="/api/v1/applications", tags=["applications"])
    app.include_router(pipeline_router,prefix="/api/v1/pipeline",    tags=["pipeline"])
    app.include_router(ws_router,     prefix="/api/v1",              tags=["ws"])
    app.add_api_route("/health", health_check, methods=["GET"], include_in_schema=False)
    app.on_event("startup")(start_pubsub_bridge)
    return app
```

Middleware stack order (outer → inner): CORS → Idempotency → route handlers.  
Auth is a FastAPI dependency (`Depends(get_current_device)`), not middleware — gives per-route control.

---

## 3. Settings Additions

Appended to `src/settings.py` `Settings` model:

```python
# JWT / Auth
jwt_private_key: SecretStr        # Ed25519 PEM private key
jwt_public_key: str               # Ed25519 PEM public key
jwt_algorithm: str = "EdDSA"
jwt_ttl_days: int = 7
jwt_rotation_days: int = 6        # issue refresh token when iat older than this
jwt_leeway_seconds: int = 60      # clock skew tolerance

# Bootstrap
bootstrap_secret_ttl_seconds: int = 600   # 10 min, single-use

# Rate limits
rate_limit_pair_per_min: int = 5
rate_limit_auth_per_min: int = 60

# App
app_version: str = "0.2.0"
environment: str = "development"
```

Key generation (one-time, at deploy):
```bash
python -c "
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, PublicFormat, NoEncryption
k = Ed25519PrivateKey.generate()
print(k.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode())
print(k.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode())
"
```

---

## 4. Auth Flow

### 4.1 Bootstrap (CLI → QR)

```bash
python main.py bootstrap
```

Generates 32-byte random secret, stores in Redis:
```
bootstrap:{secret} = {"issued_at": ts, "ip_hash": sha256(ip)} TTL 600s
```
Prints as QR code to stdout. Single-use — consumed on successful pairing.

### 4.2 Device Pairing (3-step proof-of-possession)

Device generates Ed25519 keypair locally before starting the flow.

**Step 1 — Request challenge**
```
POST /api/v1/auth/challenge
Body: {"bootstrap_secret": "<hex>"}

→ verify secret exists in Redis
→ store challenge:{secret} = random_32_bytes  TTL 60s
← 200 {"challenge": "<hex>"}

Rate limit: pair:{ip} → 5/min → 429 on breach
```

**Step 2 — Pair with proof**
```
POST /api/v1/auth/pair
Body: {"bootstrap_secret": "<hex>", "public_key": "<PEM>", "signature": "<hex>"}

→ verify bootstrap_secret still valid (→ 401 if expired/absent)
→ verify Ed25519 signature(challenge bytes, public_key) (→ 401 if invalid)
→ delete bootstrap:{secret} (single-use)
→ delete challenge:{secret}
→ INSERT sessions row
→ issue JWT
← 201 {"token": "<jwt>"}
```

Sessions row inserted:
```sql
INSERT INTO sessions (device_id, public_key, pairing_ip, pairing_time, created_at)
VALUES (gen_random_uuid(), $pubkey, $ip, now(), now())
```

### 4.3 JWT Format

```json
{
  "sub": "<device_id uuid>",
  "jti": "<uuid4>",
  "iat": 1714000000,
  "exp": 1714604800
}
```
Signed with Ed25519 private key (`EdDSA` algorithm). Library: `python-jose[cryptography]`.

### 4.4 Per-Request Auth (`deps.py`)

```python
async def get_current_device(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_async_session),
    redis: Redis = Depends(get_redis),
    request: Request = None,
) -> Device:
    try:
        payload = jwt.decode(
            token, settings.jwt_public_key,
            algorithms=[settings.jwt_algorithm],
            options={"leeway": settings.jwt_leeway_seconds},
        )
    except JWTError:
        raise HTTPException(401, "Invalid token")

    jti       = payload["jti"]
    device_id = payload["sub"]
    iat       = payload["iat"]

    # JTI revocation check (covers logout + rotation of old token)
    if await redis.exists(f"revoked:jti:{jti}"):
        raise HTTPException(401, "Token revoked")

    # Load session
    session = await session_repo.get(db, device_id)
    if not session:
        raise HTTPException(401, "Device not found")

    # Device-wide revocation: iat must be after revoked_at
    if session.revoked_at and iat < session.revoked_at.timestamp():
        raise HTTPException(401, "Token predates device revocation")

    # Rotation: if token is older than rotation_days, issue new one
    iat_dt = datetime.fromtimestamp(iat, tz=timezone.utc)
    if (datetime.now(tz=timezone.utc) - iat_dt).days >= settings.jwt_rotation_days:
        new_token = create_jwt(device_id)
        remaining = int(payload["exp"] - time.time())
        if remaining > 0:
            await redis.setex(f"revoked:jti:{jti}", remaining, "1")
        request.state.next_token = new_token

    # Fire-and-forget last_seen update
    asyncio.create_task(
        session_service.touch(db, device_id, request.client.host, request.headers.get("User-Agent"))
    )

    return Device(id=device_id, session=session)
```

Response middleware injects `X-Auth-Next-Token: <token>` when `request.state.next_token` is set.

### 4.5 Revocation (`DELETE /api/v1/devices/{device_id}`)

```python
session.revoked_at = datetime.now(tz=timezone.utc)
await db.commit()
# Optionally invalidate current token immediately
if current_jti:
    remaining = int(payload["exp"] - time.time())
    await redis.setex(f"revoked:jti:{current_jti}", max(remaining, 1), "1")
```

Device-wide revocation is immediate for any new request after commit (iat < revoked_at check).

### 4.6 Redis Key Space

| Key | Value | TTL |
|-----|-------|-----|
| `bootstrap:{secret}` | JSON `{issued_at, ip_hash}` | 600s |
| `challenge:{secret}` | random bytes (hex) | 60s |
| `pair:{ip}` | rate limit counter | 60s |
| `revoked:jti:{jti}` | `"1"` | token remaining lifetime |
| `auth:{device_id}` | rate limit counter | 60s |
| `idem:{device_id}:{key}` | `{status, body}` | 86400s |

No unbounded sets. All keys have explicit TTLs.

---

## 5. REST API Surface

All routes under `/api/v1/` require `Authorization: Bearer <token>` except auth challenge/pair and `/health`.

### 5.1 Endpoint List

```
# Auth — no JWT required
POST   /api/v1/auth/challenge
POST   /api/v1/auth/pair

# Devices — JWT required
DELETE /api/v1/devices/{device_id}

# Jobs — read-only
GET    /api/v1/jobs                 ?page=1&per_page=50&status=&source=
GET    /api/v1/jobs/{job_id}

# Runs
GET    /api/v1/runs                 ?page=1&per_page=50&status=
GET    /api/v1/runs/{run_id}

# Applications
GET    /api/v1/applications         ?page=1&per_page=50&status=
GET    /api/v1/applications/{app_id}

# Pipeline trigger
POST   /api/v1/pipeline/trigger     requires Idempotency-Key header

# WebSocket
WS     /api/v1/ws?token={jwt}

# System
GET    /health                      no auth
GET    /api/v1/status               queue depths, worker counts
```

Pagination defaults: `page=1`, `per_page=50`, max `per_page=200`.

### 5.2 Response Envelopes

**Paginated list:**
```json
{
  "items": [...],
  "total": 100,
  "page": 1,
  "per_page": 50,
  "has_next": true
}
```

**Error:**
```json
{
  "error": {
    "code": "INVALID_TOKEN",
    "message": "Human-readable description",
    "request_id": "uuid"
  }
}
```

**HTTP status codes:**
- 400 — bad request / validation
- 401 — auth failure
- 404 — not found
- 409 — idempotency conflict (same key, different payload)
- 422 — Pydantic validation error
- 429 — rate limit
- 500 — internal error (PipelineError.safe_detail only, no raw tracebacks)

---

## 6. Idempotency Middleware

Applies to mutating methods: POST, PUT, PATCH, DELETE.

**Header:** `Idempotency-Key: <uuid4>` — required for `POST /pipeline/trigger`, optional elsewhere.

**Flow:**
```
1. Extract Idempotency-Key header
2. Redis key: idem:{device_id}:{idempotency_key}  TTL 24h
3. If key exists in Redis:
   - same method+path: return cached {status_code, body}  [200/201]
   - different method+path: 409 Conflict
4. If key absent: process request normally, cache response, return
```

Implemented as Starlette `BaseHTTPMiddleware`. Only caches 2xx responses. Does not cache 4xx/5xx.

---

## 7. WebSocket Event Bridge

### 7.1 Connection

```
WS /api/v1/ws?token={jwt}
→ same JWT validation as deps.py (EdDSA decode, leeway, JTI check, revoked_at)
→ connection_manager.connect(device_id, websocket)
→ subscribe to Redis pubsub events:{device_id}
← stream of JSON event frames until disconnect
```

### 7.2 ConnectionManager

```python
# src/api/core/connection_manager.py
class ConnectionManager:
    _connections: dict[str, set[WebSocket]]

    async def connect(self, device_id: str, ws: WebSocket) -> None
    async def disconnect(self, device_id: str, ws: WebSocket) -> None
    async def send(self, device_id: str, payload: dict) -> None
        # iterates set copy; discards dead sockets silently
    async def broadcast(self, payload: dict) -> None
        # sends to all connected devices
```

Singleton instantiated at app startup, injected via `Depends()`.

### 7.3 Redis Pubsub Bridge

Background `asyncio.Task` started in `app.on_event("startup")`:

```python
async def pubsub_bridge(manager: ConnectionManager, redis: Redis):
    async with redis.pubsub() as ps:
        await ps.psubscribe("events:*")
        async for msg in ps.listen():
            if msg["type"] != "pmessage":
                continue
            device_id = msg["channel"].decode().split(":", 1)[1]
            await manager.send(device_id, json.loads(msg["data"]))
```

Celery tasks publish via `redis.publish(f"events:{device_id}", json.dumps(event))`.

### 7.4 Event Schema

All events include `type`, `ts` (ISO8601), and type-specific fields:

```json
{"type": "run.started",   "run_id": "...", "correlation_id": "...", "ts": "..."}
{"type": "run.completed", "run_id": "...", "result": {...},          "ts": "..."}
{"type": "run.failed",    "run_id": "...", "error_code": "...",      "ts": "..."}
{"type": "job.found",     "job_id": "...", "title": "...",           "ts": "..."}
{"type": "auth_refresh",  "token": "..."}
```

`auth_refresh` is sent by the WS handler when token rotation fires mid-connection (iat > rotation_days). Client should reconnect with the new token on next connection.

---

## 8. Database Migration

New `sessions` table (Alembic revision):

```sql
CREATE TABLE sessions (
    device_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    public_key      TEXT NOT NULL,
    pairing_ip      INET,
    pairing_time    TIMESTAMPTZ,
    last_seen       TIMESTAMPTZ,
    last_ip         INET,
    last_user_agent TEXT,
    revoked_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_sessions_revoked_at ON sessions (revoked_at) WHERE revoked_at IS NOT NULL;
```

---

## 9. Testing Strategy

```
tests/api/
  conftest.py           # AsyncClient + db_session (reuse W1 testcontainers fixture)
                        # real Ed25519 keypair fixture, real Redis fixture
  test_auth.py          # challenge flow, pairing, invalid sig, expired challenge,
                        # JWT decode, JTI revocation, device-wide revocation, rotation
  test_jobs.py          # list pagination, filters, detail, 404
  test_runs.py
  test_applications.py
  test_pipeline.py      # trigger + idempotency replay (same key = cached response)
  test_devices.py       # revoke → subsequent request 401
  test_ws.py            # connect, receive pubsub event, auth_refresh frame
  test_middleware.py    # idempotency: first request processes, second returns cache
```

- `pytest-asyncio` `loop_scope="session"` — consistent with W1
- `httpx.AsyncClient(app=app, base_url="http://test")` — no real server
- `httpx_ws` for WebSocket tests
- All tests hit real Postgres (testcontainers) and real Redis (testcontainers)
- Auth fixtures: generate Ed25519 keypair, run pairing flow, return token
- No mocking of DB or Redis — W1 pattern maintained

---

## 10. Acceptance Criteria

- [ ] `POST /api/v1/auth/pair` creates sessions row, returns valid EdDSA JWT
- [ ] `GET /api/v1/jobs` returns paginated list, respects `per_page` max=200
- [ ] `POST /api/v1/pipeline/trigger` enqueues Celery task, replay returns cached response
- [ ] Revoked device token rejected with 401 on next request
- [ ] WS client receives `run.started` event published by task
- [ ] `auth_refresh` event sent when token iat > 6 days
- [ ] `/docs` returns 404 in production environment
- [ ] Rate limit: 6th pairing attempt from same IP within 60s → 429
- [ ] All `tests/api/` tests pass against testcontainers Postgres+Redis
- [ ] `alembic upgrade head` applies sessions migration cleanly
