# SP4 — Job Search Automation

**Date:** 2026-05-15  
**Branch:** prod/w3-console  
**Scope:** Saved searches in DB → periodic auto-discovery (scrape + match) → FCM push on new matches → Android Settings UI to manage searches.  
**Out of scope:** auto-apply, auto-tailor (discovery only).

---

## Tasks

| # | What | Layer |
|---|------|-------|
| 1 | `SavedSearch` ORM + migration `c4d5e6f7a8b9` | Backend |
| 2 | `SavedSearchesRepository` CRUD + `SearchIn`/`SearchOut` schemas | Backend |
| 3 | `/api/v1/searches` router (GET/POST/PATCH/DELETE + `POST /{id}/run`) | Backend |
| 4 | `ScraperService.scrape(queries, sources)` dynamic override | Backend |
| 5 | `run_discovery` Celery task — scrape→match→push→update timestamps | Backend |
| 6 | `run_due_searches` beat task + `beat_schedule` in `celery_app.py` | Backend |
| 7 | Android `SavedSearchDto` + `JobAiService` endpoints | Android |
| 8 | `SearchesViewModel` + `SearchesSection` in `SettingsScreen` | Android |

---

## Data Model

```python
class SavedSearch(Base):
    id: UUID
    keywords: str
    location: str
    sources: list[str]         # JSONB — ["linkedin", "indeed", ...]
    min_match_score: float     # default 0.6 — threshold for notification
    enabled: bool              # default True
    run_every_hours: int       # default 24
    last_run_at: datetime | None
    next_run_at: datetime | None
    created_at: datetime
```

---

## API

| Method | Path | What |
|--------|------|------|
| `POST` | `/api/v1/searches` | Create saved search |
| `GET` | `/api/v1/searches` | List all |
| `PATCH` | `/api/v1/searches/{id}` | Update (enabled, keywords, etc.) |
| `DELETE` | `/api/v1/searches/{id}` | Delete |
| `POST` | `/api/v1/searches/{id}/run` | Trigger immediate discovery run |

---

## Discovery Task Flow

```
run_discovery(search_id, correlation_id)
  → load SavedSearch
  → ScraperService.scrape(queries=[{keywords, location}], sources=saved.sources)
  → upsert new jobs (status="new")
  → JobMatcher.rank() on status="new" jobs
  → count jobs with match_score >= min_match_score
  → if count > 0: PushService.send_fcm("N new matches for '{keywords}'")
  → update last_run_at, next_run_at = now + timedelta(hours=run_every_hours)
```

```
run_due_searches() [beat, every 30 min]
  → list SavedSearch where enabled=True AND (next_run_at IS NULL OR next_run_at <= now)
  → for each: run_discovery.delay(search_id, correlation_id=uuid4())
```

---

## Android

- `SavedSearchDto(id, keywords, location, sources, minMatchScore, enabled, runEveryHours, lastRunAt, nextRunAt)`
- `SearchesViewModel`: load/create/toggle/delete/trigger searches via API
- `SearchesSection` composable embedded in `SettingsScreen` between Gmail and Unpair
  - Cards per search: keywords chip, location, enabled `Switch`, "Run" icon button, delete icon
  - `+ Add Search` button → `AlertDialog` with keywords + location text fields

---

## Architecture Decisions

- `ScraperService.scrape(queries=None, sources=None)` — `None` falls back to config; both args respected when provided
- Beat task runs as plain `@celery_app.task` (not `@pipeline_task` — no idempotency/audit needed for the dispatcher)
- `run_discovery` uses `@pipeline_task(stage="discovery", queue="scrape")` for idempotency + audit
- FCM push sent via `_push_on_complete` pattern reusing PushService from `src/notifications/push.py`
- Migration revision: `c4d5e6f7a8b9`, down_revision: `b3c4d5e6f7a8`
