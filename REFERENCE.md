# JobAI — Command Reference

## Ports & Services

### JobAI App

| Port | Service | Notes |
|------|---------|-------|
| **9999** | FastAPI server | Operator console + REST API |
| **5432** | PostgreSQL | Docker, localhost only |
| **6379** | Redis | Docker, localhost only (Celery broker + auth) |

### Observability Stack (`~/Work/observability`)

| Port | Service |
|------|---------|
| **3000** | Grafana |
| **3100** | Loki (log aggregation) |
| **3200** | Tempo (distributed tracing) |
| **4317** | OpenTelemetry Collector (gRPC) |
| **4318** | OpenTelemetry Collector (HTTP) |
| **9090** | Prometheus |
| **9100** | Node Exporter |
| **8001** | Claude metrics exporter |
| **8002** | AI observability app |
| **8080** | Observability portal (static) |
| **16379** | Redis (observability stack) |
| **35432** | PostgreSQL (observability stack) |

### Other Local Services

| Port | Service |
|------|---------|
| **3101** | iPAW API |
| **5174** | iPAW Vite frontend |
| **11434** | Ollama (local LLM) |

---

## JobAI Systemd Services

All services auto-start on boot. Managed via `systemctl --user`.

### Start / Stop / Restart

```bash
# All at once
systemctl --user start   jobai-server jobai-worker-default jobai-worker-scrape jobai-beat
systemctl --user stop    jobai-server jobai-worker-default jobai-worker-scrape jobai-beat
systemctl --user restart jobai-server jobai-worker-default jobai-worker-scrape jobai-beat

# Individual
systemctl --user restart jobai-server          # restart API (after code changes)
systemctl --user restart jobai-worker-default  # restart default + browser workers
systemctl --user restart jobai-worker-scrape   # restart scrape worker
systemctl --user restart jobai-beat            # restart beat scheduler
```

### Status

```bash
systemctl --user status jobai-server
systemctl --user status jobai-worker-default jobai-worker-scrape jobai-beat
```

### Logs

```bash
# Live tail via journald
journalctl --user -u jobai-server -f
journalctl --user -u jobai-worker-default -f
journalctl --user -u jobai-worker-scrape -f
journalctl --user -u jobai-beat -f

# Log files
tail -f logs/celery-default.log
tail -f logs/celery-scrape.log
tail -f logs/celery-beat.log
```

---

## Docker (PostgreSQL + Redis)

```bash
# Start
docker compose -f docker-compose.dev.yml up -d

# Stop
docker compose -f docker-compose.dev.yml stop

# Status
docker compose -f docker-compose.dev.yml ps

# Logs
docker compose -f docker-compose.dev.yml logs -f postgres
docker compose -f docker-compose.dev.yml logs -f redis
```

---

## Celery

```bash
# Check workers alive
.venv/bin/celery -A src.tasks.celery_app inspect ping

# List registered tasks
.venv/bin/celery -A src.tasks.celery_app inspect registered

# Active tasks right now
.venv/bin/celery -A src.tasks.celery_app inspect active

# Queue lengths
.venv/bin/celery -A src.tasks.celery_app inspect reserved

# Purge all queues (danger — drops pending tasks)
.venv/bin/celery -A src.tasks.celery_app purge
```

---

## Database

```bash
# Connect to PostgreSQL
docker compose -f docker-compose.dev.yml exec postgres \
  psql -U jobauto -d jobautomation

# Run Alembic migrations
.venv/bin/python -m alembic upgrade head

# Check current migration version
.venv/bin/python -m alembic current

# Show migration history
.venv/bin/python -m alembic history

# Redis CLI
docker compose -f docker-compose.dev.yml exec redis redis-cli
```

---

## Tests

```bash
# Run all API tests (use python -m pytest, not bare pytest)
python -m pytest tests/api/ -v

# Run specific suite
python -m pytest tests/api/test_jobs.py -v
python -m pytest tests/api/test_searches.py -v
python -m pytest tests/api/test_applications.py -v

# Run with output (no capture)
python -m pytest tests/api/ -v -s
```

---

## Bootstrap & Pairing

```bash
# Generate bootstrap secret to pair browser or Android app
python main.py bootstrap

# Server with explicit host/port
python main.py serve --host 0.0.0.0 --port 8000
```

---

## Troubleshooting

### Server won't start
```bash
# Check port already in use
ss -tlnp | grep 8000

# Check .env has required keys
grep -E "OPENAI_API_KEY|DATABASE_URL|CELERY_BROKER_URL" .env

# Test settings load
.venv/bin/python -c "from src.settings import get_settings; print(get_settings())"

# Check DB connection
docker compose -f docker-compose.dev.yml ps
```

### Celery workers not responding
```bash
# Check Redis is up
docker compose -f docker-compose.dev.yml exec redis redis-cli ping

# Restart all workers
systemctl --user restart jobai-worker-default jobai-worker-scrape jobai-beat

# Check for errors
journalctl --user -u jobai-worker-default -n 50 --no-pager
```

### Task stuck / not running
```bash
# See what's queued in Redis
docker compose -f docker-compose.dev.yml exec redis redis-cli llen celery

# Check DLQ in operator console
open http://localhost:8000/#/dlq

# Inspect active tasks
.venv/bin/celery -A src.tasks.celery_app inspect active
```

### Migration errors
```bash
# Check current head
.venv/bin/python -m alembic heads

# Stamp to specific revision if out of sync
.venv/bin/python -m alembic stamp <revision_id>
```

### Android app can't connect
```bash
# Find your LAN IP
ip addr | grep "inet " | grep -v 127

# Verify server reachable from LAN
curl http://<your-lan-ip>:8000/health

# Re-pair: generate new bootstrap secret
python main.py bootstrap
```
