# Production Deployment — job-automation-ai

Full requirements for production-grade deployment of the job automation platform
with Operator Console (W3).

---

## Architecture Overview

```
Internet
    │
    ▼
[Nginx / Caddy]  ← TLS termination, port 443
    │
    ▼
[FastAPI API Server]  :8000
    ├── /api/v1/*        — REST API (jobs, auth, integrations, dlq, config, audit, selectors)
    ├── /ws              — WebSocket (real-time job events)
    ├── /static/*        — SPA assets (JS, CSS)
    └── /*               — Orbital Command SPA (index.html catch-all)
    │
    ├──► [Postgres 16]   :5432  (jobs, runs, audit logs, devices, selector overrides)
    └──► [Redis 7]       :6379  (Celery broker, result backend, JWT JTI revocation, config-reload pubsub)

[Celery Workers]
    ├── worker-scrape    (concurrency 1, Playwright Chromium)
    ├── worker-browser   (concurrency 1, Playwright Chromium)
    ├── worker-ai        (concurrency 4, OpenAI / Anthropic / Gemini)
    └── worker-mail      (concurrency 2, Gmail OAuth)
```

---

## Server Requirements

### Minimum (single VPS, personal use)

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU      | 2 vCPU  | 4 vCPU      |
| RAM      | 4 GB    | 8 GB        |
| Disk     | 20 GB   | 50 GB SSD   |
| OS       | Ubuntu 22.04 LTS | Ubuntu 24.04 LTS |

**Note:** Playwright Chromium requires ~400 MB RAM per browser instance.
`worker-scrape` + `worker-browser` = 2 concurrent instances minimum.
RAM floor is effectively 3 GB just for workers.

### Production (separate services)

| Service | CPU | RAM | Notes |
|---------|-----|-----|-------|
| API server | 1 vCPU | 512 MB | FastAPI + uvicorn |
| Celery workers | 2 vCPU | 3 GB | Playwright needs headless Chromium |
| Postgres | 1 vCPU | 1 GB | Managed DB preferred |
| Redis | 1 vCPU | 512 MB | Managed Redis preferred |

---

## Required Software

```bash
# System packages
docker >= 24.0
docker compose >= 2.20
python >= 3.12
playwright (bundled in Docker image)

# Optional (if not using Docker)
postgresql-client-16
redis-tools
nginx or caddy
certbot (if using Let's Encrypt with nginx)
```

---

## Environment Variables

### Required — App will fail to start without these

| Variable | Example | Notes |
|----------|---------|-------|
| `OPENAI_API_KEY` | `sk-...` | GPT-4o for resume/cover generation |
| `ANTHROPIC_API_KEY` | `sk-ant-...` | Claude for job matching + AI scoring |
| `DATABASE_URL` | `postgresql+asyncpg://jobauto:PASSWORD@db:5432/jobautomation` | asyncpg driver required |
| `CELERY_BROKER_URL` | `redis://redis:6379/0` | Celery task queue |
| `CELERY_RESULT_BACKEND` | `redis://redis:6379/1` | Celery result storage |

### Required in staging/production (optional in development)

| Variable | Example | Notes |
|----------|---------|-------|
| `JWT_PRIVATE_KEY` | `-----BEGIN PRIVATE KEY-----\n...` | Ed25519 PEM, `\n` escaped as `\\n` in .env |
| `JWT_PUBLIC_KEY` | `302a300506032b6570...` | Ed25519 DER hex (not PEM) |
| `ENVIRONMENT` | `production` | Triggers JWT key validation at boot |

### Optional — features degrade gracefully without these

| Variable | Default | Notes |
|----------|---------|-------|
| `GEMINI_API_KEY` | — | Google Gemini fallback model |
| `NOTION_API_KEY` | — | Sync matched jobs to Notion tracker DB |
| `SENTRY_DSN` | — | Error monitoring |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `LOG_FORMAT` | `json` | `json` (prod) or `kv` (dev) |
| `CONFIG_PATH` | `config.yaml` | Feature config file path |
| `PROFILE_PATH` | `data/profile.json` | User profile (name, skills, preferences) |

### Tunable — safe to leave at defaults

| Variable | Default | Notes |
|----------|---------|-------|
| `JWT_TTL_DAYS` | `7` | JWT validity window |
| `JWT_ROTATION_DAYS` | `6` | Browser silently refreshes after this many days |
| `JWT_LEEWAY_SECONDS` | `60` | Clock skew tolerance |
| `BOOTSTRAP_SECRET_TTL_SECONDS` | `600` | Bootstrap secret expires in 10 min |
| `RATE_LIMIT_PAIR_PER_MIN` | `5` | Max device pair attempts per IP per minute |
| `RATE_LIMIT_AUTH_PER_MIN` | `60` | Max auth requests per IP per minute |
| `APP_VERSION` | `0.2.0` | Reported in `/api/v1/health` |

### Docker Compose / Postgres only

| Variable | Default | Notes |
|----------|---------|-------|
| `POSTGRES_PASSWORD` | `devpassword` | **Change in prod.** Used by docker-compose.yml |

---

## API Keys — How to Get

### OpenAI
1. https://platform.openai.com/api-keys
2. Create key with "All" permissions
3. Enable billing. GPT-4o costs ~$0.005/job processed.

### Anthropic
1. https://console.anthropic.com/keys
2. Create key. Claude Sonnet 4.6 recommended.
3. Enable billing. ~$0.003/job processed.

### Gemini (optional)
1. https://aistudio.google.com/app/apikey
2. Free tier sufficient for personal use.

### Notion (optional)
1. https://www.notion.so/my-integrations → Create integration
2. Share target database with the integration
3. Copy "Internal Integration Token"

### Sentry (optional)
1. https://sentry.io → New Project → Python → FastAPI
2. Copy DSN from project settings

---

## JWT Keypair Generation

Ed25519 keypair required for device pairing auth. Generate once, store in secrets manager.

```bash
# Generate keypair
python -c "
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding, PrivateFormat, PublicFormat, NoEncryption
)
priv = Ed25519PrivateKey.generate()
pem = priv.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode()
der_hex = priv.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo).hex()
print('JWT_PRIVATE_KEY=' + pem.replace('\n', '\\\\n'))
print('JWT_PUBLIC_KEY=' + der_hex)
"
```

**Security rules:**
- Private key: never commit, never log, never send over HTTP
- Rotate keypair when: key suspected compromised, every 90 days (recommended)
- After rotation: all existing JWTs are immediately invalid (users re-pair)

---

## File & Volume Requirements

### Persistent volumes (must survive container restarts)

| Path | Type | Notes |
|------|------|-------|
| `/var/lib/postgresql/data` | Docker volume `pg_data` | All job/run/audit data |
| `/data` (Redis) | Docker volume `redis_data` | AOF persistence enabled |
| `./artifacts/` | Bind mount | Browser states, job dumps, resumes |
| `./logs/` | Bind mount | App logs |

### Configuration files (must exist at boot)

| File | Required | Notes |
|------|----------|-------|
| `config.yaml` | Yes | Scraper config, search queries, LLM settings |
| `data/profile.json` | Yes | User profile for resume/cover generation |
| `.env` | Yes | All secrets (or use env vars directly) |
| `config.overrides.yaml` | No | Auto-created by selectors approve API |

### Generated at runtime (do not commit)

```
artifacts/browser/linkedin_state.json   # LinkedIn session cookies
artifacts/jobs/jobs.json                # Job dump cache
artifacts/resumes/                      # Generated PDFs
artifacts/covers/                       # Generated cover letters
artifacts/pitches/                      # Generated pitch emails
```

---

## Services & Ports

| Service | Internal Port | External Port | Protocol |
|---------|--------------|---------------|----------|
| FastAPI API + SPA | 8000 | 443 (via proxy) | HTTPS |
| Postgres | 5432 | none (internal only) | TCP |
| Redis | 6379 | none (internal only) | TCP |
| Streamlit dashboard | 8501 | deprecated — remove in W4 | HTTP |

**Firewall rules:**
- Allow 443 inbound (HTTPS)
- Allow 80 inbound (HTTP → redirect to 443)
- Block 5432, 6379, 8000 from public internet
- Allow 22 inbound (SSH) from known IPs only

---

## Reverse Proxy (Nginx)

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate     /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # API + SPA
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket upgrade
    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}

server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$host$request_uri;
}
```

**Alternative: Caddy (simpler, auto-TLS)**

```caddyfile
your-domain.com {
    reverse_proxy localhost:8000
}
```

---

## Startup Order

Services must start in this order:

1. **Postgres** — must pass healthcheck before anything else
2. **Redis** — must pass healthcheck before anything else
3. **Alembic migrations** — `alembic upgrade head` (one-shot, before API starts)
4. **FastAPI API server** — `uvicorn src.api.app:app --host 0.0.0.0 --port 8000`
5. **Celery workers** — all four queues (scrape, ai, browser, mail)

---

## Production docker-compose.prod.yml (template)

```yaml
services:
  api:
    build: .
    command: uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --workers 2
    env_file: .env.prod
    ports:
      - "127.0.0.1:8000:8000"
    depends_on:
      postgres: {condition: service_healthy}
      redis: {condition: service_healthy}
    restart: unless-stopped
    volumes:
      - ./artifacts:/app/artifacts
      - ./logs:/app/logs
      - ./config.yaml:/app/config.yaml:ro
      - ./data:/app/data:ro

  migrate:
    build: .
    command: alembic upgrade head
    env_file: .env.prod
    depends_on:
      postgres: {condition: service_healthy}

  worker-scrape:
    build: .
    command: python main.py worker --queues scrape --concurrency 1
    env_file: .env.prod
    depends_on:
      postgres: {condition: service_healthy}
      redis: {condition: service_healthy}
    restart: unless-stopped
    volumes:
      - ./artifacts:/app/artifacts

  worker-ai:
    build: .
    command: python main.py worker --queues ai --concurrency 4
    env_file: .env.prod
    depends_on:
      postgres: {condition: service_healthy}
      redis: {condition: service_healthy}
    restart: unless-stopped

  worker-browser:
    build: .
    command: python main.py worker --queues browser --concurrency 1
    env_file: .env.prod
    depends_on:
      postgres: {condition: service_healthy}
      redis: {condition: service_healthy}
    restart: unless-stopped
    volumes:
      - ./artifacts:/app/artifacts

  worker-mail:
    build: .
    command: python main.py worker --queues mail --concurrency 2
    env_file: .env.prod
    depends_on:
      postgres: {condition: service_healthy}
      redis: {condition: service_healthy}
    restart: unless-stopped

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: jobautomation
      POSTGRES_USER: jobauto
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pg_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U jobauto -d jobautomation"]
      interval: 5s
      retries: 10
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: ["redis-server", "--appendonly", "yes", "--requirepass", "${REDIS_PASSWORD}"]
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 5s
      retries: 10
    restart: unless-stopped

volumes:
  pg_data:
  redis_data:
```

---

## Operator Console Access (W3)

After deployment, the Orbital Command console is at `https://your-domain.com`.

**First-time device pairing:**
```bash
# On the server
python main.py bootstrap
# Prints: Bootstrap secret: abc123def456...
```

1. Open `https://your-domain.com` in browser
2. Paste bootstrap secret into login screen
3. Browser generates Ed25519 keypair, signs challenge, receives JWT
4. JWT stored in `localStorage` — valid 7 days, auto-refreshes at day 6

**Bootstrap secret is single-use, expires in 10 minutes.**

---

## Deferred (not yet implemented)

| Feature | Target | Notes |
|---------|--------|-------|
| API key persistence (encrypted DB column) | W4 | Currently stub UI only |
| Gmail full OAuth (device-code flow) | W5 | Worker-mail uses placeholder auth |
| Config validate-without-save endpoint | Future | Plan spec'd, not built |
| WebAuthn device pairing | Future | Upgrade path from bootstrap secret flow |
| Multi-user / RBAC | Not planned | Single-operator tool by design |

---

## Backup Strategy

### Postgres
```bash
# Daily backup
pg_dump -U jobauto jobautomation | gzip > backup-$(date +%Y%m%d).sql.gz

# Restore
gunzip < backup-20260429.sql.gz | psql -U jobauto jobautomation
```

### Redis
- AOF persistence enabled by default (`--appendonly yes`)
- AOF file: `/data/appendonly.aof` inside container
- For point-in-time: enable RDB snapshots with `--save 3600 1 300 100 60 10000`

### JWT Keypair
- Store in a secrets manager (AWS Secrets Manager, Vault, 1Password Secrets)
- Never in version control

---

## Pre-Launch Checklist

- [ ] `ENVIRONMENT=production` set in .env
- [ ] `JWT_PRIVATE_KEY` + `JWT_PUBLIC_KEY` generated and set
- [ ] `POSTGRES_PASSWORD` changed from `devpassword`
- [ ] Redis password set (`requirepass`) and `CELERY_BROKER_URL` updated
- [ ] All required API keys set and tested
- [ ] Alembic migrations applied (`alembic upgrade head`)
- [ ] Reverse proxy configured with valid TLS cert
- [ ] Ports 5432, 6379, 8000 blocked from public internet
- [ ] `artifacts/` and `logs/` directories writable by container user
- [ ] `config.yaml` present with correct search queries
- [ ] `data/profile.json` present with user profile
- [ ] Smoke test: all 7 SPA routes load, bootstrap pairing works, one job pipeline run succeeds
- [ ] Backup cron configured for Postgres

---

*Generated: 2026-04-29 | Branch: prod/w3-console | Version: 0.2.0*
