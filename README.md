# Automated Job Application System

Production-oriented Python workflow for scraping jobs, ranking them with OpenAI embeddings, tailoring ATS-safe resumes with Claude, generating DOCX assets, running semi-automated LinkedIn Easy Apply, and tracking every step in CSV or SQLite.

## Development Status

**Branch:** `prod/w3-console` — W3 Operator Console **in progress** (2026-04-28)

| Phase | Status | What it builds |
|-------|--------|----------------|
| W1 Foundation | ✅ Complete | Async DB layer (SQLAlchemy + asyncpg), Celery pipeline (4 queues), Alembic migrations, CLI |
| W2 API + Auth | ✅ Complete | FastAPI backend, EdDSA JWT device-pairing auth, REST API, WebSocket bridge, idempotency middleware |
| W3 Operator Console | 🔄 In Progress | SPA operator UI (Orbital Command), integrations/DLQ/config/audit/selectors routers, boot-time autostart |
| W4–W6 | Planned | LinkedIn safety, Gmail classifier, push notifications, KEK rotation, rollback runbooks |

**W2 — all tasks complete (2026-04-26):**

| Tasks | What shipped |
|-------|--------------|
| 0–4 | Dependencies, settings, Device ORM, Alembic migration, DevicesRepository |
| 5–9 | Package stubs, `create_app()` factory, EdDSA JWT helpers, Redis dep, challenge/pair auth service |
| 10–12 | `get_current_device` dependency, JTI + device-wide revocation, token rotation, `DELETE /devices/{id}` |
| 13–14 | Idempotency middleware (Redis 24h cache), job/run/application read routers |
| 15–16 | Paginated list + detail endpoints for jobs, runs, applications |
| 17 | `POST /api/v1/pipeline/trigger` — enqueue scrape with idempotency; rate-limit on `/challenge` (5/min, SET NX EX) |
| 18 | `ConnectionManager`, WebSocket `/api/v1/ws`, Redis pubsub bridge (lifespan task) |
| 19 | `GET /api/v1/status` (auth-gated), `python main.py serve` CLI subcommand |

**W3 — shipped so far (2026-04-28):**

| Commit | What shipped |
|--------|--------------|
| `d49123e` | StaticFiles mount + SPA catch-all route |
| `4b48705` | AuditLog, Integration, SelectorOverride, ConfigVersion repositories |
| `935c854` | ACID-safe `IntegrationsRepository.upsert()` (INSERT ON CONFLICT) |
| `6aefe5d` | Pydantic schemas for integrations, DLQ, config, audit, selectors |
| `0ee19d0` | **Auth fix:** Ed25519 public-key transport switched PEM → DER hex (all 44 tests green) |
| `cfa7780` | **Auth fix:** `_normalize_pem()` expands `\n` escape from systemd env vars; JWT keypair added to `.env` |

**UI:** Complete OLED dark / HUD sci-fi design (Orbital Command) — CSS custom properties, radar animations, toast notifications, skeleton loading, SVG nav icons.

**Autostart:** 3-service systemd chain (`job-automation-ai-infra` → `job-automation-ai` → `job-automation-ai-browser`) launches Docker, FastAPI, and opens browser on login.

**Test suite:** 44/44 API tests pass (`tests/api/`)

**Session memory:** `memory/project_status.md`

**Pending (resume after reboot):**
- Verify full browser pairing flow works end-to-end (JWT key fix needs server restart with new env)
- Integrations/DLQ/Config/Audit/Selectors routers (Tasks 3–8 of W3 plan)

---

## Architecture

```text
src/
  api/          FastAPI app (W2+) — routers, services, schemas, middleware
    core/         security.py (JWT), deps.py (auth guard), connection_manager.py
    middleware/   idempotency.py
    routers/      auth, devices, jobs, runs, applications, pipeline, ws
    schemas/      pydantic request/response models
    services/     auth, devices business logic
  data/
    db.py         async SQLAlchemy engine (LRU-cached, reset_engine_cache)
    models/       ORM models — Device, Job, JobArtifact, Run, Application, …
    repositories/ JobsRepository, RunsRepository, ApplicationsRepository, DevicesRepository
    migrations/   Alembic (async env.py, versions/)
  tasks/        Celery app + task modules (scrape, ai, browser, mail queues)
  scraper/      LinkedIn and Naukri job scraping adapters
  matcher/      OpenAI embedding client and weighted semantic ranking
  resume/       Claude-powered tailoring + ATS-safe DOCX generator
  apply/        Playwright-based LinkedIn Easy Apply workflow
  tracking/     CSV/SQLite persistence + Streamlit dashboard
  orchestrator/ End-to-end pipeline
  cli/          bootstrap.py, migrate_sqlite.py
  utils/        Config, browser helpers, logging, retry, text helpers
main.py         CLI entrypoint (pipeline, scrape, match, resume, apply, worker, migrate, bootstrap, serve)
config.yaml     Central configuration
data/profile.json
```

## Features

- Config-driven scraping, matching, resume generation, application, and tracking.
- Modular package layout with clear service boundaries.
- OpenAI embeddings with cosine similarity and weighted scoring.
- Claude-based output generation for tailored resume text, recruiter pitch, and cover letter.
- ATS-safe DOCX generation with a simple single-column layout.
- Playwright browser automation with session reuse, human-like delays, upload support, and multi-step form handling.
- Ordered selector fallback lists for scraper resilience when LinkedIn or Naukri change their markup.
- SQLite or CSV tracking plus a Streamlit dashboard.
- Optional Notion sync for application tracking status reporting.
- Structured logging and retry wrappers for external API calls.

## Setup

1. Create and activate a virtual environment.

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies.

```bash
pip install -r requirements.txt
playwright install chromium
```

3. Configure API keys.

```bash
cp .env.example .env
```

Set:

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `NOTION_API_KEY` if you want local tracking records pushed into Notion

4. Update `data/profile.json` with your real profile details.

5. Review `config.yaml`:

- add or change search queries
- adjust scraping selectors if LinkedIn or Naukri change their DOM
- choose `tracking.mode` as `sqlite` or `csv`
- decide whether final submission should pause for manual review
- confirm `notion.application_tracking_data_source_id` points to your Notion tracking data source

## Usage

Run the full pipeline:

```bash
python3 main.py --config config.yaml pipeline
```

Run without final submission:

```bash
python3 main.py --config config.yaml pipeline --skip-apply
```

Run phase by phase:

```bash
python3 main.py --config config.yaml scrape
python3 main.py --config config.yaml match
python3 main.py --config config.yaml resume
python3 main.py --config config.yaml apply
python3 main.py --config config.yaml sync-notion
```

Launch the dashboard:

```bash
python3 main.py --config config.yaml dashboard
```

Run the unit tests:

```bash
python -m pytest -v --ignore=scratch
```

Run database migrations:

```bash
python main.py migrate
```

Start the FastAPI server (W2+):

```bash
python main.py serve --port 8000
```

Generate a device-pairing QR code:

```bash
python main.py bootstrap
```

## Docker

Build the image:

```bash
docker build -t job-automation-ai .
```

Run the pipeline in a container:

```bash
docker run --rm -it --env-file .env -v "$(pwd):/app" job-automation-ai \
  python3 main.py --config config.yaml pipeline --skip-apply
```

Use Docker Compose:

```bash
docker compose run --rm app
docker compose run --rm app python3 -m unittest discover -s tests -v
docker compose up dashboard
```

## Pipeline Flow

1. Scrape jobs from LinkedIn and Naukri using Playwright and selector-driven parsers.
2. Generate OpenAI embeddings for the profile and each job.
3. Score jobs using:
   - description similarity
   - title similarity
   - profile skill overlap
4. Keep the top-ranked matches above the configured threshold.
5. Send the candidate profile plus job description to Claude.
6. Save:
   - ATS-safe tailored resume text
   - recruiter pitch
   - cover letter
   - resume DOCX
7. Reuse the LinkedIn browser session and walk the Easy Apply flow.
8. Track every job state in SQLite or CSV and inspect results in Streamlit.
9. Optionally sync local application records into the configured Notion data source.

## Notes

- The first scraping or apply run will open a browser and wait for you to log in if saved cookies are not available.
- LinkedIn and Naukri markup changes over time. Each selector key in `config.yaml` can now hold an ordered list of fallback selectors, so update the config before changing scraper code.
- The Easy Apply flow defaults to semi-automated behavior by pausing before final submission when `manual_review_required: true`.
- Notion sync is best-effort. If the token or data source access is missing, the local pipeline still runs and logs a warning.
- This project assumes you will use it in line with each platform's terms, rate limits, and account policies.

## Output Locations

- scraped jobs: `artifacts/jobs/jobs.json`
- tailored resumes: `artifacts/resumes/`
- cover letters: `artifacts/covers/`
- recruiter pitches: `artifacts/pitches/`
- tracking DB or CSV: `artifacts/`
- logs: `logs/job_automation.log`
- Notion application tracking data source: configured in `config.yaml`
