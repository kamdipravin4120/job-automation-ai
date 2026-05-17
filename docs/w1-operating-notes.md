# W1 Operating Notes

## Local dev loop

```bash
# 1. Start infra
docker compose up postgres redis -d

# 2. Create .env from .env.example; fill in the API keys.

# 3. Apply migrations
python main.py migrate

# 4. Import legacy SQLite (optional, one-time)
python main.py migrate-sqlite --from artifacts/tracking.sqlite

# 5. Start a worker in a second terminal
python main.py worker --queues scrape,ai,browser,mail

# 6. Enqueue work the normal way
python main.py pipeline
```

## Running tests

```bash
# Unit + repo + CLI tests: no infra needed for a subset
python -m pytest tests/test_errors.py tests/test_settings.py tests/observability -v

# Everything, including testcontainers-backed repo + migration + e2e
python -m pytest -v
```

## Migrations

- Schema changes: edit ORM under `src/data/models/`, then
  `alembic revision --autogenerate -m "<message>"`. Review the
  generated file before committing.
- `alembic upgrade head` applies. `alembic downgrade -1` reverts.
- Never edit committed migrations. Always generate a new one.

## Debugging a stuck run

- `SELECT * FROM runs WHERE status='running' ORDER BY started_at DESC LIMIT 20;`
- Kill the orphaned row: `UPDATE runs SET status='failed', error_code='STALE' WHERE id=...;`
- Re-enqueue by calling the CLI command again — idempotency key prevents the
  still-running (if any) duplicate from doing work.

## What's not here yet

See `docs/superpowers/specs/2026-04-21-production-web-app-design.md` §4.2–§4.6
for W2–W6 scope.
