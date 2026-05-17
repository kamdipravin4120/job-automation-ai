# SP3c — Recruiter Intelligence

**Date:** 2026-05-15
**Branch:** prod/w3-console
**Precondition:** SP3b complete (15 commits, 59/59 tests pass)

---

## Goal

When Gmail is synced, automatically extract recruiter contacts, link emails to applications, and surface follow-up reminders on Android.

---

## Scope (8 tasks)

| # | Layer | What |
|---|-------|------|
| 1 | DB | Alembic migration — `last_contact_at` + `next_follow_up_at` on Application |
| 2 | Backend | `RecruiterExtractor` — parse name/email/company from sender header + Claude Haiku |
| 3 | Backend | `ApplicationLinker` — match email to Application by company (join Jobs table) |
| 4 | Backend | Gmail sync enrichment — run linker+extractor per email, write recruiter/email_status/last_contact_at |
| 5 | Backend | ApplicationOut update — recruiter, email_status, last_contact_at, next_follow_up_at, job_title, company |
| 6 | Backend | `GET /api/v1/applications/follow-ups` endpoint |
| 7 | Android | ApplicationDto + ApplicationEntity + domain model update |
| 8 | Android | TrackerRepository enrichment + ApplicationDetailScreen recruiter card + follow-up badge |

---

## Out of Scope (future)

- Thread record creation / email history listing
- User-settable next_follow_up_at date
- Gmail token migration to Integration DB table

---

## Key Architecture Decisions

### Matching strategy
- Extract company from email subject+body using Claude Haiku
- Query `SELECT applications.* FROM applications JOIN jobs ON applications.job_id = jobs.id WHERE LOWER(jobs.company) LIKE LOWER('%{company}%')` 
- Take first match; skip if no match (email not linked)
- Extractor also parses sender name+email from `From:` header directly (no Claude needed for those)

### Follow-up rules
Application surfaces in follow-ups if:
1. `email_status == 'follow_up_needed'` (classifier said so), OR
2. `submitted_at < now() - 7 days` AND `email_status IS NULL` (no response yet)

AND `next_follow_up_at IS NULL OR next_follow_up_at <= now()`

### Application.recruiter JSONB shape
```json
{
  "name": "Jane Smith",
  "email": "jane@company.com",
  "company": "Acme Corp"
}
```

### ApplicationOut new fields
- `recruiter: dict | None` — raw JSONB passthrough
- `email_status: str | None`
- `last_contact_at: datetime | None`
- `next_follow_up_at: datetime | None`
- `job_title: str` — joined from Job table
- `job_company: str` — joined from Job table

---

## Key File Locations

| File | Purpose |
|------|---------|
| `src/gmail/recruiter.py` | `RecruiterExtractor` — contact parsing |
| `src/gmail/linker.py` | `ApplicationLinker` — company matching |
| `src/api/routers/gmail.py` | Gmail sync endpoint (update) |
| `src/api/routers/applications.py` | Add follow-ups endpoint |
| `src/api/schemas/applications.py` | ApplicationOut (update) |
| `src/data/repositories/applications.py` | Add follow_ups query |
| `src/data/models/application.py` | Add 2 columns |
| `src/data/migrations/versions/` | New migration |
| `android/.../tracker/TrackerRepository.kt` | Job enrichment fix |
| `android/.../tracker/ApplicationDetailScreen.kt` | Recruiter card |
| `android/.../tracker/TrackerScreen.kt` | Follow-up badge |
| `android/.../core/api/JobAiService.kt` | ApplicationDto update |
| `android/.../core/db/ApplicationEntity.kt` | Entity update |
| `android/.../core/model/Application.kt` | Domain model update |
