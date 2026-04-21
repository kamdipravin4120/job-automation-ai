# Production-Grade Web App — Design Spec

**Project:** Job Automation AI — web backend + operator console
**Status:** Design, pending approval
**Author:** System architect (Claude Opus 4.7)
**Date:** 2026-04-21
**Consumers of this spec:** implementation agent, reviewers, future-me

---

## 0. Reading guide

This is the mega-spec covering all six phases of the production web-app build (W1–W6). Each phase has its own section (§4.1 through §4.6) with goals, deliverables, and acceptance criteria. The mobile companion (`docs/MOBILE_APP_PRD.md`) consumes the API defined here; this spec is the server-side contract.

The cross-cutting sections (§5 data, §6 auth, §7 self-correcting mechanisms, §8 observability, §9 deploy, §10 testing) apply to every phase. Read them once.

---

## 1. Goal

Turn the current Python job-automation pipeline into a production-grade, self-hostable service:

- **Reliable** — the system survives scraper breakage, LLM quota loss, network blips, and its own bugs without needing a human to SSH in.
- **Self-correcting** — detects its own failures and recovers; when it can't, produces actionable diagnostics instead of 40-line log tracebacks.
- **API-first** — the mobile companion, future iOS app, and operator web console all consume the same `/api/v1/*` surface.
- **Operator-ready** — a web console that surfaces integration health, DLQ items, per-run timelines, and config edits without touching shell.
- **One-command deploy** — `docker compose up -d` on a fresh VPS brings the full stack up with HTTPS.

## 2. Non-goals

- Multi-tenant SaaS. Single user, multiple devices. (User management is device pairing, not usernames/passwords.)
- Microservices. One Docker-Compose stack is enough.
- Kubernetes. YAGNI at this scale.
- Real-time analytics / BI. Postgres + a dashboard is plenty.
- Supporting job boards beyond LinkedIn / Naukri / Indeed / Glassdoor in v1.
- Replacing Claude or OpenAI with a local model. Provider swap is a later concern.

## 3. Architecture overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                           Caddy (HTTPS + HTTP/3)                      │
│          automatic TLS, reverse-proxy to FastAPI, websocket passthru  │
└─────────────────────────────────┬────────────────────────────────────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │  FastAPI  (api + ws)       │    ┌────────────────┐
                    │  Auth · Routers · Schemas  │◄───┤  Redis         │
                    │  Celery enqueue · WS proxy │    │  broker + pubsub│
                    └─────────────┬──────────────┘    └────────┬───────┘
                                  │                            │
                    ┌─────────────▼──────────────┐             │
                    │  Celery workers             │◄────────────┘
                    │  Playwright · Claude · GPT  │
                    │  Gmail SDK · LinkedIn Flow  │
                    └─────────────┬──────────────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │  Postgres (source of truth) │
                    └─────────────┬──────────────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │  artifacts/  (bind mount)   │
                    │  DOCX, PDF, screenshots      │
                    └────────────────────────────┘
```

### 3.1 Components

| Component | Responsibility | Notes |
|---|---|---|
| **Caddy** | TLS termination, HTTP→HTTPS redirect, WebSocket upgrade, 1 config file | Chosen over Traefik for zero-config TLS and readability |
| **FastAPI** | REST endpoints, OpenAPI schema, request validation, auth, enqueue jobs, WS multiplex | Never calls Playwright / Claude directly; always enqueues |
| **Celery workers** | Run the pipeline: scrape, match, tailor, apply, send mail, send DM | Split into queues by kind: `scrape`, `ai`, `browser`, `mail` so one slow browser job can't starve quick mail sends |
| **Redis** | Celery broker + result backend + idempotency-key store + pubsub for WS events | Single instance, persistence enabled (AOF) |
| **Postgres** | All persistent state | Alembic migrations, version-controlled schema |
| **artifacts/** | Generated DOCX / PDF / screenshots | Bind-mounted; signed-URL access from API |

### 3.2 Directory layout (target)

```
src/
  api/               ← NEW: FastAPI routers, request/response schemas, deps
    routers/         jobs.py, applications.py, drafts.py, runs.py, integrations.py, auth.py
    schemas/         pydantic request/response models
    deps/            auth, db session, current_device
    ws.py            WebSocket endpoint + topic multiplexer
  domain/            ← MOVED from top-level models.py: pure pydantic domain models
  data/              ← NEW: SQLAlchemy models + Alembic
    models/
    repositories/    one per aggregate (jobs, applications, runs, drafts)
    migrations/      alembic env + versions
  tasks/             ← NEW: Celery tasks, one file per pipeline stage
    scrape.py · match.py · tailor.py · apply.py · mail.py · dm.py
  services/          ← REFACTOR: existing orchestrator/, matcher/, resume/, scraper/, apply/
    scraper/         unchanged layout
    matcher/         unchanged
    resume/          unchanged
    apply/           unchanged
    gmail/           ← NEW
    linkedin_dm/     ← NEW
  selfheal/          ← NEW: selector repair, output validation, drift detection
    selector_repair.py
    output_validator.py
    drift_detector.py
  integrations/      ← NEW: external-service adapters (Gmail, Notion, FCM)
  utils/             unchanged
main.py              CLI stays; gains 'serve', 'worker', 'migrate' commands
config.yaml          unchanged format; loaded via pydantic-settings
```

## 4. Phase plan

Each phase ends with a runnable, user-visible state. No phase depends on a later phase. Each phase has its own acceptance test list at the end of §4.x.

### 4.1 Phase W1 — Foundation: Postgres, Celery, typed errors

**Goal:** the existing pipeline runs unchanged from the CLI, but storage is Postgres, long tasks are Celery, errors are typed.

**Deliverables:**

1. **Postgres schema** (see §5) via Alembic. Migrate existing SQLite records with a one-shot `migrate-sqlite` CLI command.
2. **SQLAlchemy models + repositories** per aggregate (`jobs`, `applications`, `runs`, `drafts`, `threads`, `devices`, `integrations`, `audit_log`).
3. **Celery + Redis** wiring, with four named queues (`scrape`, `ai`, `browser`, `mail`).
4. **Pipeline stages as Celery tasks** — `scrape_job_board`, `embed_and_match`, `tailor_resume`, `submit_application`, `send_email`, `send_linkedin_dm`. Each task is **idempotent** keyed by `(stage, correlation_id)`.
5. **Typed error domain** — `src/errors.py` with a small hierarchy: `PipelineError`, `ExternalServiceError`, `SelectorBrokenError`, `LLMValidationError`, `AuthenticationExpiredError`, `RateLimitExceededError`, `UserActionRequiredError`. Every raise sets `error_code: str` that UI/API can match on.
6. **Structured logging** — switch to `structlog`, JSON output in prod, key-value in dev. Every log line carries `correlation_id`, `run_id`, `stage`.
7. **pydantic-settings** replaces the ad-hoc `load_config`. Fail-fast on boot if required env vars missing.

**Deprecated in this phase:** CSV tracking mode, direct SQLite file access. The CLI commands still work; they now talk to Postgres.

**Acceptance:**
- `python main.py pipeline` runs end-to-end against Postgres with no code changes in `src/services/*`.
- Killing `redis` mid-run: Celery retries with backoff, run resumes after Redis comes back.
- Killing a worker mid-tailor: the task is reassigned, idempotency key prevents duplicate Claude call.
- `alembic upgrade head` on an empty DB produces the full schema.
- `migrate-sqlite --from artifacts/tracking.sqlite` imports every existing row lossless.

### 4.2 Phase W2 — API + auth (device pairing)

**Goal:** every operation the CLI can do is reachable over HTTPS by an authenticated device. Mobile companion work (SP1 prerequisite) unblocks.

**Deliverables:**

1. **FastAPI app** refactored per §3.2 (routers, schemas, deps).
2. **Device-pairing auth** per `docs/MOBILE_APP_PRD.md` §7.1:
   - `POST /api/v1/auth/pair` with bootstrap secret + device public key (Ed25519).
   - Session tokens stored as `token_hash` (argon2id) in `sessions` table.
   - `Authorization: Bearer` middleware on all non-auth endpoints.
   - Auto-rotate token via `X-Auth-Next-Token` response header after 6 days.
   - `GET/DELETE /auth/devices`.
3. **Bootstrap QR flow** — on first boot the API prints `https://<host>/?bs=<secret>` encoded as QR to stdout. Single-use; invalidated after first pair.
4. **REST surface** matching mobile PRD §8: jobs, runs, applications, drafts, threads, integrations, profile, config.
5. **WebSocket endpoint** `/ws` with topic subscription protocol (`run:{id}`, `jobs:new`, `apps:status`). Celery workers emit events to Redis pubsub channels; FastAPI bridges pubsub → subscribed WS clients.
6. **Idempotency-Key** middleware on `POST`s that enqueue runs. Replay returns the original `run_id`.
7. **OpenAPI 3.1 schema** generated and committed to `docs/api/openapi.json` for the mobile client to code-gen against.
8. **CSRF protection** for browser flows (Caddy sets `__Host-` cookie, FastAPI verifies double-submit token).
9. **Web operator session** — same device-pairing flow, but a browser's Keystore equivalent is WebAuthn (platform authenticator); falls back to a single passphrase stored argon2id if WebAuthn unavailable.

**Acceptance:**
- `curl -X POST /api/v1/auth/pair` with a valid bootstrap secret returns a session token.
- Re-using bootstrap secret returns 401.
- Subsequent `curl /api/v1/jobs` with the token returns the job list; without it, 401.
- WebSocket `{op:"subscribe", topic:"run:abc"}` delivers real-time events emitted by a running Celery task.
- `Idempotency-Key` replays return the same `run_id` and do not re-enqueue.
- OpenAPI doc round-trips through `openapi-generator` into a valid Kotlin client.

### 4.3 Phase W3 — Web operator console (admin-first)

**Goal:** a single-page web app at `https://<host>/` that is the operator/admin console. Dedicated to things the phone shouldn't do.

**Deliverables:**

1. **Tech choice** — stay with vanilla HTML/CSS/JS (current `static/`) to avoid a build step and npm dependency surface. Modern browser support only; CSS grid; fetch API; native web components for reusable UI.
2. **Routes:**
   - `/` — dashboard: pipeline health per integration, recent runs, DLQ badge count, KPIs.
   - `/integrations` — connect/reconnect Gmail (OAuth button), LinkedIn (Playwright login with live screenshot stream over WS for 2FA), set API keys (OpenAI, Anthropic, Gemini).
   - `/runs` — list all Celery runs with filters; click to open run detail with timeline + step screenshots + retry button.
   - `/dlq` — dead-letter queue: failed runs with Claude-generated diagnosis, "Retry", "Investigate" (opens full state snapshot), "Dismiss".
   - `/config` — safe config editing. YAML editor with schema validation; diff view before save; "Test config" button that re-parses without applying; Alembic-style undo for the last N changes.
   - `/audit` — append-only activity log with filters.
   - `/selectors` — self-healed selectors awaiting review. Approve → writes into `config.yaml`; Reject → restores previous.
3. **Design** — continues the tactical aesthetic from the existing `static/` files. Reuse `static/dashboard-preview.html` and `static/samples.html` as the design language reference. Accessibility: keyboard nav, focus rings, color-independent status.
4. **Admin-only scope:** No job-browsing UI (that's the phone). No resume editing (phone). No apply (phone). No follow-up composer (phone). Web is the wrench; phone is the dashboard.

**Acceptance:**
- All routes load in < 500 ms from a cold cache on LAN.
- Gmail OAuth connect button completes round-trip and `GET /api/v1/integrations` shows `gmail: connected`.
- Editing `config.yaml` via the UI updates Postgres and triggers Celery workers to reload; invalid YAML blocked with an inline schema error.
- Self-healed selectors approved via the UI are persisted to `config.overrides.yaml` with provenance.

### 4.4 Phase W4 — Self-correcting mechanisms

**Goal:** the five self-correcting mechanisms from the brainstorm (§7) ship here. This is where "production-grade" graduates from "wrapped-in-try/except" to "detects and recovers from its own failures."

See §7 for detailed designs. Deliverables:

1. **Selector self-healing** — when a scrape returns 0 jobs on a page with known landmarks, the worker snapshots the DOM, Claude proposes a new selector, system tests it, on success stages it to `config.overrides.yaml` pending operator review via W3.
2. **Output validation with regeneration loop** — every LLM output validated against a schema + semantic checks; failures trigger up-to-2 regenerations with validator feedback appended.
3. **Apply-flow drift detection** — Claude screenshot-check before final submit.
4. **Idempotent retry framework** — all stages `(stage, correlation_id)`-keyed; exponential backoff; per-service daily caps; DLQ after exhaustion.
5. **Structured diagnostics** — DLQ entries include last error, full state snapshot, last-3-step timeline, Claude one-line summary, suggested action.

**Acceptance:**
- Induce a selector break (rename a CSS class in test HTML): scraper detects 0 results, triggers repair, proposes a new selector, system writes to `config.overrides.yaml`, operator sees it in `/selectors`.
- Induce LLM output failure (prompt-inject to omit a required key): validator catches, regenerates once with error feedback, succeeds. Audit log shows regeneration.
- Simulate a submit page with missing submit button: drift detector pauses the flow and surfaces `UserActionRequiredError`.
- Kill Claude API 5 times in a row: pipeline stops retrying, DLQ entry created, next scheduled run pre-flights and skips tailoring stage.

### 4.5 Phase W5 — Gmail + LinkedIn follow-ups

**Goal:** end-to-end follow-up flows that the phone consumes.

**Deliverables:**

1. **Gmail OAuth** — installed-app-style OAuth (desktop flow; for a VPS we use "limited input device" or pop Chrome on the operator side). Refresh tokens stored encrypted (§6) in `integrations.credentials_encrypted`.
2. **Gmail send** — `POST /drafts/{id}/send` with `channel: "gmail"` dispatches via `google-api-python-client`. Threading: replies attach to the same thread ID if known; otherwise new thread with a standardized subject line prefix.
3. **Inbound Gmail polling** — every 10 minutes, poll Gmail for replies matching tracked thread IDs; write to `threads` with direction `in`; emit `apps:status` WS event + FCM push if a thread has unread incoming.
4. **LinkedIn DM via Playwright** — dedicated Celery task on the `browser` queue. Strict rate limits enforced server-side: max 5 per day, 45-minute gap. CAPTCHA detection pauses the task with `AuthenticationExpiredError`. Feature-flagged via `config.linkedin_dm.enabled`.
5. **Draft lifecycle** — `POST /applications/{id}/followup` creates a Claude-drafted entry in `drafts`. `PATCH /drafts/{id}` accepts user edits. `POST /drafts/{id}/send` dispatches. Status transitions logged in `audit_log`.
6. **Tone rewrites** — `POST /drafts/{id}/rewrite?tone=warm|professional|assertive` returns a regenerated body; chosen variant promoted on user pick.

**Acceptance:**
- End-to-end: create job → apply → draft follow-up → send Gmail → receive mocked reply → status change delivered to phone.
- Sending the 6th LinkedIn DM in a day: 429 with `error.code = "rate_limit_exceeded"` and `retry_after_seconds`.
- CAPTCHA simulated during LinkedIn DM: task pauses, phone receives approval request with screenshot over WS.

### 4.6 Phase W6 — Deploy + observability

**Goal:** a fresh VPS boots the whole stack in under 5 minutes with one command; ops hygiene is in place.

**Deliverables:**

1. **docker-compose.production.yml** — services: `caddy`, `api`, `worker-scrape`, `worker-ai`, `worker-browser`, `worker-mail`, `redis`, `postgres`. Healthchecks on every service. Resource limits. Read-only root filesystems where possible.
2. **Caddyfile** — one-liner that reverse-proxies to FastAPI and handles LetsEncrypt.
3. **Bootstrap script** — `scripts/vps-bootstrap.sh` takes a domain and an email and produces a `.env` + runs `docker compose up -d`. Prints QR pairing token.
4. **Prometheus metrics** — `/metrics` endpoint on FastAPI + on each Celery worker. Counters: `pipeline_runs_total{stage,status}`, `llm_tokens_total{provider,model}`, `external_errors_total{service}`. Histograms: `stage_duration_seconds{stage}`. (No Grafana required in v1; `curl /metrics` is enough. Prometheus server optional.)
5. **Backups** — `pg_dump` nightly via a cron container; uploads to a user-configured S3-compatible target; retains 14 dailies. Artifacts tarballed weekly.
6. **Health endpoint** — `/healthz` returns DB reachable, Redis reachable, last successful scrape-age, integration statuses. Caddy uses it for readiness. Mobile uses it for a Status screen.
7. **Graceful shutdown** — SIGTERM drains running Celery tasks for up to 60 s before killing; FastAPI stops accepting new connections immediately.
8. **CI** — GitHub Actions runs unit + contract tests on every push; builds and pushes Docker images on tagged releases.

**Acceptance:**
- `./scripts/vps-bootstrap.sh example.com admin@example.com` on a clean Ubuntu 24.04 VPS brings a paired, HTTPS-serving instance up in ≤ 5 min.
- `curl https://example.com/healthz` returns `200` once all services are green.
- `systemctl restart docker` mid-run: all runs either complete or land in DLQ with diagnostics; no silent data loss.
- Backup restore from a dump produces an identical `applications` table (checked by row-count + deterministic hash).

---

## 5. Data model (Postgres, Alembic-managed)

Full SQL in `src/data/migrations/versions/0001_initial.py`. Summary of tables:

```
devices           (id uuid pk, name text, public_key bytea unique, paired_at timestamptz,
                   last_seen_at timestamptz, revoked_at timestamptz null)

sessions          (token_hash bytea pk, device_id uuid fk devices, issued_at timestamptz,
                   rotates_at timestamptz, revoked_at timestamptz null)

integrations      (provider text pk {gmail|linkedin|openai|anthropic|gemini|notion|fcm},
                   status text {connected|disconnected|error}, credentials_encrypted bytea null,
                   last_error text null, last_check_at timestamptz null)

jobs              (id uuid pk, source text, source_id text, url text,
                   title text, company text, location text, salary_band jsonb null,
                   jd_text text, scraped_at timestamptz,
                   match_score float, score_breakdown jsonb,
                   status text {new|starred|applied|dismissed},
                   user_notes text, unique (source, source_id))

job_artifacts     (id uuid pk, job_id uuid fk jobs, kind text {resume|cover|pitch|jd_snapshot},
                   file_path text, text text, version int, generated_at timestamptz)

applications      (id uuid pk, job_id uuid fk jobs unique, submitted_at timestamptz,
                   channel text {easy_apply|external}, external_ref text null,
                   current_status text {submitted|acknowledged|interview|offer|rejected|ghosted},
                   status_history jsonb, recruiter jsonb, notes text, briefing_json text null)

runs              (id uuid pk, kind text {scrape|match|tailor|apply|login|send_mail|send_dm|repair_selector|validate_llm},
                   correlation_id text, idempotency_key text null,
                   job_id uuid null, application_id uuid null,
                   status text {queued|running|waiting_approval|succeeded|failed|dead},
                   started_at timestamptz, finished_at timestamptz null,
                   error_code text null, error_details jsonb null,
                   steps jsonb,  -- array of {name, status, at, screenshot_path, notes}
                   retry_count int default 0, next_retry_at timestamptz null,
                   unique(kind, correlation_id))

drafts            (id uuid pk, application_id uuid fk applications, channel text {gmail|linkedin},
                   subject text null, body text, tone text,
                   created_by text {ai|user}, parent_draft_id uuid null,
                   created_at timestamptz, edited_at timestamptz null)

threads           (id uuid pk, application_id uuid fk applications, channel text {gmail|linkedin},
                   direction text {out|in}, body text, sent_at timestamptz,
                   external_id text null,
                   unique(channel, external_id))

selector_overrides (id uuid pk, source text, key_path text, selector text,
                    proposed_at timestamptz, proposed_by text {heal|operator},
                    status text {pending|approved|rejected},
                    dom_snapshot_path text, provenance jsonb)

audit_log         (id bigserial pk, at timestamptz, actor text, action text,
                   target text, details jsonb)

fcm_tokens        (id uuid pk, device_id uuid fk devices, token text unique, last_seen_at timestamptz)

config_versions   (id bigserial pk, applied_at timestamptz, actor text, diff_patch text, rolled_back bool)
```

**Encryption.** `integrations.credentials_encrypted` uses AES-256-GCM with a KEK from `JOB_AUTOMATION_KEK` env var (32 random bytes, base64). Rotation procedure: set `JOB_AUTOMATION_KEK_PREVIOUS` alongside the new one, run `python main.py rotate-secrets`, remove the old env var.

**Postgres version:** 16. Extensions used: `uuid-ossp`, `pg_trgm` (for future full-text on JD).

## 6. Auth & secrets

### 6.1 Device session
Per `docs/MOBILE_APP_PRD.md §7.1`. `token_hash = argon2id(session_token)` with interactive-tier parameters; the plaintext token is never stored.

### 6.2 Secret hierarchy
- **KEK** — env var, never in DB.
- **Third-party creds** — DB, encrypted with KEK.
- **Bootstrap secret** — env var, single-use, zeroed from memory after pair.
- **API keys (OpenAI etc.)** — may be env var for simplicity, or DB-encrypted via the `/integrations` flow. Both supported; env var wins precedence.

### 6.3 Request signing (optional, off by default)
For very-sensitive endpoints (`DELETE /auth/devices`, `PATCH /config`) we optionally require an Ed25519 signature using the device's Keystore private key: `X-Signature: base64(sign(canonicalize(request)))`. Off in v1; design accommodates it.

## 7. Self-correcting mechanisms (the distinctive bit)

Five mechanisms. All live under `src/selfheal/`. All emit audit-log entries.

### 7.1 Selector self-healing

**Detection signal:** a scraper returns 0 job cards *and* the page has ≥ 1 of `<nav>`, `<main>`, `<footer>`, or `data-testid`-bearing nodes → strong evidence the page loaded but our selector is stale.

**Repair flow:**
1. Worker writes the HTML to `artifacts/dom/{source}-{timestamp}.html`.
2. Worker asks Claude (function-call constrained): `repair_selector(source, stale_selector, html_fragment)` → returns a candidate CSS selector + confidence.
3. Worker retries the scrape with the candidate on the same page; if it yields ≥ 3 matches, the candidate is written to `config.overrides.yaml` with status `pending`, provenance `{ claude_response, confidence, tested_at, matches_count }`.
4. Operator sees it in `/selectors`; approving merges into `config.overrides.yaml` with status `approved`.

**Safety:** never runs on apply-flow selectors (too destructive if wrong). Limited to scrape-card/list selectors. Retried at most 3× per selector per week.

### 7.2 Output validation with regeneration

Every LLM output goes through `OutputValidator.validate(kind, payload, context)`. Kind-specific checks:

| Kind | Checks |
|---|---|
| `tailored_resume` | JSON schema; contains ≥ N keywords from JD (N = max(3, 5% of JD unique nouns)); word count within ±25% of source resume |
| `cover_letter` | No placeholder strings (`[Company]`, `Dear Sir/Madam`); mentions company name; 200–400 words |
| `recruiter_pitch` | 80–150 words; no first-person-plural ("we"); ends with CTA |
| `interview_briefing` | List of objects with `question`, `rationale`, `star_points[3..4]`; ≥ 5 items |
| `selector_repair_candidate` | Valid CSS selector syntax; confidence ≥ 0.6 |

**Regeneration:** on failure, append `Previous output failed validation: <complaint>. Please regenerate addressing this.` to the prompt. Max 2 retries. After 2 failures the error propagates as `LLMValidationError` and the user sees the last output with a banner; they can accept or edit manually.

### 7.3 Apply-flow drift detection

Before the final submit click in Easy Apply, screenshot the page. Claude call `verify_submit_page(screenshot, expected_title)` → `{ready: bool, reason: str}`. If `ready=false`, task transitions to `waiting_approval`, user sees the screenshot + reason on phone, decides.

Budget: ~1¢ per apply (one small Claude vision call). Opt-out via `config.apply.drift_check: false`.

### 7.4 Idempotent retry framework

`@pipeline_task(stage, max_retries, backoff, daily_cap, queue)` decorator:

```python
@pipeline_task(stage="tailor", max_retries=2, backoff="expo", daily_cap=100, queue="ai")
def tailor_resume(correlation_id, job_id): ...
```

- `correlation_id` + `stage` = unique key, stored in Redis for 24h.
- On exception:
  - `ExternalServiceError` → backoff and retry.
  - `LLMValidationError` → regenerate (§7.2) rather than retry.
  - `UserActionRequiredError` → set run status `waiting_approval`, do not retry.
  - `RateLimitExceededError` → respect `retry_after`, retry after.
  - Anything else → fail the run; if retry budget left, retry; else → DLQ.
- Daily cap per `(service, date)` counter in Redis; exceeding blocks new tasks until next UTC day with explicit `CapExceeded` error surfaced in DLQ.

### 7.5 DLQ + structured diagnostics

Failed runs with exhausted retries land in `runs.status = 'dead'`. On write, a Celery task `diagnose_dead_run(run_id)`:
1. Pulls the run's full error, steps timeline, last screenshot (if any).
2. Claude call: `diagnose_run(error, steps, screenshot_url)` → one-line summary + suggested action (`retry` / `reconnect_linkedin` / `update_selector` / `manual`).
3. Writes `runs.error_details.diagnosis`.

Operator sees a single row in `/dlq` per dead run: status, summary, suggested action button. One click to retry / reconnect / open selector repair.

## 8. Observability

- **Logs:** `structlog`, JSON, every line carries `{correlation_id, run_id, stage, service}`. Shipped to stdout; Docker collects. Optional Loki adapter for later.
- **Metrics:** Prometheus text format at `/metrics`. Counters and histograms listed in §4.6.
- **Audit log:** every side-effect (apply, send mail, send dm, config change, integration connect/disconnect) writes a row to `audit_log`. Append-only; no deletes.
- **Tracing:** OpenTelemetry SDK installed, exporter configurable; defaults to no-op in v1. Makes adding Tempo/Jaeger later a one-line env change.
- **Error reporting:** `sentry_sdk` integration, opt-in via `SENTRY_DSN`. PII scrubbing filter in place (JD text, email bodies).

## 9. Deploy

One-liner on a fresh Ubuntu 24.04 VPS:

```bash
curl -fsSL https://raw.githubusercontent.com/<repo>/master/scripts/vps-bootstrap.sh \
  | bash -s -- example.com admin@example.com
```

The script:
1. Installs Docker + compose plugin if absent.
2. Clones the repo to `/opt/job-automation-ai`.
3. Generates `.env` with fresh `JOB_AUTOMATION_KEK`, `POSTGRES_PASSWORD`, `BOOTSTRAP_SECRET`.
4. Writes Caddyfile with `example.com`.
5. Runs `docker compose -f docker-compose.production.yml up -d`.
6. Waits for `/healthz`, prints the pairing QR code + bootstrap secret.

No secrets in the repo. No secrets in CI. Rotation: edit `.env`, `docker compose up -d` picks up changes and restarts.

## 10. Testing strategy

Per `docs/APP_GUIDELINES.md` testing section adapted to Python/FastAPI.

| Layer | Tool | What gets tested |
|---|---|---|
| **Unit** | `pytest` | Pure domain logic: scoring, validators, selector repair candidate synthesis (mocked Claude) |
| **Contract** | `pytest` + `respx` / `pytest-httpserver` | Every external adapter (LinkedIn, Indeed, Gmail, Claude, OpenAI, Gemini). Record-replay mode against live APIs, gated by `RUN_CONTRACT_TESTS=1` |
| **API** | `pytest` + `httpx.AsyncClient` against a test FastAPI app | Every endpoint: auth required, request/response schemas, error codes |
| **Integration** | `pytest` + `testcontainers` (Postgres + Redis) | Celery round-trip: enqueue → task runs → DB state is expected |
| **E2E** | `pytest` + Playwright | One happy-path: scrape fake job board served by `pytest-httpserver` → match → tailor → fake-apply → follow-up draft |
| **Self-heal** | `pytest` | Induce selector break on a fixture page; verify repair emits an override candidate |
| **Load** | `locust` (optional) | Dashboard load with 100 concurrent mobile clients; WS fan-out |

CI matrix: Python 3.11 + 3.12, Postgres 16, Redis 7.

**Coverage gate:** 80% line coverage on `src/selfheal/`, `src/api/`, `src/data/repositories/`, `src/tasks/`. No gate on `src/services/scraper/*` (selectors drift; brittle tests are worse than no tests).

## 11. Rollout & migration

From the current state (commit `ad6c571`):

1. **W1 first** on a feature branch `prod/w1-foundation`. Existing CLI pipeline continues to work unchanged. Merge when the acceptance tests pass.
2. **W2** on branch `prod/w2-api`. Old `static/` dashboard continues to serve under `/` until W3 replaces it.
3. **W3** on branch `prod/w3-console`. Cuts over `/` to the new operator console; old endpoints retained under `/legacy/` for one release.
4. **W4** on branch `prod/w4-selfheal`. Gated by a feature flag per mechanism so each can be rolled back independently.
5. **W5** on branch `prod/w5-followup`. Gmail first, LinkedIn DM behind `config.linkedin_dm.enabled` (default off).
6. **W6** on branch `prod/w6-deploy`. Production cutover.

Each branch produces a PR with: spec link, acceptance-test report, coverage delta, changelog entry.

## 12. Risks & mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| LinkedIn detection / account restriction | Medium | High | Rate limits, CAPTCHA detection, feature flag kill-switch, prefer Gmail path |
| Playwright selector drift in scrapers | High (weekly) | Medium | Self-healing §7.1; ordered fallback selectors already in place |
| Claude/OpenAI vendor quota or outage | Medium | Medium | Vendor-agnostic interfaces; `OutputValidator` works across vendors; Gemini already present as a secondary |
| Self-healing proposes wrong selector, corrupts downstream data | Low | High | Proposals land in `pending` state, require operator approval in W3 before merging |
| KEK leak via operator error | Low | Critical | Single env var, not in repo, not in backups; rotation procedure documented; `/audit` surfaces any `credentials_encrypted` read |
| Postgres data loss | Low | High | Nightly `pg_dump` to S3-compatible storage; tested restore in CI |
| VPS compromise | Low | Critical | Key rotation doc; audit log; fail-closed on token verification; MFA on the VPS provider account |

## 13. Open questions (to decide before W1 starts)

1. **Backup target.** Which S3-compatible provider? (Backblaze B2 is cheapest; Cloudflare R2 has no egress.) — **my call:** Backblaze B2, easy cheap, migrateable later.
2. **Gemini retention.** The current Gemini client (for LinkedIn analysis + briefing) is a second AI provider. Keep alongside Claude forever, or deprecate after Claude covers the same prompts? — **my call:** keep; it's a useful fallback + hedge and its prompts are already tuned.
3. **Streamlit dashboard.** Delete in W3 cutover, or keep as a read-only analytics pane? — **my call:** delete. W3 console covers the admin need; Streamlit adds a second dependency stack.
4. **Notion sync.** Current optional integration. Keep, or cut? — **my call:** keep behind feature flag; nothing depends on it and some users like the shareability.
5. **Multi-profile support.** Multiple `profile.json` files (one per job search focus)? — **my call:** out of scope v1; add a `profile_id` column everywhere so we're not blocked later.

If any of my calls in (1–5) are wrong, say so before W1 starts — they're cheap to change now, expensive later.

---

## Appendix A — Minimal `.env` for production

```env
# Secrets (generated by bootstrap script)
JOB_AUTOMATION_KEK=<base64, 32 bytes>
POSTGRES_PASSWORD=<random>
BOOTSTRAP_SECRET=<random, single-use>

# External services
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=

# Optional
SENTRY_DSN=
NOTION_API_KEY=
BACKUP_S3_ENDPOINT=
BACKUP_S3_BUCKET=
BACKUP_S3_ACCESS_KEY_ID=
BACKUP_S3_SECRET_ACCESS_KEY=

# Domain
PUBLIC_DOMAIN=example.com
ADMIN_EMAIL=admin@example.com
```

## Appendix B — Directory-tree delta summary

**New:**
- `src/api/` · `src/data/` · `src/tasks/` · `src/selfheal/` · `src/services/gmail/` · `src/services/linkedin_dm/` · `src/integrations/` · `src/errors.py`
- `docker-compose.production.yml` · `Caddyfile` · `scripts/vps-bootstrap.sh`
- `docs/api/openapi.json`

**Moved:**
- `src/models.py` → `src/domain/models.py`
- `src/orchestrator/` + `src/matcher/` + `src/resume/` + `src/scraper/` + `src/apply/` → `src/services/*` (same content, re-namespaced)

**Deleted in W3 cutover:**
- `src/app.py` → replaced by `src/api/main.py`
- `src/tracking/streamlit_dashboard.py`
- current `static/*.html` → replaced by the new operator console (dashboard-preview.html, samples.html retained as design references)

**Unchanged:**
- `config.yaml` format · `data/profile.json` · `tests/` structure (expanded)
