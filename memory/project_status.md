---
name: W2 Implementation Status
description: Current branch, completed tasks, next task, and key implementation decisions for W2 API + Auth
type: project
---

Branch: `prod/w1-foundation`

**Why:** W2 adds FastAPI backend with EdDSA JWT device-pairing auth, REST API, WebSocket bridge, idempotency middleware. Plan at `docs/superpowers/plans/2026-04-24-w2-api-auth.md`. Spec at `docs/superpowers/specs/2026-04-24-w2-api-auth-design.md`.

**How to apply:** Resume subagent-driven development at Task 5. Use `superpowers:subagent-driven-development` skill. For each task: dispatch implementer → spec review → code quality review → fix issues → mark complete.

---

## Completed Tasks (Tasks 0–4)

| Task | Commit(s) | Notes |
|------|-----------|-------|
| 0: Add deps | bb1b80a, a51139d | PyJWT[crypto]==2.9.0, qrcode==7.4.2, cryptography==47.0.0 |
| 1: Extend Settings | 528c03b, 3d8ec7c, 8527245 | 11 new fields; Literal types for jwt_algorithm/environment; model_validator rejects placeholder key in non-dev |
| 2: Revise Device ORM | 5c5822a, 13dfc0f | Session model dropped; public_key LargeBinary→Text; added pairing_ip/last_ip/last_user_agent INET/Text; InetString TypeDecorator for asyncpg coercion |
| 3: Alembic migration | ec4b3fa, 5ed6d50 | Alembic at src/data/migrations/ (pre-existing); async env.py with single run_sync; migration adds 3 columns, drops sessions, casts public_key via convert_from(bytea,'UTF8') |
| 4: DevicesRepository | d968261, 68ecdc2 | get/create/touch/revoke; touch/revoke use self.session (not passed session param); unique test keys with uuid suffix |

**HEAD commit:** `68ecdc2`

---

## Next Task: Task 5 — JWT Security Helpers

**Files:**
- Create: `src/api/__init__.py`
- Create: `src/api/core/__init__.py`
- Create: `src/api/core/security.py`
- Create: `tests/api/__init__.py`
- Create: `tests/api/test_security.py`

**What to build:**

```python
# src/api/core/security.py
def create_jwt(device_id: uuid.UUID, *, private_key_pem: str | None = None) -> str:
    # uses settings.jwt_private_key if private_key_pem not given
    # payload: sub=str(device_id), jti=uuid4, iat=now, exp=now+ttl_days*86400
    # signs with EdDSA via PyJWT

def decode_jwt(token: str, *, public_key_pem: str | None = None) -> dict:
    # uses settings.jwt_public_key if not given
    # decodes with leeway=settings.jwt_leeway_seconds
```

**Tests:**
- `test_create_and_decode_jwt` — round-trip
- `test_decode_jwt_wrong_key_raises` — InvalidSignatureError

**Package stubs to create first:**
```bash
mkdir -p src/api/core src/api/middleware src/api/routers src/api/services src/api/schemas
touch src/api/__init__.py src/api/core/__init__.py src/api/middleware/__init__.py
touch src/api/routers/__init__.py src/api/services/__init__.py src/api/schemas/__init__.py
mkdir -p tests/api
touch tests/api/__init__.py
```

---

## Remaining Tasks (6–19)

- Task 6: App factory + /health
- Task 7: Common schemas (PaginatedResponse, ErrorResponse)
- Task 8: Bootstrap CLI command
- Task 9: Auth schemas + Redis dependency
- Task 10: Auth service + challenge/pair endpoints (includes rate limiting fix: add ip param to store_challenge)
- Task 11: get_current_device dependency
- Task 12: Devices router (revoke)
- Task 13: Idempotency middleware
- Task 14: Jobs router + list_paginated
- Task 15: Runs router + list_paginated
- Task 16: Applications router + list_paginated
- Task 17: Pipeline trigger endpoint
- Task 18: ConnectionManager + WebSocket router
- Task 19: Status endpoint + serve CLI

---

## Key Architecture Decisions

- EdDSA JWT (not HS256) — asymmetric, Ed25519 keypair
- 3-step pairing: bootstrap secret → challenge → pair with signature
- JWT revocation: JTI in Redis (`revoked:jti:{jti}` with TTL); device-wide via `revoked_at` column
- Token rotation at 6 days (TTL is 7 days) via `X-Auth-Next-Token` header
- Idempotency: Stripe-style `Idempotency-Key` header, Redis `idem:{device_id}:{key}` TTL 24h
- WebSocket: ConnectionManager (`dict[str, set[WebSocket]]`) + Redis pubsub bridge
- Rate limiting: `pair:{ip}` Redis INCR → 5/min → 429 (in store_challenge, needs ip param)

## Key File Locations

- Settings: `src/settings.py` (get_settings LRU-cached)
- DB engine: `src/data/db.py` (get_engine, reset_engine_cache)
- Models: `src/data/models/` (Base, Device, Job, Run, Application, etc.)
- Repositories: `src/data/repositories/`
- Alembic: `src/data/migrations/` (NOT `alembic/`)
- Test conftest: `tests/conftest.py` (testcontainers Postgres+Redis, JWT key fixtures)
- Plan: `docs/superpowers/plans/2026-04-24-w2-api-auth.md`

## Known Pre-existing Failures

- `tests/test_notion_sync.py` — `FakeNotionAPIClient` missing `query_database` — unrelated to W2
- `scratch/test_api_flow.py` — scratch file, ignored
